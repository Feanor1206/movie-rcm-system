import re
import sys

from sqlalchemy import text

from mysql_database_support import ROOT, mysql_database

sys.path.insert(0, str(ROOT / "backend/fastapi"))
from services.database import Base


INIT_SCHEMA = ROOT / "database/schema/01_init.sql"
MIGRATIONS = ROOT / "database/migrations"
MIGRATION_07 = MIGRATIONS / "07_catalog_publication_and_tracks.sql"

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
VALUES ('episode','series','Episode','episode','{"status":"ready"}','["genre"]','["character"]');
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
