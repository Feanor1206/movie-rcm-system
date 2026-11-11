from pathlib import Path
import sys

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "backend" / "fastapi") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend" / "fastapi"))

from main import create_app


def test_python_main_auth_movies_and_user_library(tmp_path):
    db_file = tmp_path / "test_mysql_compat.db"
    app = create_app(
        sync_secret="test-secret",
        sync_path=tmp_path / "sync.json",
        cache_dir=tmp_path / "cache",
        model_mode="light",
        load_default=False,
        database_url=f"sqlite:///{db_file}",
    )
    with TestClient(app) as client:
        health = client.get("/api/health")
        assert health.status_code == 200
        assert health.json()["data"]["status"] == "UP"

        movies_res = client.get("/api/movies")
        assert movies_res.status_code == 200
        movies = movies_res.json()["data"]
        assert len(movies) >= 13
        assert movies[0]["id"] == "drive-videoplayback"

        browse_res = client.get("/api/movies/browse?q=Orbit&genre=Sci-Fi&page=0&size=5")
        assert browse_res.status_code == 200
        browse_data = browse_res.json()["data"]
        assert browse_data["totalElements"] == 1
        assert browse_data["items"][0]["id"] == "the-last-orbit"

        desc_res = client.get("/api/movies/the-last-orbit/media-descriptor")
        assert desc_res.status_code == 200
        assert desc_res.json()["data"]["hasFeature"] is True
        assert desc_res.json()["data"]["hasTrailer"] is True

        reg_res = client.post(
            "/api/auth/register",
            json={
                "username": "new_tester",
                "email": "tester@dippie.com",
                "password": "password123",
                "fullName": "Tester Dippie",
            },
        )
        assert reg_res.status_code == 201
        token = reg_res.json()["data"]["token"]
        headers = {"Authorization": f"Bearer {token}"}

        me_res = client.get("/api/auth/me", headers=headers)
        assert me_res.status_code == 200
        assert me_res.json()["data"]["username"] == "new_tester"

        wl_add = client.post("/api/users/watchlist", json={"movieId": "the-last-orbit"}, headers=headers)
        assert wl_add.status_code == 200
        wl_get = client.get("/api/users/watchlist", headers=headers)
        assert len(wl_get.json()["data"]) == 1
        assert wl_get.json()["data"][0]["movieId"] == "the-last-orbit"
        wl_del = client.delete("/api/users/watchlist/the-last-orbit", headers=headers)
        assert wl_del.status_code == 200
        assert client.get("/api/users/watchlist", headers=headers).json()["data"] == []

        fav_add = client.post("/api/users/favorites", json={"movieId": "spirited-away"}, headers=headers)
        assert fav_add.status_code == 200
        assert len(client.get("/api/users/favorites", headers=headers).json()["data"]) == 1
        client.delete("/api/users/favorites/spirited-away", headers=headers)
        assert client.get("/api/users/favorites", headers=headers).json()["data"] == []

        rate_add = client.post("/api/users/ratings", json={"movieId": "your-name", "rating": 9}, headers=headers)
        assert rate_add.status_code == 200
        assert rate_add.json()["data"]["rating"] == 9
        client.delete("/api/users/ratings/your-name", headers=headers)
        assert client.get("/api/users/ratings", headers=headers).json()["data"] == []


def test_python_main_catalog_import_search_and_watch_progress(tmp_path):
    db_file = tmp_path / "test_catalog.db"
    app = create_app(
        sync_secret="test-secret",
        sync_path=tmp_path / "sync.json",
        cache_dir=tmp_path / "cache",
        model_mode="light",
        load_default=False,
        database_url=f"sqlite:///{db_file}",
    )
    sample_package = {
        "package": {"id": "pkg_mysql_test", "version": "1.0.0", "revision": 1},
        "series": [
            {
                "id": "ser_shin",
                "title": "Shin Cậu Bé Bút Chì",
                "synopsis": "Phim hoạt hình gia đình vui nhộn",
                "release_year_start": 2024,
                "record": {"status": "ready", "revision": 1},
            }
        ],
        "seasons": [
            {
                "id": "sea_shin_1",
                "series_id": "ser_shin",
                "number": 1,
                "title": "Mùa 1",
                "record": {"status": "ready", "revision": 1},
            }
        ],
        "episodes": [
            {
                "id": "ep_shin_1",
                "series_id": "ser_shin",
                "season_id": "sea_shin_1",
                "number": 1,
                "title": "Tập 1: Đi siêu thị",
                "kind": "standard",
                "duration_ms": 600000,
                "synopsis": "Shin cùng mẹ đi mua sắm ở siêu thị",
                "record": {"status": "ready", "revision": 1},
            }
        ],
        "media_assets": [
            {
                "id": "ast_shin_1",
                "role": "feature",
                "duration_ms": 600000,
                "size_bytes": 1024000,
                "access_policy": "public",
                "enabled": True,
                "storage": {"provider": "local", "storage_key": "local_main", "relative_path": "synthetic/feature_test.mp4"},
                "coverage": [{"episode_id": "ep_shin_1", "scope": "full_episode"}],
                "record": {"status": "ready", "revision": 1},
            }
        ],
    }

    with TestClient(app) as client:
        admin_login = client.post("/api/auth/login", json={"username": "admin", "password": "password123"})
        assert admin_login.status_code == 200
        admin_token = admin_login.json()["data"]["token"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        imp_res = client.post("/api/admin/catalog/import", json=sample_package, headers=admin_headers)
        assert imp_res.status_code == 200
        assert imp_res.json()["data"]["success"] is True

        series_res = client.get("/api/catalog/series/ser_shin")
        assert series_res.status_code == 200
        assert len(series_res.json()["data"]["episodes"]) == 1

        ep_res = client.get("/api/catalog/episodes/ep_shin_1")
        assert ep_res.status_code == 200
        assert ep_res.json()["data"]["episode"]["title"] == "Tập 1: Đi siêu thị"

        search_res = client.get("/api/catalog/search?q=siêu thị")
        assert search_res.status_code == 200
        assert len(search_res.json()["data"]) >= 1

        prog_create = client.put(
            "/api/users/watch-progress/ep_shin_1",
            json={"assetId": "ast_shin_1", "positionMs": 120000, "expectedVersion": -1},
            headers=admin_headers,
        )
        assert prog_create.status_code == 200
        assert prog_create.json()["data"]["positionMs"] == 120000
        assert prog_create.json()["data"]["version"] == 0

        prog_update = client.put(
            "/api/users/watch-progress/ep_shin_1",
            json={"assetId": "ast_shin_1", "positionMs": 590000, "expectedVersion": 0},
            headers=admin_headers,
        )
        assert prog_update.status_code == 200
        assert prog_update.json()["data"]["completed"] is True
        assert prog_update.json()["data"]["version"] == 1
