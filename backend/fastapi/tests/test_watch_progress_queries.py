from datetime import datetime, timedelta
import json
from pathlib import Path
import sys

from fastapi.testclient import TestClient
from sqlalchemy import event

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "backend" / "fastapi"))
sys.path.insert(0, str(ROOT))

from main import create_app
from services.database import (
    CatalogEpisode,
    CatalogMediaAsset,
    CatalogSeason,
    CatalogSeries,
    MediaAsset,
    User,
    WatchProgress,
    create_jwt_token,
)


def test_recent_progress_keeps_cap_and_eligibility_with_bounded_queries(tmp_path):
    app = create_app(
        sync_secret="test-secret",
        sync_path=tmp_path / "sync.json",
        cache_dir=tmp_path / "cache",
        model_mode="light",
        load_default=False,
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
    )
    with TestClient(app) as client:
        db_service = app.state.runtime.db
        with db_service.session() as db:
            user = User(
                username="progress_user",
                email="progress@example.com",
                password="unused",
            )
            other = User(
                username="other_user", email="other@example.com", password="unused"
            )
            db.add_all([user, other])
            db.flush()
            db.add(
                CatalogSeries(id="s", title="Series", record_json='{"status":"ready"}')
            )
            db.add(
                CatalogSeason(
                    id="season",
                    series_id="s",
                    title="Season",
                    number=1,
                    record_json='{"status":"ready"}',
                )
            )
            db.flush()
            for i in range(32):
                ep_id = f"ep{i}"
                asset_id = f"asset{i}"
                db.add(
                    CatalogEpisode(
                        id=ep_id,
                        series_id="s",
                        season_id=(
                            None if i == 30 else "missing" if i == 25 else "season"
                        ),
                        title=f"Episode {i}",
                        number=i,
                        kind="standard",
                        record_json='{"status":"ready"}',
                    )
                )
                db.add(
                    CatalogMediaAsset(
                        id=asset_id,
                        content_type="video",
                        role="dub" if i == 31 else "feature",
                        storage_provider="local",
                        storage_key="local",
                        relative_path="test.mp4",
                        access_policy="private" if i == 27 else "public",
                        coverage_json=json.dumps(
                            [
                                {
                                    "episode_id": ep_id,
                                    "scope": "partial" if i == 28 else "full_episode",
                                }
                            ]
                        ),
                        record_json='{"status":"ready"}',
                        duration_ms=100000,
                    )
                )
                if i != 26:
                    db.add(
                        MediaAsset(
                            id=asset_id,
                            movie_id="the-last-orbit",
                            kind=f"test{i}",
                            relative_path="test.mp4",
                            mime_type="video/mp4",
                            is_available=i != 29,
                        )
                    )
                db.add(
                    WatchProgress(
                        user_id=user.id,
                        episode_id=ep_id,
                        asset_id=asset_id,
                        position_ms=i * 1000,
                        updated_at=datetime(2024, 1, 1) + timedelta(minutes=i),
                    )
                )
            db.flush()
            db.add(
                WatchProgress(
                    user_id=other.id,
                    episode_id="ep0",
                    asset_id="asset0",
                    position_ms=0,
                    updated_at=datetime(2025, 1, 1),
                )
            )
            db.commit()
        statements = []

        def count_sql(conn, cursor, statement, parameters, context, executemany):
            statements.append(statement)

        event.listen(db_service.engine, "before_cursor_execute", count_sql)
        try:
            response = client.get(
                "/api/users/watch-progress",
                headers={
                    "Authorization": f"Bearer {create_jwt_token('progress_user')}"
                },
            )
        finally:
            event.remove(db_service.engine, "before_cursor_execute", count_sql)
        assert response.status_code == 200
        rows = response.json()["data"]
        assert [row["episodeId"] for row in rows] == [
            f"ep{i}" for i in range(30, 1, -1) if i not in {25, 26, 27, 28, 29}
        ]
        assert rows[0]["seasonId"] is None
        assert rows[0]["positionMs"] == 30000
        print(f"watch-progress SQL statements: {len(statements)}")
        assert len(statements) <= 3
        headers = {"Authorization": f"Bearer {create_jwt_token('progress_user')}"}
        for row in rows:
            single = client.get(
                f"/api/users/watch-progress/{row['episodeId']}", headers=headers
            )
            assert single.status_code == 200
            assert single.json()["data"] == row
        for i in (25, 26, 27, 28, 29, 31):
            single = client.get(f"/api/users/watch-progress/ep{i}", headers=headers)
            assert single.status_code == 404
