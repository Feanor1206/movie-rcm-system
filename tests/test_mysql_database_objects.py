from decimal import Decimal
import json
import os
import re
import secrets
import shutil
import subprocess
import sys

import pymysql
import pytest
from sqlalchemy.orm import Session

from mysql_database_support import ROOT, mysql_database, mysql_executable

sys.path.insert(0, str(ROOT / "backend/fastapi"))
from services.database import DatabaseManager, export_eligible_catalog


OBJECTS = ROOT / "database/objects"
OBJECT_FILES = ("views.sql", "functions.sql", "procedures.sql", "triggers.sql")
INIT_SCHEMA = ROOT / "database/schema/01_init.sql"


@pytest.fixture
def mysql_objects(mysql_database):
    with mysql_database.schema() as engine:
        name = engine.url.database
        mysql_database.run_sql(name, INIT_SCHEMA)
        mysql_database.run_sql(name, "DROP TABLE audit_log;")
        for _ in range(2):
            mysql_database.run_sql(name, ROOT / "database/migrations/09_audit_log.sql")
        mysql_database.run_sql(name, """
INSERT INTO users (id,username,email,password) VALUES (10,'viewer','viewer@invalid.test','stored');
INSERT INTO movies (id,title,release_year,rating) VALUES ('movie','Movie',2026,7);
INSERT INTO movie_ratings (user_id,movie_id,rating) VALUES (10,'movie',8);
INSERT INTO catalog_series (id,title) VALUES ('series','Series');
INSERT INTO catalog_seasons (id,series_id,title,number,kind) VALUES ('season','series','Season',1,'regular');
INSERT INTO catalog_episodes (id,series_id,season_id,number,title,synopsis,kind,duration_ms,publication_status,record_json,raw_json)
VALUES ('published','series','season',1,'Episode 1','Plot','regular',1000,'ready','{"status":"ready"}',NULL),
       ('complete','series','season',2,'Episode 2','Detailed plot','regular',1000,'draft','{"status":"draft","revision":1}',
        '{"id":"complete","series_id":"series","record":{"status":"draft","revision":1}}'),
       ('incomplete','series','season',3,'Episode 3',NULL,'regular',1000,'draft','{"status":"draft"}',NULL);
INSERT INTO catalog_genres (id,labels_json) VALUES ('genre','{"vi":"Thiếu nhi"}');
INSERT INTO catalog_episode_genres VALUES ('published','genre'),('complete','genre');
INSERT INTO catalog_media_assets (id,storage_provider,storage_key,relative_path,duration_ms)
VALUES ('asset','local','demo','video.mp4',1000);
INSERT INTO catalog_episode_assets VALUES ('published','asset');
""")
        passwords = {role: secrets.token_hex(16) + " 'a\\b$" for role in ("app", "readonly", "admin")}
        variables = "\n".join(
            f"SET @dippie_db_{role}_password = CONVERT(0x{value.encode('utf-8').hex()} USING utf8mb4);"
            for role, value in passwords.items()
        )
        mysql_database.run_sql(name, "\n".join([
            *((OBJECTS / file).read_text(encoding="utf-8") for file in OBJECT_FILES),
            variables, (OBJECTS / "security.sql").read_text(encoding="utf-8"),
        ]))
        powershell = shutil.which("pwsh")
        if powershell:
            env = {**os.environ, **{f"DIPPIE_DB_{role.upper()}_PASSWORD": value for role, value in passwords.items()}}
            result = subprocess.run([
                powershell, "-NoProfile", "-File", str(ROOT / "scripts/load_database_objects.ps1"),
                "-Database", name, "-Port", str(mysql_database.port), "-Client", mysql_executable("mysql"),
                "-DefaultsFile", str(mysql_database.ini),
            ], env=env, capture_output=True, timeout=45, creationflags=mysql_database.flags)
            assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
        else:
            for file in OBJECT_FILES:
                mysql_database.run_sql(name, OBJECTS / file)
            mysql_database.run_sql(name, variables + "\n" + (OBJECTS / "security.sql").read_text(encoding="utf-8"))
        yield engine, passwords


def test_mysql_views_and_functions(mysql_database, mysql_objects):
    engine, _ = mysql_objects
    with mysql_database.connection(engine.url.database) as db, db.cursor() as cursor:
        cursor.execute("SELECT episode_id,series_title,season_title FROM v_published_episodes WHERE episode_id='published'")
        assert cursor.fetchone() == ("published", "Series", "Season")
        cursor.execute("SELECT episode_count,total_duration_ms FROM v_genre_stats WHERE genre_id='genre'")
        assert cursor.fetchone() == (1, 1000)
        cursor.execute("SELECT rating_count,average_rating FROM v_movie_rating_summary WHERE movie_id='movie'")
        assert cursor.fetchone() == (1, Decimal("8.00"))
        cursor.execute("SELECT fn_movie_avg_rating('movie'),fn_movie_avg_rating('missing')")
        assert cursor.fetchone() == (Decimal("8.00"), None)
        cursor.execute("INSERT INTO watch_progress (user_id,episode_id,asset_id,position_ms) VALUES (10,'published','asset',250)")
        cursor.execute("SELECT position_ms,episode_title FROM v_user_watch_history WHERE user_id=10")
        assert cursor.fetchone() == (250, "Episode 1")
        cursor.execute("SELECT fn_episode_progress_pct(10,'published'),fn_episode_progress_pct(11,'published')")
        assert cursor.fetchone() == (Decimal("25.00"), Decimal("0.00"))
        cursor.execute("DELETE FROM watch_progress WHERE user_id=10")


def test_mysql_procedures_and_audit(mysql_database, mysql_objects):
    engine, passwords = mysql_objects
    with mysql_database.connection(engine.url.database, "dippie_app", passwords["app"]) as db, db.cursor() as cursor:
        cursor.execute("CALL sp_add_favorite(10,'movie')")
        favorite = cursor.fetchone()
        cursor.execute("CALL sp_add_favorite(10,'movie')")
        assert cursor.fetchone() == favorite
        cursor.execute("SELECT COUNT(*) FROM favorite_items WHERE user_id=10 AND movie_id='movie'")
        assert cursor.fetchone() == (1,)
        with pytest.raises(pymysql.IntegrityError):
            cursor.execute("CALL sp_add_favorite(10,'missing')")
        cursor.execute("CALL sp_next_episode(10,'series')")
        assert cursor.fetchone()[0] == "published"
        cursor.execute("INSERT INTO watch_progress (user_id,episode_id,asset_id,position_ms) VALUES (10,'published','asset',1000)")
        with mysql_database.connection(engine.url.database) as observer, observer.cursor() as other:
            other.execute("SELECT position_ms FROM watch_progress WHERE user_id=10")
            assert other.fetchone() == (1000,)
        cursor.execute("CALL sp_next_episode(10,'series')")
        assert cursor.fetchone() is None
        with pytest.raises(pymysql.MySQLError, match="metadata") as rejected:
            cursor.execute("CALL sp_publish_episode('incomplete')")
        assert rejected.value.args[0] == 1644
        cursor.execute("CALL sp_publish_episode('complete')")
        cursor.execute("CALL sp_next_episode(10,'series')")
        assert cursor.fetchone()[0] == "complete"
        cursor.execute("SELECT publication_status,record_json,raw_json FROM catalog_episodes WHERE id='complete'")
        status, record, raw = cursor.fetchone()
        assert status == json.loads(record)["status"] == "ready"
        assert json.loads(raw)["record"]["status"] == "draft"
        cursor.execute("DELETE FROM catalog_episodes WHERE id='incomplete'")
        cursor.execute("SELECT operation,old_values,new_values,mysql_user FROM audit_log ORDER BY id")
        update, delete = cursor.fetchall()
        assert update[0] == "UPDATE"
        assert json.loads(update[1])["publication_status"] == "draft"
        assert json.loads(update[2])["publication_status"] == "ready"
        assert delete[0] == "DELETE" and json.loads(delete[1])["id"] == "incomplete" and delete[2] is None
        assert all(row[3].startswith("dippie_app@") for row in (update, delete))
        cursor.execute("DELETE FROM watch_progress WHERE user_id=10")
    with Session(engine) as session:
        exported = export_eligible_catalog(session)
        assert exported["episodes"][0]["record"]["status"] == "ready"


def test_mysql_watch_progress_triggers_block_invalid_insert_and_update(mysql_database, mysql_objects):
    engine, _ = mysql_objects
    insert = "INSERT INTO watch_progress (user_id,episode_id,asset_id,position_ms) VALUES (10,'published','asset',%s)"
    with mysql_database.connection(engine.url.database) as db, db.cursor() as cursor:
        with pytest.raises(pymysql.MySQLError, match="duration_ms") as rejected:
            cursor.execute(insert, (1001,))
        assert rejected.value.args[0] == 1644
        cursor.execute(insert, (1000,))
        with pytest.raises(pymysql.MySQLError, match="duration_ms") as rejected:
            cursor.execute("UPDATE watch_progress SET position_ms=1001 WHERE user_id=10")
        assert rejected.value.args[0] == 1644
        cursor.execute("SELECT position_ms FROM watch_progress WHERE user_id=10")
        assert cursor.fetchone() == (1000,)
        cursor.execute("DELETE FROM watch_progress WHERE user_id=10")


def test_mysql_account_privileges(mysql_database, mysql_objects):
    engine, passwords = mysql_objects
    name = engine.url.database
    with mysql_database.connection(name, "dippie_readonly", passwords["readonly"]) as db, db.cursor() as cursor:
        for view in ("v_published_episodes", "v_genre_stats", "v_user_watch_history", "v_movie_rating_summary"):
            cursor.execute(f"SELECT COUNT(*) FROM {view}")
        for statement in ("SELECT password FROM users", "DELETE FROM v_movie_rating_summary WHERE movie_id='movie'",
                          "INSERT INTO movies (id,title,release_year,rating) VALUES ('denied','Denied',2026,0)"):
            with pytest.raises(pymysql.MySQLError) as denied:
                cursor.execute(statement)
            assert denied.value.args[0] in (1142, 1143)
    with mysql_database.connection(name, "dippie_app", passwords["app"]) as db, db.cursor() as cursor:
        cursor.execute("SELECT fn_movie_avg_rating('movie')")
        assert cursor.fetchone() == (Decimal("8.00"),)
        for statement in ("CREATE TABLE denied_ddl (id INT)", "ALTER TABLE users ADD test_only INT"):
            with pytest.raises(pymysql.MySQLError) as denied:
                cursor.execute(statement)
            assert denied.value.args[0] == 1142
        neighboring_schema = name.replace("_", "x")
        with mysql_database.connection() as admin, admin.cursor() as root:
            root.execute(f"CREATE DATABASE `{neighboring_schema}`")
            try:
                root.execute(f"CREATE TABLE `{neighboring_schema}`.probe (id INT)")
                with pytest.raises(pymysql.MySQLError) as denied:
                    cursor.execute(f"SELECT * FROM `{neighboring_schema}`.probe")
                assert denied.value.args[0] in (1044, 1142)
            finally:
                root.execute(f"DROP DATABASE `{neighboring_schema}`")
    with mysql_database.connection(name, "dippie_admin", passwords["admin"]) as db, db.cursor() as cursor:
        cursor.execute("CREATE TABLE privilege_probe (id INT PRIMARY KEY)")
        cursor.execute("DROP TABLE privilege_probe")
    app_url = engine.url.set(username="dippie_app", password=passwords["app"])
    manager = DatabaseManager(app_url.render_as_string(hide_password=False), seed=False)
    try:
        assert manager.healthy()
    finally:
        if manager.engine:
            manager.engine.dispose()


def test_mysql_transaction_exercises_use_two_sessions(mysql_database, mysql_objects):
    engine, _ = mysql_objects
    source = (OBJECTS / "transactions_demo.sql").read_text(encoding="utf-8")
    blocks = re.split(r"SELECT '([a-z_]+)' AS exercise;\s*", source)
    exercises = dict(zip(blocks[1::2], blocks[2::2], strict=True))

    def run(cursor, exercise):
        reads = []
        for statement in exercises[exercise].split(";"):
            if statement.strip():
                cursor.execute(statement)
                if cursor.description:
                    reads.append(cursor.fetchone()[0])
        return reads

    with mysql_database.connection(engine.url.database) as reader, reader.cursor() as first, \
         mysql_database.connection(engine.url.database) as writer, writer.cursor() as second:
        first.execute("INSERT INTO movies (id,title,release_year,rating) VALUES ('the-last-orbit','Demo',2026,7)")
        assert run(first, "savepoint_walkthrough") == [7.0, 10.0, 7.0]
        for isolation, expected in (("read_committed_begin", 10.0), ("repeatable_read_begin", 7.0)):
            assert run(first, isolation) == [7.0]
            run(second, "writer_change")
            assert run(first, "reader_finish") == [expected]
            run(second, "writer_restore")


def test_mysql_sample_queries_execute_in_documented_order(mysql_database, mysql_objects):
    engine, _ = mysql_objects
    source = (ROOT / "database/queries/sample_queries.sql").read_text(encoding="utf-8-sig")
    queries = [statement.strip() for statement in source.split(";") if statement.strip()]
    assert len(queries) == 20
    columns = []
    results = []
    with mysql_database.connection(engine.url.database) as db, db.cursor() as cursor:
        for query in queries:
            cursor.execute(query)
            columns.append(tuple(column[0] for column in cursor.description))
            results.append(cursor.fetchall())
    assert columns[0][-1] == "character_name"
    assert columns[5][-1] == "duration_rank"
    assert columns[6][-1] == "previous_episode_number"
    assert columns[16][-1] == "cumulative_positions_ms"
    assert results[8][0] == (0, 5, 1)
    assert results[13][0][2:] == (3, 2, 1, 0)
    assert results[17] == (("genre", 1, Decimal("0.00")),)
