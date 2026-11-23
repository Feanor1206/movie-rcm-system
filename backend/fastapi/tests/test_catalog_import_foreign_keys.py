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
    CatalogInputError,
    CatalogMediaAsset,
    CatalogSeason,
    CatalogSegment,
    CatalogSeries,
    CatalogTextTrack,
    MediaAsset,
    Movie,
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
    data["media_assets"].append(standalone)
    first = import_catalog_package(catalog_db, data)
    assert first["success"]
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
        if "FROM catalog_episodes" in statement:
            statements.append(statement)

    event.listen(catalog_db.bind, "before_cursor_execute", capture)
    try:
        visible = export_eligible_catalog(catalog_db)
        assert {row["id"] for row in visible["episodes"]} == {"verified", "legacy"}
        assert len(statements) == 1
        assert "WHERE" in statements[0]
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
