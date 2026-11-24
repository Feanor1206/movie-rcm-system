from datetime import datetime
import hashlib
import json
import logging
from time import monotonic, sleep

from sqlalchemy import CheckConstraint, Date, DateTime, String, inspect, select, text, type_coerce
from sqlalchemy.schema import AddConstraint

from .database import (
    Base,
    CatalogCharacter,
    CatalogCharacterSeries,
    CatalogEpisode,
    CatalogGenre,
    CatalogSegment,
    CatalogSeries,
    CatalogSeriesCharacter,
    CatalogSeriesGenre,
    CatalogTextTrack,
    Movie,
    MovieGenre,
    SEGMENT_SQLITE_TYPES,
    SEGMENT_TIME_RANGE,
    _replace_catalog_links,
    _replace_episode_taxonomy,
    _replace_movie_genres,
    catalog_publication_status,
    parse_catalog_date,
    parse_catalog_datetime,
)


CATALOG_TAXONOMY = (
    (CatalogSeriesGenre, CatalogSeries, CatalogGenre, "series_id", "genre_ids", "genre_id"),
    (CatalogSeriesCharacter, CatalogSeries, CatalogCharacter, "series_id", "character_ids", "character_id"),
    (CatalogCharacterSeries, CatalogCharacter, CatalogSeries, "character_id", "series_ids", "series_id"),
)
REFERENCE_CONSTRAINTS = {
    "watchlist_items": {"fk_watchlist_movie"},
    "favorite_items": {"fk_favorite_movie"},
    "movie_ratings": {"fk_rating_movie", "ck_movie_rating_range"},
    "watch_progress": {"fk_watch_progress_asset", "ck_watch_progress_position"},
    "catalog_scenes": {"fk_scene_asset", "fk_scene_segment"},
    "catalog_media_assets": {"fk_asset_related"},
}
LIBRARY_SNAPSHOTS = {"watchlist_items", "favorite_items"}
TEMPORAL_FIELDS = {
    "catalog_sources": ("retrieved_at", DateTime, "DATETIME(6)", parse_catalog_datetime),
    "catalog_seasons": ("release_date", Date, "DATE", parse_catalog_date),
    "catalog_episodes": ("release_date", Date, "DATE", parse_catalog_date),
}
DOMAIN_TABLES = (
    "catalog_packages", "catalog_snapshots", "catalog_episodes", "users", "catalog_media_assets",
    "catalog_sources", "catalog_seasons", "catalog_text_tracks", "media_assets", "movies", "catalog_series",
    "catalog_scenes", "catalog_attribute_scales",
)


def upgrade_catalog_schema(engine):
    with engine.connect() as connection:
        dialect = connection.dialect.name
        lock_name = None
        if dialect == "sqlite":
            connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
            connection.exec_driver_sql("PRAGMA legacy_alter_table=ON")
            connection.exec_driver_sql("BEGIN IMMEDIATE")
        elif dialect == "mysql":
            name = engine.url.database or ""
            lock_name = "dippie-catalog-" + hashlib.sha256(name.encode()).hexdigest()[:32]
            deadline = monotonic() + 60
            while connection.execute(text("SELECT GET_LOCK(:name, 0)"), {"name": lock_name}).scalar() != 1:
                if monotonic() >= deadline:
                    raise RuntimeError("Không lấy được khóa nâng cấp danh mục MySQL.")
                sleep(0.25)
        try:
            inspector = inspect(connection)
            backfill_tables = {
                model.__tablename__ for model in (MovieGenre, *(rule[0] for rule in CATALOG_TAXONOMY))
                if not inspector.has_table(model.__tablename__)
            }
            Base.metadata.create_all(connection)
            _upgrade_segments(connection)
            _upgrade_episodes(connection)
            tracks_rebuilt = _upgrade_text_tracks(connection)
            _backfill_taxonomy(connection, backfill_tables)
            rebuilt = _upgrade_references(connection)
            domains_rebuilt = _upgrade_domains(connection)
            if dialect == "sqlite" and (rebuilt or tracks_rebuilt or domains_rebuilt):
                orphans = connection.exec_driver_sql("PRAGMA foreign_key_check").all()
                if orphans:
                    raise ValueError(f"Các khóa ngoại SQLite có dữ liệu mồ côi: {orphans}")
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            if dialect == "sqlite":
                connection.exec_driver_sql("PRAGMA legacy_alter_table=OFF")
                connection.exec_driver_sql("PRAGMA foreign_keys=ON")
            if lock_name:
                try:
                    connection.execute(text("SELECT RELEASE_LOCK(:name)"), {"name": lock_name})
                except Exception:
                    connection.invalidate()
                    raise


def _table_batches(connection, table, *columns):
    query = select(table.c.id, *columns).order_by(table.c.id).limit(500)
    batch = connection.execute(query).all()
    while batch:
        yield batch
        batch = connection.execute(query.where(table.c.id > batch[-1].id)).all()


def _backfill_taxonomy(connection, backfill_tables):
    for model, source, target, owner_column, field, reference_column in CATALOG_TAXONOMY:
        if model.__tablename__ not in backfill_tables:
            continue
        table = source.__table__
        target_ids = set(connection.execute(select(target.id)).scalars())
        for batch in _table_batches(connection, table, table.c[field + "_json"]):
            items = [{"id": row_id, field: [ref for ref in _legacy_reference_ids(value) if ref in target_ids]}
                     for row_id, value in batch]
            _replace_catalog_links(connection, items, model, owner_column, field, reference_column)
    if MovieGenre.__tablename__ in backfill_tables:
        for batch in _table_batches(connection, Movie.__table__, Movie.genres):
            _replace_movie_genres(connection, batch)


def _rebuild_sqlite_table(connection, table, inspector):
    old_columns = {column["name"] for column in inspector.get_columns(table.name)}
    indexes = inspector.get_indexes(table.name)
    legacy = table.name + "_previous"
    connection.exec_driver_sql(f"ALTER TABLE {table.name} RENAME TO {legacy}")
    quote = connection.dialect.identifier_preparer.quote
    for index in indexes:
        connection.exec_driver_sql(f"DROP INDEX {quote(index['name'])}")
    table.create(connection)
    copied = ", ".join(quote(column.name) for column in table.columns if column.name in old_columns)
    connection.exec_driver_sql(f"INSERT INTO {table.name} ({copied}) SELECT {copied} FROM {legacy}")
    connection.exec_driver_sql(f"DROP TABLE {legacy}")


def _upgrade_references(connection):
    inspector = inspect(connection)
    pending = []
    for name, expected in REFERENCE_CONSTRAINTS.items():
        keys = {key["name"] for key in inspector.get_foreign_keys(name)}
        checks = {check["name"] for check in inspector.get_check_constraints(name)}
        missing = expected - keys - checks
        obsolete = {column["name"] for column in inspector.get_columns(name)} & {"movie_title", "poster_url"} if name in LIBRARY_SNAPSHOTS else set()
        if missing or obsolete:
            pending.append((Base.metadata.tables[name], missing, obsolete))
    if connection.dialect.name == "sqlite":
        for table, _, _ in pending:
            _rebuild_sqlite_table(connection, table, inspector)
        return bool(pending)

    orphans = []
    for table, missing, _ in pending:
        for key in table.foreign_keys:
            if key.name not in missing:
                continue
            parent = key.column.table.alias("parent")
            reference = table.c[key.parent.name]
            orphan_rows = select(table.c.id, reference).select_from(
                table.outerjoin(parent, parent.c[key.column.name] == reference)
            ).where(reference.is_not(None), parent.c[key.column.name].is_(None))
            orphans.extend((table.name, row_id, reference.name, ref) for row_id, ref in connection.execute(orphan_rows))
    if orphans:
        raise ValueError(f"Các khóa ngoại MySQL có dữ liệu mồ côi: {orphans}")
    for table, missing, obsolete in pending:
        for constraint in table.constraints:
            if constraint.name in missing:
                connection.execute(AddConstraint(constraint))
        for column in sorted(obsolete):
            connection.exec_driver_sql(f"ALTER TABLE {table.name} DROP COLUMN {column}")


def _normalize_legacy_dates(connection, conversions):
    pending = []
    invalid = []
    for table, field, parse in conversions:
        for batch in _table_batches(connection, table, type_coerce(table.c[field], String())):
            updates = []
            for row_id, value in batch:
                if value is None:
                    continue
                try:
                    converted = parse(value)
                except (OverflowError, TypeError, ValueError):
                    invalid.append((table.name, row_id, field, value))
                    continue
                stored = (converted.isoformat(sep=" ", timespec="microseconds")
                          if isinstance(converted, datetime) else converted.isoformat())
                if stored != value:
                    updates.append({"id": row_id, "value": stored})
            if updates:
                pending.append((table.name, field, updates))
    if invalid:
        raise ValueError(f"Ngày giờ cũ không chuyển đổi được: {invalid}")
    for table, field, updates in pending:
        connection.execute(text(f"UPDATE {table} SET {field}=:value, updated_at=updated_at WHERE id=:id"), updates)


def _upgrade_domains(connection):
    inspector = inspect(connection)
    changes = []
    conversions = []
    for name in DOMAIN_TABLES:
        table = Base.metadata.tables[name]
        columns = {column["name"]: column for column in inspector.get_columns(name)}
        present = {check["name"] for check in inspector.get_check_constraints(name)}
        candidates = table.constraints.union(*(column.constraints for column in table.columns))
        checks = sorted((check for check in candidates if isinstance(check, CheckConstraint) and check.name not in present),
                        key=lambda check: check.name)
        temporal_change = None
        if name in TEMPORAL_FIELDS:
            field, target, ddl, parse = TEMPORAL_FIELDS[name]
            actual = columns[field]["type"]
            if not isinstance(actual, target):
                conversions.append((table, field, parse))
                temporal_change = (field, ddl)
            elif target is DateTime and connection.dialect.name == "mysql" and actual.fsp != 6:
                temporal_change = (field, ddl)
        publication_change = name == "catalog_episodes" and columns["publication_status"]["nullable"]
        if checks or temporal_change or publication_change:
            changes.append((table, checks, temporal_change, publication_change))
    _normalize_legacy_dates(connection, conversions)
    for table, checks, temporal_change, publication_change in changes:
        if table.name in {"catalog_seasons", "catalog_episodes"}:
            aliases = "HEX('standard'), HEX('episode')" if table.name == "catalog_episodes" else "HEX('standard')"
            connection.exec_driver_sql(f"UPDATE {table.name} SET kind='regular', updated_at=updated_at WHERE HEX(kind) IN ({aliases})")
        if connection.dialect.name == "sqlite":
            _rebuild_sqlite_table(connection, table, inspector)
            continue
        if temporal_change:
            field, ddl = temporal_change
            connection.exec_driver_sql(f"ALTER TABLE {table.name} MODIFY COLUMN {field} {ddl} NULL")
        if publication_change:
            connection.exec_driver_sql("ALTER TABLE catalog_episodes MODIFY COLUMN publication_status VARCHAR(16) NOT NULL DEFAULT 'draft'")
        for check in checks:
            connection.exec_driver_sql(f"ALTER TABLE {table.name} ADD CONSTRAINT {check.name} CHECK ({check.sqltext})")
    return bool(changes)


def _upgrade_segments(connection):
    inspector = inspect(connection)
    table = CatalogSegment.__table__
    expected = {index.name: index for index in table.indexes}
    key_name = "uq_cat_segment_position"
    if key_name not in {index["name"] for index in inspector.get_indexes(table.name)}:
        duplicate = connection.exec_driver_sql(
            "SELECT episode_id, position FROM catalog_segments "
            "GROUP BY episode_id, position HAVING COUNT(*) > 1 LIMIT 1"
        ).first()
        if duplicate is not None:
            logging.getLogger(__name__).error(
                "Tập %s có nhiều phân đoạn ở vị trí %s.", duplicate.episode_id, duplicate.position,
            )
            raise ValueError("Còn phân đoạn trùng vị trí.")
        expected[key_name].create(connection)
    checks = {check["name"] for check in inspector.get_check_constraints(table.name)}
    range_check = "ck_cat_segment_time_range"
    if connection.dialect.name == "mysql":
        if range_check not in checks:
            condition = SEGMENT_TIME_RANGE.format(row="")
            connection.exec_driver_sql(f"ALTER TABLE {table.name} ADD CONSTRAINT {range_check} CHECK ({condition})")
    elif connection.dialect.name == "sqlite":
        existing_triggers = set(connection.exec_driver_sql(
            "SELECT name FROM sqlite_master WHERE type = 'trigger' AND tbl_name = 'catalog_segments'"
        ).scalars())
        for name, expression in ((range_check, SEGMENT_TIME_RANGE), ("ck_cat_segment_integer_types", SEGMENT_SQLITE_TYPES)):
            if name not in checks:
                _guard_existing_sqlite_segments(connection, table.name, name, expression, existing_triggers)


def _guard_existing_sqlite_segments(connection, table, name, expression, existing_triggers):
    operations = {"insert": "INSERT", "update": "UPDATE OF position, episode_start_ms, episode_end_ms"}
    if all(f"{name}_{action}" in existing_triggers for action in operations):
        return
    condition = expression.format(row="")
    invalid = connection.exec_driver_sql(f"SELECT id FROM {table} WHERE NOT {condition} LIMIT 1").scalar()
    if invalid is not None:
        logging.getLogger(__name__).error("Dữ liệu phân đoạn %s không thỏa ràng buộc %s.", invalid, name)
        raise ValueError(f"Dữ liệu phân đoạn đang lưu không hợp lệ: {invalid}")
    new_condition = expression.format(row="NEW.")
    for action, operation in operations.items():
        connection.exec_driver_sql(
            f"CREATE TRIGGER IF NOT EXISTS {name}_{action} BEFORE {operation} ON {table} "
            f"WHEN NOT {new_condition} BEGIN SELECT RAISE(ABORT, '{name}'); END"
        )


def _legacy_reference_ids(value):
    try:
        values = json.loads(value or "[]")
    except (TypeError, ValueError):
        return []
    if not isinstance(values, list):
        return []
    return [item for item in values if isinstance(item, str) and item]


def _upgrade_episodes(connection):
    table = CatalogEpisode.__table__
    inspector = inspect(connection)
    if "publication_status" not in {column["name"] for column in inspector.get_columns(table.name)}:
        connection.exec_driver_sql("ALTER TABLE catalog_episodes ADD COLUMN publication_status VARCHAR(16)")
    if "idx_cat_ep_publication" not in {index["name"] for index in inspector.get_indexes(table.name)}:
        next(index for index in table.indexes if index.name == "idx_cat_ep_publication").create(connection)

    pending = select(table.c.id, table.c.record_json, table.c.character_ids_json, table.c.genre_ids_json).where(
        table.c.publication_status.is_(None)
    ).order_by(table.c.id).limit(500)
    batch = connection.execute(pending).all()
    if not batch:
        return
    available_characters = set(connection.execute(select(CatalogCharacter.id)).scalars())
    available_genres = set(connection.execute(select(CatalogGenre.id)).scalars())
    missing = 0
    while batch:
        episodes = []
        for row in batch:
            characters = _legacy_reference_ids(row.character_ids_json)
            genres = _legacy_reference_ids(row.genre_ids_json)
            episode = {
                "id": row.id,
                "character_ids": [item for item in characters if item in available_characters],
                "genre_ids": [item for item in genres if item in available_genres],
            }
            missing += len(characters) + len(genres) - len(episode["character_ids"]) - len(episode["genre_ids"])
            episodes.append(episode)
        _replace_episode_taxonomy(connection, episodes)
        connection.execute(
            text("UPDATE catalog_episodes SET publication_status=:status, updated_at=updated_at WHERE id=:episode"),
            [{"episode": row.id, "status": catalog_publication_status(row.record_json)} for row in batch],
        )
        batch = connection.execute(pending).all()
    if missing:
        logging.getLogger(__name__).warning(
            "Không tạo liên kết cho %d mã nhân vật/thể loại cũ thiếu bản ghi tham chiếu.", missing,
        )


def _upgrade_text_tracks(connection):
    table = CatalogTextTrack.__table__
    inspector = inspect(connection)
    columns = {column["name"]: column for column in inspector.get_columns(table.name)}
    if connection.dialect.name == "sqlite":
        if "episode_id" in columns:
            return
        _rebuild_sqlite_table(connection, table, inspector)
        return True

    for field in ("episode_id", "source_id"):
        if field not in columns:
            connection.exec_driver_sql(f"ALTER TABLE {table.name} ADD COLUMN {field} VARCHAR(100)")
    if not columns["media_asset_id"]["nullable"]:
        connection.exec_driver_sql(f"ALTER TABLE {table.name} MODIFY media_asset_id VARCHAR(100) NULL")
    indexes = {index["name"] for index in inspector.get_indexes(table.name)}
    for index in table.indexes:
        if index.name not in indexes:
            index.create(connection)
    constraints = {key["name"] for key in inspector.get_foreign_keys(table.name)}
    constraints.update(check["name"] for check in inspector.get_check_constraints(table.name))
    new_constraints = {"fk_cat_track_episode", "fk_cat_track_source", "ck_cat_text_track_origin"}
    for constraint in table.constraints:
        if constraint.name in new_constraints - constraints:
            connection.execute(AddConstraint(constraint))
