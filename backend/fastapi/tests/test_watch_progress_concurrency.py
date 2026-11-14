import json
from pathlib import Path
import sys

from fastapi.testclient import TestClient
import pytest
from sqlalchemy import event, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "backend" / "fastapi"))
sys.path.insert(0, str(ROOT))

from main import create_app
from services.database import (
    CatalogEpisode,
    CatalogMediaAsset,
    CatalogSeries,
    MediaAsset,
    User,
    WatchProgress,
    create_jwt_token,
)


@pytest.fixture
def progress_app(tmp_path):
    app = create_app(
        sync_secret="test-secret",
        sync_path=tmp_path / "sync.json",
        cache_dir=tmp_path / "cache",
        model_mode="light",
        load_default=False,
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
    )
    with TestClient(app) as client:
        with app.state.runtime.db.session() as db:
            user = User(
                username="watcher", email="watcher@example.com", password="unused"
            )
            db.add(user)
            db.add(
                CatalogSeries(
                    id="series", title="Series", record_json='{"status":"ready"}'
                )
            )
            db.flush()
            db.add(
                CatalogEpisode(
                    id="episode",
                    series_id="series",
                    title="Episode",
                    kind="standard",
                    record_json='{"status":"ready"}',
                )
            )
            db.add(
                CatalogMediaAsset(
                    id="asset",
                    content_type="video",
                    role="feature",
                    storage_provider="local",
                    storage_key="local",
                    relative_path="test.mp4",
                    coverage_json=json.dumps(
                        [{"episode_id": "episode", "scope": "full_episode"}]
                    ),
                    record_json='{"status":"ready"}',
                )
            )
            db.add(
                MediaAsset(
                    id="asset",
                    movie_id="the-last-orbit",
                    kind="test",
                    relative_path="test.mp4",
                    mime_type="video/mp4",
                    is_available=True,
                )
            )
            db.commit()
            user_id = user.id
        yield app, client, user_id


def test_independent_sessions_reject_stale_update(progress_app):
    app, _, user_id = progress_app
    factory = app.state.runtime.db.session
    with factory() as db:
        progress = WatchProgress(
            user_id=user_id,
            episode_id="episode",
            asset_id="asset",
            position_ms=0,
            opt_lock_version=0,
        )
        db.add(progress)
        db.commit()
        row_id = progress.id
    with factory() as first, factory() as second:
        a = first.get(WatchProgress, row_id)
        b = second.get(WatchProgress, row_id)
        a.position_ms = 1
        a.opt_lock_version = 1
        first.commit()
        b.position_ms = 2
        b.opt_lock_version = 1
        with pytest.raises(StaleDataError):
            second.commit()


@pytest.mark.parametrize("create", [True, False])
def test_http_conflict_when_another_writer_commits_before_flush(progress_app, create):
    app, client, user_id = progress_app
    factory = app.state.runtime.db.session
    if not create:
        with factory() as db:
            db.add(
                WatchProgress(
                    user_id=user_id,
                    episode_id="episode",
                    asset_id="asset",
                    position_ms=0,
                    opt_lock_version=0,
                )
            )
            db.commit()
    interleaved = False

    def concurrent_write(session, flush_context, instances):
        nonlocal interleaved
        if interleaved or not any(
            isinstance(row, WatchProgress) for row in session.new.union(session.dirty)
        ):
            return
        interleaved = True
        with factory() as db:
            if create:
                db.add(
                    WatchProgress(
                        user_id=user_id,
                        episode_id="episode",
                        asset_id="asset",
                        position_ms=5,
                        opt_lock_version=0,
                    )
                )
            else:
                row = (
                    db.query(WatchProgress)
                    .filter_by(user_id=user_id, episode_id="episode")
                    .one()
                )
                row.position_ms = 5
                row.opt_lock_version = 1
            db.commit()

    event.listen(Session, "before_flush", concurrent_write)
    try:
        response = client.put(
            "/api/users/watch-progress/episode",
            json={
                "assetId": "asset",
                "positionMs": 10,
                "expectedVersion": -1 if create else 0,
            },
            headers={"Authorization": f"Bearer {create_jwt_token('watcher')}"},
        )
    finally:
        event.remove(Session, "before_flush", concurrent_write)
    assert interleaved
    assert response.status_code == 409
    assert (
        response.json()["message"]
        == "Watch progress changed since it was loaded; refresh and retry."
    )
    with factory() as db:
        row = (
            db.query(WatchProgress)
            .filter_by(user_id=user_id, episode_id="episode")
            .one()
        )
        assert row.position_ms == 5
        assert row.opt_lock_version == (0 if create else 1)


def test_same_position_increments_and_response_does_not_refresh_later_write(
    progress_app,
):
    app, client, user_id = progress_app
    factory = app.state.runtime.db.session
    headers = {"Authorization": f"Bearer {create_jwt_token('watcher')}"}
    payload = {"assetId": "asset", "positionMs": 10, "expectedVersion": -1}
    created = client.put(
        "/api/users/watch-progress/episode", json=payload, headers=headers
    )
    assert created.status_code == 200
    assert created.json()["data"]["version"] == 0
    interleaved = False

    def after_commit(session):
        nonlocal interleaved
        if interleaved:
            return
        interleaved = True
        with factory() as db:
            row = (
                db.query(WatchProgress)
                .filter_by(user_id=user_id, episode_id="episode")
                .one()
            )
            row.position_ms = 20
            db.commit()

    event.listen(Session, "after_commit", after_commit)
    try:
        response = client.put(
            "/api/users/watch-progress/episode",
            json={**payload, "expectedVersion": 0},
            headers=headers,
        )
    finally:
        event.remove(Session, "after_commit", after_commit)
    assert response.status_code == 200
    assert response.json()["data"]["positionMs"] == 10
    assert response.json()["data"]["version"] == 1
    with factory() as db:
        row = (
            db.query(WatchProgress)
            .filter_by(user_id=user_id, episode_id="episode")
            .one()
        )
        assert row.position_ms == 20
        assert row.opt_lock_version == 2


def test_unrelated_integrity_error_is_not_reported_as_conflict(progress_app):
    _, client, _ = progress_app

    def fail_flush(session, flush_context, instances):
        if any(isinstance(row, WatchProgress) for row in session.new):
            raise IntegrityError(
                "INSERT", {}, Exception("unrelated constraint failure")
            )

    event.listen(Session, "before_flush", fail_flush)
    try:
        with pytest.raises(IntegrityError, match="unrelated constraint failure"):
            client.put(
                "/api/users/watch-progress/episode",
                json={"assetId": "asset", "positionMs": 10, "expectedVersion": -1},
                headers={"Authorization": f"Bearer {create_jwt_token('watcher')}"},
            )
    finally:
        event.remove(Session, "before_flush", fail_flush)


def test_response_uses_database_timestamp_before_commit(progress_app):
    _, client, _ = progress_app
    applied = False

    def set_database_timestamp(session, flush_context):
        nonlocal applied
        if applied:
            return
        applied = True
        session.execute(
            text(
                "UPDATE watch_progress SET updated_at = '2024-01-01 12:00:00' WHERE episode_id = 'episode'"
            )
        )

    event.listen(Session, "after_flush_postexec", set_database_timestamp)
    headers = {"Authorization": f"Bearer {create_jwt_token('watcher')}"}
    try:
        response = client.put(
            "/api/users/watch-progress/episode",
            json={"assetId": "asset", "positionMs": 10, "expectedVersion": -1},
            headers=headers,
        )
    finally:
        event.remove(Session, "after_flush_postexec", set_database_timestamp)
    saved = client.get("/api/users/watch-progress/episode", headers=headers)
    assert applied
    assert response.status_code == 200
    assert saved.status_code == 200
    assert (
        response.json()["data"]["updatedAt"]
        == saved.json()["data"]["updatedAt"]
        == "2024-01-01T12:00:00"
    )
