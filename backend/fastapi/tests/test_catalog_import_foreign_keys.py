import copy
import json
from pathlib import Path
import sys

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "backend" / "fastapi"))
sys.path.insert(0, str(ROOT))

from services.database import (
    Base,
    CatalogEpisode,
    CatalogCharacterSeries,
    CatalogInputError,
    CatalogMediaAsset,
    CatalogSeason,
    CatalogSegment,
    CatalogSeries,
    CatalogSeriesCharacter,
    CatalogSeriesGenre,
    CatalogSource,
    CatalogTextTrack,
    DatabaseManager,
    MediaAsset,
    Movie,
    MovieGenre,
    export_eligible_catalog,
    import_catalog_package,
)


@pytest.fixture
def catalog_db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'catalog.db'}")

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, record):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with factory() as db:
        yield db
    engine.dispose()


def test_rehearsal_catalog_import_respects_foreign_keys_and_is_repeatable(catalog_db):
    data = json.loads(
        (ROOT / "docs/fixtures/rehearsal_catalog.json").read_text(encoding="utf-8")
    )
    standalone = copy.deepcopy(data["media_assets"][0])
    standalone["id"] = "standalone-asset"
    standalone["coverage"] = []
    standalone["related_asset_id"] = data["media_assets"][0]["id"]
    data["media_assets"].append(standalone)
    first = import_catalog_package(catalog_db, data)
    assert first["success"]
    assert catalog_db.get(CatalogMediaAsset, standalone["id"]).related_asset_id == standalone["related_asset_id"]
    for item in data["series"]:
        assert catalog_db.query(CatalogSeriesGenre).filter_by(series_id=item["id"]).count() == len(set(item["genre_ids"]))
        assert catalog_db.query(CatalogSeriesCharacter).filter_by(series_id=item["id"]).count() == len(set(item["character_ids"]))
        assert catalog_db.get(MovieGenre, (item["id"], "animation")) is not None
    for item in data["characters"]:
        assert catalog_db.query(CatalogCharacterSeries).filter_by(character_id=item["id"]).count() == len(set(item["series_ids"]))
    for item in data["seasons"]:
        assert catalog_db.get(
            CatalogSeries, catalog_db.get(CatalogSeason, item["id"]).series_id
        )
    for item in data["episodes"]:
        assert catalog_db.get(
            CatalogSeries, catalog_db.get(CatalogEpisode, item["id"]).series_id
        )
    for item in data["segments"]:
        assert catalog_db.get(
            CatalogEpisode, catalog_db.get(CatalogSegment, item["id"]).episode_id
        )
    for item in data["text_tracks"]:
        assert catalog_db.get(
            CatalogMediaAsset,
            catalog_db.get(CatalogTextTrack, item["id"]).media_asset_id,
        )
    for item in data["media_assets"]:
        assert catalog_db.get(Movie, catalog_db.get(MediaAsset, item["id"]).movie_id)
    assert not catalog_db.execute(text("PRAGMA foreign_key_check")).all()
    exported = export_eligible_catalog(
        catalog_db, include_draft=True, include_private=True
    )
    assert {item["id"] for item in exported["episodes"]} == {
        item["id"] for item in data["episodes"]
    }
    second = import_catalog_package(catalog_db, data)
    assert second["counts"] == first["counts"]
    assert catalog_db.query(CatalogEpisode).count() == len(data["episodes"])


def test_serving_export_prefilters_episode_rows_without_loading_orm_entities(catalog_db):
    catalog_db.add(CatalogSeries(id="series", title="Series"))
    catalog_db.flush()
    statuses = {
        "verified": '{"status":"READY"}',
        "draft": '{"status":"draft"}',
        "draft-mention": '{"status":"draft","note":"ready later"}',
        "legacy": '{"status":"draft","status":"ready"}',
        "malformed": 'ready but invalid JSON',
        "absent": None,
    }
    for episode_id, record in statuses.items():
        catalog_db.add(CatalogEpisode(id=episode_id, series_id="series", title=episode_id, kind="regular",
                                      record_json=record, raw_json=json.dumps({"id": episode_id})))
    catalog_db.commit()
    catalog_db.expunge_all()
    statements = []

    def capture(_connection, _cursor, statement, _params, _context, _many):
        if "FROM catalog_episodes" in statement and statement.startswith("SELECT catalog_episodes."):
            statements.append(statement)

    event.listen(catalog_db.bind, "before_cursor_execute", capture)
    try:
        visible = export_eligible_catalog(catalog_db)
        assert {row["id"] for row in visible["episodes"]} == {"verified", "legacy"}
        assert len(statements) == 1
        assert "WHERE" in statements[0]
        assert "catalog_episodes.publication_status" in statements[0]
        assert "LIKE" not in statements[0]
        assert "catalog_episodes.raw_json" in statements[0]
        assert "catalog_episodes.title" not in statements[0]
        administrative = export_eligible_catalog(catalog_db, include_draft=True)
        assert {row["id"] for row in administrative["episodes"]} == set(statuses)
    finally:
        event.remove(catalog_db.bind, "before_cursor_execute", capture)


@pytest.mark.parametrize("bad_kind, error_type", [("episode", CatalogInputError), ("track", IntegrityError)])
def test_import_failure_rolls_back_parent_and_child_rows(catalog_db, bad_kind, error_type):
    data = json.loads(
        (ROOT / "docs/fixtures/rehearsal_catalog.json").read_text(encoding="utf-8")
    )
    data = copy.deepcopy(data)
    if bad_kind == "episode":
        data["episodes"][0]["series_id"] = "missing-series"
    else:
        data["text_tracks"][0]["media_asset_id"] = "missing-asset"
    with pytest.raises(error_type):
        import_catalog_package(catalog_db, data)
    catalog_db.rollback()
    assert catalog_db.query(CatalogSeries).count() == 0
    assert catalog_db.query(CatalogEpisode).count() == 0


@pytest.mark.parametrize("invalid", [
    {"position": 1},
    {"episode_start_ms": -1},
    {"episode_end_ms": None},
    {"episode_end_ms": 0},
    {"episode_end_ms": "invalid"},
    {"episode_end_ms": 1.5},
])
def test_segment_constraints_apply_to_direct_database_writes(catalog_db, invalid):
    data = json.loads((ROOT / "docs/fixtures/rehearsal_catalog.json").read_text(encoding="utf-8"))
    import_catalog_package(catalog_db, data)
    values = {
        "id": "invalid-segment",
        "episode_id": data["segments"][0]["episode_id"],
        "position": 2,
        "title": "Invalid segment",
        "episode_start_ms": 0,
        "episode_end_ms": 2000,
    }
    values.update(invalid)
    catalog_db.add(CatalogSegment(**values))
    with pytest.raises(IntegrityError):
        catalog_db.flush()
    catalog_db.rollback()
    assert catalog_db.query(CatalogSegment).count() == 1


def test_package_updates_can_swap_segment_positions(catalog_db):
    data = json.loads((ROOT / "docs/fixtures/rehearsal_catalog.json").read_text(encoding="utf-8"))
    first = data["segments"][0]
    second = copy.deepcopy(first)
    second.update(id="second-segment", position=2)
    data["segments"].append(second)
    import_catalog_package(catalog_db, data)
    data["package"]["revision"] += 1
    for segment, position in [(first, 2), (second, 1)]:
        segment["position"] = position
        segment["record"]["revision"] += 1
    import_catalog_package(catalog_db, data)
    assert catalog_db.get(CatalogSegment, first["id"]).position == 2
    assert catalog_db.get(CatalogSegment, second["id"]).position == 1


def test_package_can_move_legacy_negative_position_without_a_collision(catalog_db):
    data = json.loads((ROOT / "docs/fixtures/rehearsal_catalog.json").read_text(encoding="utf-8"))
    legacy = data["segments"][0]
    occupying = copy.deepcopy(legacy)
    occupying.update(id="occupying-segment", position=2)
    data["segments"].append(occupying)
    import_catalog_package(catalog_db, data)
    catalog_db.get(CatalogSegment, legacy["id"]).position = -1
    catalog_db.flush()
    catalog_db.get(CatalogSegment, occupying["id"]).position = 1
    catalog_db.commit()
    data["package"]["revision"] += 1
    for segment, position in [(legacy, 2), (occupying, 1)]:
        segment["position"] = position
        segment["record"]["revision"] += 1
    import_catalog_package(catalog_db, data)
    assert catalog_db.get(CatalogSegment, legacy["id"]).position == 2
    assert catalog_db.get(CatalogSegment, occupying["id"]).position == 1


def test_episode_relationships_and_publication_follow_package_updates(catalog_db):
    data = json.loads((ROOT / "docs/fixtures/rehearsal_catalog.json").read_text(encoding="utf-8"))
    episode = data["episodes"][0]
    import_catalog_package(catalog_db, data)
    genre_rows = text("SELECT genre_id FROM catalog_episode_genres WHERE episode_id = :episode")
    character_rows = text("SELECT character_id FROM catalog_episode_characters WHERE episode_id = :episode")
    parameters = {"episode": episode["id"]}
    assert set(catalog_db.execute(genre_rows, parameters).scalars()) == set(episode["genre_ids"])
    assert set(catalog_db.execute(character_rows, parameters).scalars()) == set(episode["character_ids"])
    data["package"]["revision"] += 1
    episode["record"].update(status="draft", revision=episode["record"]["revision"] + 1)
    episode["genre_ids"] = episode["genre_ids"][:1]
    episode["character_ids"] = []
    import_catalog_package(catalog_db, data)
    assert list(catalog_db.execute(genre_rows, parameters).scalars()) == episode["genre_ids"]
    assert list(catalog_db.execute(character_rows, parameters).scalars()) == []
    assert episode["id"] not in {row["id"] for row in export_eligible_catalog(catalog_db)["episodes"]}


def test_existing_database_backfills_publication_and_relationships(tmp_path):
    url = f"sqlite:///{tmp_path / 'previous.db'}"
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    data = json.loads((ROOT / "docs/fixtures/rehearsal_catalog.json").read_text(encoding="utf-8"))
    with factory() as db:
        import_catalog_package(db, data)
    with engine.begin() as connection:
        connection.exec_driver_sql("DROP TABLE catalog_episode_characters")
        connection.exec_driver_sql("DROP TABLE catalog_episode_genres")
        connection.exec_driver_sql("DROP INDEX idx_cat_ep_publication")
        connection.exec_driver_sql("DROP INDEX idx_cat_ep_status_series_duration")
        connection.exec_driver_sql("ALTER TABLE catalog_episodes DROP COLUMN publication_status")
        connection.execute(text(
            "UPDATE catalog_episodes SET record_json=:record WHERE id=:episode"
        ), {"record": '{"status":"draft","status":"READY"}', "episode": data["episodes"][0]["id"]})
    engine.dispose()
    manager = DatabaseManager(url, seed=False)
    try:
        with manager.session() as db:
            episode = db.get(CatalogEpisode, data["episodes"][0]["id"])
            assert episode.publication_status == "ready"
            assert db.execute(text(
                "SELECT count(*) FROM catalog_episode_characters WHERE episode_id=:episode"
            ), {"episode": episode.id}).scalar_one() == len(data["episodes"][0]["character_ids"])
            assert episode.id in {row["id"] for row in export_eligible_catalog(db)["episodes"]}
    finally:
        if manager.engine:
            manager.engine.dispose()


def test_catalog_temporal_fields_keep_an_iso_date_and_store_the_source_in_utc(catalog_db):
    data = json.loads((ROOT / "docs/fixtures/rehearsal_catalog.json").read_text(encoding="utf-8"))
    data["episodes"][0]["release_date"] = "2024-02-29"
    data["seasons"][0]["release_date"] = "2024-02-01"
    data["sources"][0]["retrieved_at"] = "2026-11-24T01:02:03.123456+07:00"
    import_catalog_package(catalog_db, data)
    episode = catalog_db.get(CatalogEpisode, data["episodes"][0]["id"])
    season = catalog_db.get(CatalogSeason, data["seasons"][0]["id"])
    source = catalog_db.get(CatalogSource, data["sources"][0]["id"])
    assert episode.to_dict()["releaseDate"] == "2024-02-29"
    assert season.to_dict()["releaseDate"] == "2024-02-01"
    assert source.retrieved_at.isoformat() == "2026-11-23T18:02:03.123456"


def test_remote_text_track_links_the_episode_and_exact_source(catalog_db):
    data = json.loads((ROOT / "docs/fixtures/rehearsal_catalog.json").read_text(encoding="utf-8"))
    remote = copy.deepcopy(data["text_tracks"][0])
    remote.update(
        id="external-caption",
        media_asset_id=None,
        episode_id=data["episodes"][0]["id"],
        source_id=data["sources"][0]["id"],
    )
    data["text_tracks"].append(remote)
    import_catalog_package(catalog_db, data)
    record = catalog_db.get(CatalogTextTrack, "external-caption")
    assert record.media_asset_id is None
    assert record.episode_id == remote["episode_id"]
    assert record.source_id == remote["source_id"]
    assert {track["id"] for track in export_eligible_catalog(catalog_db)["text_tracks"]} >= {remote["id"]}

    with catalog_db.begin_nested():
        catalog_db.execute(text("UPDATE catalog_sources SET record_json=:record WHERE id=:source"),
                           {"record": '{"status":"archived"}', "source": remote["source_id"]})
        assert remote["id"] not in {track["id"] for track in export_eligible_catalog(catalog_db)["text_tracks"]}
        assert remote["id"] in {
            track["id"] for track in export_eligible_catalog(catalog_db, include_draft=True)["text_tracks"]
        }


@pytest.mark.parametrize("bad_field,bad_value", [("relative_path", "../private.json"), ("sha256", "not-a-hash")])
def test_catalog_rejects_invalid_transcript_file_reference(catalog_db, bad_field, bad_value):
    data = json.loads((ROOT / "docs/fixtures/rehearsal_catalog.json").read_text(encoding="utf-8"))
    track = data["text_tracks"][0]
    track["format"] = "json"
    track["external_file"] = {
        "storage_key": "caption_evidence", "relative_path": "captions/episode.json", "sha256": "a" * 64,
    }
    track["external_file"][bad_field] = bad_value
    with pytest.raises(CatalogInputError):
        import_catalog_package(catalog_db, data)
