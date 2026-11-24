import re
import sys

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from mysql_database_support import ROOT, mysql_database

sys.path.insert(0, str(ROOT / "backend/fastapi"))
from services.database import Base


INIT_SCHEMA = ROOT / "database/schema/01_init.sql"
MIGRATIONS = ROOT / "database/migrations"
MIGRATION_07 = MIGRATIONS / "07_catalog_publication_and_tracks.sql"
MIGRATION_08 = MIGRATIONS / "08_catalog_value_domains.sql"

REFERENCES_07 = (
    ("watchlist_items", "fk_watchlist_movie"),
    ("favorite_items", "fk_favorite_movie"),
    ("movie_ratings", "fk_rating_movie"),
    ("watch_progress", "fk_watch_progress_asset"),
    ("catalog_scenes", "fk_scene_asset"),
    ("catalog_scenes", "fk_scene_segment"),
    ("catalog_media_assets", "fk_asset_related"),
)


def describe_schema(engine):
    statements = {
        "tables": "SELECT table_name, engine, table_collation FROM information_schema.tables "
                  "WHERE table_schema=DATABASE() ORDER BY table_name",
        "columns": "SELECT table_name, column_name, column_type, is_nullable, column_default, extra, collation_name "
                   "FROM information_schema.columns WHERE table_schema=DATABASE() ORDER BY table_name,column_name",
        "indexes": "SELECT table_name,index_name,non_unique,seq_in_index,column_name,sub_part,collation,index_type "
                   "FROM information_schema.statistics WHERE table_schema=DATABASE() ORDER BY table_name,index_name,seq_in_index",
        "foreign_keys": "SELECT k.table_name,k.constraint_name,k.ordinal_position,k.column_name,k.referenced_table_name,"
                        "k.referenced_column_name,f.update_rule,f.delete_rule FROM information_schema.key_column_usage k "
                        "JOIN information_schema.referential_constraints f ON f.constraint_schema=k.constraint_schema "
                        "AND f.table_name=k.table_name AND f.constraint_name=k.constraint_name "
                        "WHERE k.table_schema=DATABASE() AND k.referenced_table_name IS NOT NULL "
                        "ORDER BY k.table_name,k.constraint_name,k.ordinal_position",
        "checks": "SELECT t.table_name,t.constraint_name,c.check_clause,t.enforced FROM information_schema.table_constraints t "
                  "JOIN information_schema.check_constraints c ON c.constraint_schema=t.constraint_schema "
                  "AND c.constraint_name=t.constraint_name WHERE t.table_schema=DATABASE() "
                  "AND t.constraint_type='CHECK' ORDER BY t.table_name,t.constraint_name",
    }
    with engine.connect() as connection:
        schema = {group: [tuple(row) for row in connection.execute(text(query))] for group, query in statements.items()}
    schema["checks"] = [(table, name, re.sub(r"\s+", " ", clause.strip()), enforced)
                        for table, name, clause, enforced in schema["checks"]]
    return schema


def test_mysql_sql_and_sqlalchemy_schema_are_identical(mysql_database):
    with mysql_database.schema() as mysql_sql, mysql_database.schema() as mysql_orm:
        mysql_database.run_sql(mysql_sql.url.database, INIT_SCHEMA)
        Base.metadata.create_all(mysql_orm)
        sql = describe_schema(mysql_sql)
        orm = describe_schema(mysql_orm)
        differences = {}
        for group in sql:
            missing = sorted(set(sql[group]) - set(orm[group]), key=str)
            extra = sorted(set(orm[group]) - set(sql[group]), key=str)
            if missing or extra:
                differences[group] = {"from_sql": missing, "from_orm": extra}
        assert not differences, "\n".join(f"{group}: {changes!r}" for group, changes in differences.items())


def create_before_07(mysql_database, engine):
    source = INIT_SCHEMA.read_text(encoding="utf-8")
    for table in ("catalog_episode_characters", "catalog_episode_genres", "catalog_series_genres",
                  "catalog_series_characters", "catalog_character_series", "movie_genres", "movie_genre_terms"):
        source = re.sub(rf"CREATE TABLE IF NOT EXISTS {table} \(.*?\n\);\s*", "", source, flags=re.S)
    for _, constraint in REFERENCES_07 + (("catalog_text_tracks", "fk_cat_track_episode"),
                                          ("catalog_text_tracks", "fk_cat_track_source")):
        source = re.sub(rf"^    CONSTRAINT {constraint} FOREIGN KEY .*?,?\n", "", source, flags=re.M)
    source = re.sub(r"^    (publication_status VARCHAR.*|INDEX idx_cat_ep_publication.*|"
                    r"UNIQUE KEY uq_cat_segment_position.*|INDEX idx_cat_track_episode.*)\n", "", source, flags=re.M)
    source = re.sub(r"^    CONSTRAINT (ck_cat_segment_time_range|ck_cat_text_track_origin) CHECK \(.*?\n    \),?\n",
                    "", source, flags=re.M | re.S)
    track_start = source.index("CREATE TABLE IF NOT EXISTS catalog_text_tracks")
    track_end = source.index("\n);", track_start)
    tracks = source[track_start:track_end].replace("    media_asset_id VARCHAR(100),", "    media_asset_id VARCHAR(100) NOT NULL,")
    tracks = tracks.replace("    episode_id VARCHAR(100),\n    source_id VARCHAR(100),\n", "")
    source = source[:track_start] + tracks + source[track_end:]
    for table in ("watchlist_items", "favorite_items"):
        start = source.index(f"CREATE TABLE IF NOT EXISTS {table}")
        end = source.index("\n);", start)
        if "movie_title" not in source[start:end]:
            added_at = source.index("    added_at", start, end)
            source = source[:added_at] + "    movie_title VARCHAR(255) NOT NULL,\n    poster_url VARCHAR(500),\n" + source[added_at:]
    mysql_database.run_sql(engine.url.database, source.replace(",\n);", "\n);"))


def test_mysql_migration_07_twice_backfills_links(mysql_database):
    with mysql_database.schema() as engine:
        create_before_07(mysql_database, engine)
        mysql_database.run_sql(engine.url.database, """
INSERT INTO movies (id,title,release_year,rating,genres) VALUES ('movie','Original',2026,4,'Action, Drama, action');
INSERT INTO users (id,username,email,password) VALUES (1,'reader','reader@invalid.test','stored');
INSERT INTO watchlist_items (user_id,movie_id,movie_title) VALUES (1,'movie','Snapshot');
INSERT INTO favorite_items (user_id,movie_id,movie_title) VALUES (1,'movie','Snapshot');
INSERT INTO catalog_genres (id,labels_json) VALUES ('genre','{}');
INSERT INTO catalog_series (id,title,genre_ids_json,character_ids_json) VALUES ('series','Series','["genre","missing"]','["character"]');
INSERT INTO catalog_characters (id,name,series_ids_json) VALUES ('character','Character','["series"]');
INSERT INTO catalog_episodes (id,series_id,title,kind,record_json,genre_ids_json,character_ids_json)
VALUES ('episode','series','Episode','regular','{"status":"ready"}','["genre"]','["character"]');
""")
        for _ in range(2):
            mysql_database.run_sql(engine.url.database, MIGRATION_07)
        with engine.connect() as db:
            assert db.exec_driver_sql("SELECT * FROM catalog_series_genres").all() == [("series", "genre")]
            assert db.exec_driver_sql("SELECT * FROM catalog_series_characters").all() == [("series", "character")]
            assert db.exec_driver_sql("SELECT * FROM catalog_character_series").all() == [("character", "series")]
            assert db.exec_driver_sql("SELECT * FROM catalog_episode_characters").all() == [("episode", "character")]
            assert db.exec_driver_sql("SELECT * FROM catalog_episode_genres").all() == [("episode", "genre")]
            assert db.exec_driver_sql("SELECT * FROM movie_genres ORDER BY genre_name").all() == [("movie", "action"), ("movie", "drama")]
            assert db.exec_driver_sql("SELECT publication_status FROM catalog_episodes").scalar_one() == "ready"
            assert db.exec_driver_sql("SELECT title FROM watchlist_items JOIN movies ON movies.id=movie_id").scalar_one() == "Original"
        migrated = describe_schema(engine)
        assert all((table, name) in {row[:2] for row in migrated["foreign_keys"]} for table, name in REFERENCES_07)
        assert not any(row[0] in {"watchlist_items", "favorite_items"} and row[1] in {"movie_title", "poster_url"}
                       for row in migrated["columns"])


def test_mysql_migration_07_lists_orphans_before_adding_keys(mysql_database):
    with mysql_database.schema() as engine:
        create_before_07(mysql_database, engine)
        mysql_database.run_sql(engine.url.database, """
INSERT INTO users (id,username,email,password) VALUES (1,'reader','reader@invalid.test','stored');
INSERT INTO watchlist_items (user_id,movie_id,movie_title) VALUES (1,'missing-one','One');
INSERT INTO favorite_items (user_id,movie_id,movie_title) VALUES (1,'missing-two','Two');
""")
        result = mysql_database.run_sql(engine.url.database, MIGRATION_07, check=False)
        assert result.returncode != 0
        assert b"watchlist_items\t1\tmovie_id\tmissing-one" in result.stdout
        assert b"favorite_items\t1\tmovie_id\tmissing-two" in result.stdout
        assert all((table, name) not in {row[:2] for row in describe_schema(engine)["foreign_keys"]}
                   for table, name in REFERENCES_07)


DOMAIN_CASES = (
    ("ck_catalog_package_status", "catalog_packages", {"status": "COMMITTED"}, {"status": "READY"}),
    ("ck_catalog_snapshot_status", "catalog_snapshots", {"status": "BUILDING"}, {"status": "CACHE_REQUIRED"}),
    ("ck_catalog_episode_publication", "catalog_episodes", {"publication_status": "archived"}, {"publication_status": "READY"}),
    ("ck_user_role", "users", {"role": "ROLE_ADMIN"}, {"role": "ROLE_ANONYMOUS"}),
    ("ck_catalog_asset_policy", "catalog_media_assets", {"access_policy": "authenticated"}, {"access_policy": "secret"}),
    ("ck_catalog_asset_content", "catalog_media_assets", {"content_type": "audio"}, {"content_type": "image"}),
    ("ck_catalog_asset_role", "catalog_media_assets", {"role": "audio_description"}, {"role": "poster"}),
    ("ck_catalog_source_kind", "catalog_sources", {"kind": "model_output"}, {"kind": "movie"}),
    ("ck_catalog_season_kind", "catalog_seasons", {"kind": "specials"}, {"kind": "special"}),
    ("ck_catalog_episode_kind", "catalog_episodes", {"kind": "pilot"}, {"kind": "regular "}),
    ("ck_catalog_track_kind", "catalog_text_tracks", {"kind": "ocr"}, {"kind": "mp4"}),
    ("ck_media_kind", "media_assets", {"kind": "trailer"}, {"kind": "ocr"}),
    ("ck_movie_rating_bounds", "movies", {"rating": 0}, {"rating": 10.01}),
    ("ck_catalog_series_years", "catalog_series", {"release_year_start": 2026, "release_year_end": 2026}, {"release_year_end": 2025}),
    ("ck_catalog_asset_size", "catalog_media_assets", {"size_bytes": 0}, {"size_bytes": -1}),
    ("ck_catalog_asset_duration", "catalog_media_assets", {"duration_ms": 1}, {"duration_ms": 0}),
    ("ck_catalog_episode_duration", "catalog_episodes", {"duration_ms": 1}, {"duration_ms": 0}),
    ("ck_catalog_scene_time_range", "catalog_scenes", {"start_ms": 0, "end_ms": 1}, {"end_ms": 0}),
    ("ck_catalog_scale_bounds", "catalog_attribute_scales", {"minimum": -1, "maximum": 1}, {"maximum": -1}),
)

DOMAIN_ROWS = {
    "catalog_packages": dict(version="1.0.0", revision=1, default_language="vi", import_mode="upsert",
                             reference_scope="self_contained", content_hash="test", status="COMMITTED"),
    "catalog_snapshots": dict(snapshot_version=1, content_hash="test", total_items=1, status="READY"),
    "users": dict(username="new", email="new@invalid.test", password="stored"),
    "movies": dict(title="Movie", release_year=2026, rating=1),
    "media_assets": dict(movie_id="parent-movie", kind="feature", relative_path="demo.mp4", byte_length=1),
    "catalog_media_assets": dict(storage_provider="local", storage_key="media", relative_path="demo.mp4"),
    "catalog_sources": dict(title="Source", kind="manual"),
    "catalog_series": dict(title="Series"),
    "catalog_seasons": dict(series_id="parent-series", title="Season", kind="regular"),
    "catalog_episodes": dict(series_id="parent-series", title="Episode", kind="regular", publication_status="ready"),
    "catalog_text_tracks": dict(media_asset_id="parent-asset", language="vi", kind="subtitle", format="srt"),
    "catalog_scenes": dict(episode_id="parent-episode", start_ms=0, end_ms=1),
    "catalog_attribute_scales": dict(name="Scale", minimum=0, maximum=10, levels_json="[]"),
}


@pytest.fixture(scope="module")
def mysql_domain_schema(mysql_database):
    with mysql_database.schema() as engine:
        mysql_database.run_sql(engine.url.database, INIT_SCHEMA)
        mysql_database.run_sql(engine.url.database, """
INSERT INTO movies (id,title,release_year,rating) VALUES ('parent-movie','Movie',2026,0);
INSERT INTO catalog_series (id,title) VALUES ('parent-series','Series');
INSERT INTO catalog_episodes (id,series_id,title,kind,publication_status)
VALUES ('parent-episode','parent-series','Episode','regular','ready');
INSERT INTO catalog_media_assets (id,storage_provider,storage_key,relative_path)
VALUES ('parent-asset','local','media','demo.mp4');
""")
        yield engine


@pytest.mark.parametrize("constraint,table,valid,invalid", DOMAIN_CASES, ids=[case[0] for case in DOMAIN_CASES])
@pytest.mark.parametrize("accepted", (True, False), ids=("valid", "invalid"))
def test_mysql_value_domains(mysql_domain_schema, constraint, table, valid, invalid, accepted):
    row = {**DOMAIN_ROWS[table], **valid}
    if table != "users":
        row["id"] = "checked-row"
    if not accepted:
        row.update(invalid)
    statement = text(f"INSERT INTO {table} ({', '.join(row)}) VALUES ({', '.join(':' + col for col in row)})")
    with mysql_domain_schema.connect() as db:
        if accepted:
            assert db.execute(statement, row).rowcount == 1
        else:
            with pytest.raises(DBAPIError) as failure:
                db.execute(statement, row)
            assert failure.value.orig.args[0] == 3819
            assert constraint in str(failure.value.orig)


def create_before_08(mysql_database, engine):
    source = INIT_SCHEMA.read_text(encoding="utf-8")
    constraints = "|".join(case[0] for case in DOMAIN_CASES)
    source = re.sub(rf"^    CONSTRAINT (?:{constraints}) CHECK .+\n", "", source, flags=re.M)
    source = re.sub(r"    publication_status VARCHAR\(16\).*,", "    publication_status VARCHAR(16),", source)
    source = source.replace("release_date DATE,", "release_date VARCHAR(50),")
    source = source.replace("retrieved_at DATETIME(6),", "retrieved_at VARCHAR(100),")
    mysql_database.run_sql(engine.url.database, source.replace(",\n);", "\n);"))


def test_mysql_migration_08_converts_legacy_dates_and_supports_replay(mysql_database):
    with mysql_database.schema() as engine:
        create_before_08(mysql_database, engine)
        mysql_database.run_sql(engine.url.database, """
INSERT INTO catalog_series (id,title) VALUES ('series','Series');
INSERT INTO catalog_seasons (id,series_id,title,kind,release_date) VALUES ('season','series','Season','standard','2024-02-29');
INSERT INTO catalog_episodes (id,series_id,title,kind,release_date,publication_status)
VALUES ('episode','series','Episode','episode','2026-01-02','ready');
INSERT INTO catalog_sources (id,title,kind,retrieved_at)
VALUES ('east','Source','manual','2026-11-24T01:02:03.123456+07:00'),
       ('west','Source','manual','2026-11-24T20:02:03-05:30'),
       ('utc','Source','manual','2026-11-24T01:02:03Z');
""")
        for _ in range(2):
            mysql_database.run_sql(engine.url.database, MIGRATION_08)
        with engine.connect() as db:
            assert db.exec_driver_sql("SELECT kind,release_date FROM catalog_seasons").one()[1].isoformat() == "2024-02-29"
            assert db.exec_driver_sql("SELECT kind,release_date FROM catalog_episodes").one()[0] == "regular"
            timestamps = dict(db.exec_driver_sql("SELECT id,retrieved_at FROM catalog_sources").all())
            assert {name: value.isoformat() for name, value in timestamps.items()} == {
                "east": "2026-11-23T18:02:03.123456", "west": "2026-11-25T01:32:03", "utc": "2026-11-24T01:02:03",
            }
        assert next(col for col in describe_schema(engine)["columns"]
                    if col[:2] == ("catalog_sources", "retrieved_at"))[2] == "datetime(6)"


def test_mysql_migration_08_lists_invalid_dates_before_any_alter(mysql_database):
    with mysql_database.schema() as engine:
        create_before_08(mysql_database, engine)
        mysql_database.run_sql(engine.url.database, """
INSERT INTO catalog_series (id,title) VALUES ('series','Series');
INSERT INTO catalog_seasons (id,series_id,title,release_date) VALUES ('bad-leap','series','Season','2025-02-29');
INSERT INTO catalog_episodes (id,series_id,title,kind,release_date) VALUES ('bad-month','series','Episode','regular','2026-13-10');
INSERT INTO catalog_sources (id,title,kind,retrieved_at)
VALUES ('bad-offset','Source','manual','2026-11-24T01:02:03+88:00'), ('bad-range','Source','manual','1000-01-01T01:00:00+02:00');
""")
        before = describe_schema(engine)
        result = mysql_database.run_sql(engine.url.database, MIGRATION_08, check=False)
        assert result.returncode != 0
        for value in (b"bad-leap", b"bad-month", b"bad-offset", b"bad-range"):
            assert value in result.stdout
        assert describe_schema(engine) == before
