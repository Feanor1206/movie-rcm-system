from pathlib import Path
import sys

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "backend" / "fastapi") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend" / "fastapi"))

from main import create_app


def test_python_main_auth_movies_and_user_library(tmp_path, monkeypatch):
    media_root = tmp_path / "media"
    synthetic_dir = media_root / "synthetic"
    synthetic_dir.mkdir(parents=True, exist_ok=True)
    (synthetic_dir / "feature_test.mp4").write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 1024)
    monkeypatch.setenv("APP_MEDIA_ROOT", str(media_root))
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

        browse_default = client.get("/api/movies/browse")
        assert browse_default.status_code == 200
        assert browse_default.json()["data"]["size"] == 12

        browse_res = client.get("/api/movies/browse?query=Orbit&genre=Sci-Fi&page=0&size=5")
        assert browse_res.status_code == 200
        browse_data = browse_res.json()["data"]
        assert browse_data["totalElements"] == 1
        assert browse_data["items"][0]["id"] == "the-last-orbit"

        browse_search = client.get("/api/movies/browse?search=Orbit&page=0&size=5")
        assert browse_search.status_code == 200
        assert browse_search.json()["data"]["totalElements"] == 1

        not_found_movie = client.get("/api/movies/nonexistent-movie-id")
        assert not_found_movie.status_code == 404
        assert not_found_movie.json()["success"] is False

        desc_res = client.get("/api/movies/the-last-orbit/media-descriptor")
        assert desc_res.status_code == 200
        assert desc_res.json()["data"]["hasFeature"] is True
        assert desc_res.json()["data"]["hasTrailer"] is True

        grant_res = client.post("/api/media/grant/ast-orbit-feat")
        assert grant_res.status_code == 200
        grant_body = grant_res.json()
        assert grant_body["assetId"] == "ast-orbit-feat"
        assert grant_body["grant"]
        assert grant_body["streamUrl"].startswith("/api/media/stream/ast-orbit-feat?grant=")
        assert grant_body["expiresIn"] == 300

        head_res = client.head(grant_body["streamUrl"])
        assert head_res.status_code == 200
        assert head_res.headers.get("accept-ranges") == "bytes"
        assert int(head_res.headers.get("content-length", "0")) > 0

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

        login_by_email = client.post(
            "/api/auth/login",
            json={"usernameOrEmail": "tester@dippie.com", "password": "password123"},
        )
        assert login_by_email.status_code == 200
        assert login_by_email.json()["data"]["username"] == "new_tester"

        login_by_username = client.post(
            "/api/auth/login",
            json={"usernameOrEmail": "new_tester", "password": "password123"},
        )
        assert login_by_username.status_code == 200
        assert login_by_username.json()["data"]["email"] == "tester@dippie.com"

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
        admin_login = client.post("/api/auth/login", json={"usernameOrEmail": "admin", "password": "password123"})
        assert admin_login.status_code == 200
        admin_token = admin_login.json()["data"]["token"]
        admin_headers = {"Authorization": f"Bearer {admin_token}"}

        invalid_val = client.post("/api/admin/catalog/validate", json={"series": []}, headers=admin_headers)
        assert invalid_val.status_code == 400
        assert invalid_val.json()["valid"] is False
        assert isinstance(invalid_val.json()["errors"], list)
        assert invalid_val.json()["toCreate"] == 0

        valid_val = client.post("/api/admin/catalog/validate", json=sample_package, headers=admin_headers)
        assert valid_val.status_code == 200
        assert valid_val.json()["valid"] is True
        assert valid_val.json()["packageId"] == "pkg_mysql_test"

        imp_res = client.post("/api/admin/catalog/import", json=sample_package, headers=admin_headers)
        assert imp_res.status_code == 200
        assert imp_res.json()["success"] is True

        hist_res = client.get("/api/admin/catalog/history", headers=admin_headers)
        assert hist_res.status_code == 200
        assert isinstance(hist_res.json(), list)
        assert len(hist_res.json()) == 1

        snaps_res = client.get("/api/admin/catalog/snapshots", headers=admin_headers)
        assert snaps_res.status_code == 200
        assert isinstance(snaps_res.json(), list)
        assert len(snaps_res.json()) == 1
        snap_id = snaps_res.json()[0]["id"]

        retry_res = client.post(f"/api/admin/catalog/snapshots/{snap_id}/retry", headers=admin_headers)
        assert retry_res.status_code == 200
        assert retry_res.json()["id"] == snap_id
        assert retry_res.json()["retryCount"] == 1

        export_res = client.get("/api/admin/catalog/export", headers=admin_headers)
        assert export_res.status_code == 200
        assert export_res.json()["schema_version"] == "dippie.catalog.v1"

        all_series_res = client.get("/api/catalog/series")
        assert all_series_res.status_code == 200
        assert isinstance(all_series_res.json(), list)
        assert len(all_series_res.json()) == 1

        series_res = client.get("/api/catalog/series/ser_shin")
        assert series_res.status_code == 200
        assert len(series_res.json()["episodes"]) == 1

        ep_res = client.get("/api/catalog/episodes/ep_shin_1")
        assert ep_res.status_code == 200
        assert ep_res.json()["episode"]["title"] == "Tập 1: Đi siêu thị"

        search_res = client.get("/api/catalog/search?q=siêu thị")
        assert search_res.status_code == 200
        assert len(search_res.json()) >= 1

        ai_search = client.post("/v1/search", json={"query": "siêu thị", "limit": 5})
        assert ai_search.status_code == 200
        ai_hits = ai_search.json().get("results") or []
        assert any(h.get("id") == "ep_shin_1" for h in ai_hits)

        ai_rcm = client.post("/api/recommend", json={"movie_id": "ep_shin_1", "limit": 5})
        assert ai_rcm.status_code == 200

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

    app2 = create_app(
        sync_secret="test-secret",
        sync_path=tmp_path / "nonexistent_sync.json",
        cache_dir=tmp_path / "cache2",
        model_mode="light",
        load_default=False,
        database_url=f"sqlite:///{db_file}",
    )
    with TestClient(app2) as client2:
        ai_search2 = client2.post("/v1/search", json={"query": "siêu thị", "limit": 5})
        assert ai_search2.status_code == 200
        assert any(h.get("id") == "ep_shin_1" for h in (ai_search2.json().get("results") or []))
