from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError

from main import create_app
from services import database


@pytest.mark.parametrize("content_type", ["audio", [], {}])
def test_restart_repairs_imported_media_metadata_without_reimport(tmp_path, content_type):
    import json

    url = f"sqlite:///{(tmp_path / 'catalog.db').as_posix()}"
    manager = database.DatabaseManager(database_url=url, seed=False)
    with manager.session() as db:
        db.add(database.Movie(id="old-movie", title="Tập cũ", release_year=2026, rating=0, genres="Animation"))
        db.flush()
        db.add(database.CatalogMediaAsset(id="old-audio", content_type="video", role="dub",
               storage_provider="local", storage_key="main", relative_path="old.mp3",
               raw_json=json.dumps({"content_type": content_type})))
        db.add(database.MediaAsset(id="old-audio", movie_id="old-movie", kind="dub", storage_provider="local",
               storage_key="main", relative_path="old.mp3", mime_type="video/mp4"))
        db.commit()
    manager.engine.dispose()
    restored = database.DatabaseManager(database_url=url, seed=False)
    try:
        with restored.session() as db:
            assert db.get(database.CatalogMediaAsset, "old-audio").content_type == ("audio" if content_type == "audio" else "video")
            assert db.get(database.MediaAsset, "old-audio").mime_type == ("audio/mpeg" if content_type == "audio" else "video/mp4")
            assert db.get(database.Movie, "old-movie").title == "Tập cũ"
    finally:
        if restored.engine is not None:
            restored.engine.dispose()


def test_restart_backfills_and_repairs_links_from_existing_coverage(tmp_path):
    url = f"sqlite:///{(tmp_path / 'catalog.db').as_posix()}"
    manager = database.DatabaseManager(database_url=url, seed=False)
    with manager.session() as db:
        database.import_catalog_package(db, {
            "package": {"id": "legacy-catalog"},
            "series": [{"id": "legacy-series"}],
            "episodes": [{"id": item, "series_id": "legacy-series"} for item in ("ep-first", "ep-second")],
            "media_assets": [{"id": "old-asset", "coverage": [{"episode_id": "ep-first"}]}],
        })
        db.execute(text("DROP TABLE IF EXISTS catalog_episode_assets"))
        db.commit()
    manager.engine.dispose()

    restored = database.DatabaseManager(database_url=url, seed=False)
    with restored.session() as db:
        links = text("SELECT episode_id, media_asset_id FROM catalog_episode_assets")
        assert db.execute(links).all() == [("ep-first", "old-asset")]
        db.get(database.CatalogMediaAsset, "old-asset").coverage_json = (
            '[{"episode_id":"ep-second"},{"episode_id":"missing-legacy"}]'
        )
        db.commit()
    restored.engine.dispose()

    for _ in range(2):
        reloaded = database.DatabaseManager(database_url=url, seed=False)
        with reloaded.session() as db:
            assert db.execute(links).all() == [("ep-second", "old-asset")]
            assert '"missing-legacy"' in db.get(database.CatalogMediaAsset, "old-asset").coverage_json
        reloaded.engine.dispose()


def test_explicit_sqlite_creates_its_data_directory(tmp_path):
    path = tmp_path / "data" / "catalog.db"
    application = create_app(database_url=f"sqlite:///{path.as_posix()}", load_default=False)
    with TestClient(application) as client:
        assert client.get("/api/health").status_code == 200
    assert path.is_file()


def test_configured_mysql_failure_stops_startup_in_demo_mode(tmp_path, monkeypatch):
    create_engine = database.create_engine

    def connect(url, **options):
        if make_url(url).get_backend_name() == "mysql":
            raise OperationalError(None, None, ConnectionError("Database unavailable"))
        return create_engine(url, **options)

    monkeypatch.setattr(database, "create_engine", connect)
    fallback = tmp_path / "fallback.db"
    monkeypatch.setenv("PYTHON_MAIN_SQLITE_FALLBACK", str(fallback))
    application = create_app(database_url="mysql+pymysql://local@127.0.0.1/catalog", load_default=False)
    with pytest.raises(RuntimeError, match="cơ sở dữ liệu"):
        with TestClient(application):
            pass
    assert not fallback.exists()


def test_mysql_environment_preserves_reserved_characters(monkeypatch):
    monkeypatch.delenv("DATABASE_URL")
    monkeypatch.setenv("MYSQL_USER", "catalog")
    monkeypatch.setenv("MYSQL_PASSWORD", "local@key:#/?")
    monkeypatch.setenv("MYSQL_HOST", "127.0.0.1")
    monkeypatch.setenv("MYSQL_PORT", "18306")
    url = make_url(database.resolve_database_url())
    assert (url.username, url.password, url.host, url.port) == ("catalog", "local@key:#/?", "127.0.0.1", 18306)


def test_business_health_reflects_database_outage(monkeypatch):
    application = create_app(load_default=False)
    with TestClient(application) as client:
        assert client.get("/api/health").status_code == 200

        @contextmanager
        def offline():
            raise OperationalError(None, None, ConnectionError("Database unavailable"))
            yield

        monkeypatch.setattr(application.state.runtime.db, "session", offline)
        assert client.get("/api/health").status_code == 503
        assert client.get("/ready").json()["database"] == "unavailable"
        assert client.get("/health").status_code == 200
