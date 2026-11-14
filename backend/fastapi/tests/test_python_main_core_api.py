from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys
from threading import Barrier

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "backend" / "fastapi") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend" / "fastapi"))

from main import create_app
from services.database import CatalogSnapshot, MediaAsset


@pytest.fixture
def catalog_client(tmp_path, monkeypatch):
    media_root = tmp_path / "media"
    media_root.mkdir()
    (tmp_path / "canary.mp4").write_bytes(b"outside")
    (media_root / "inside.mp4").write_bytes(b"inside")
    monkeypatch.setenv("APP_MEDIA_ROOT", str(media_root))
    monkeypatch.setenv("APP_MEDIA_DRIVE_MOUNT", str(media_root))
    app = create_app(
        sync_path=tmp_path / "sync.json",
        cache_dir=tmp_path / "cache",
        model_mode="light",
        load_default=False,
        database_url=f"sqlite:///{tmp_path / 'catalog.db'}",
    )
    try:
        with TestClient(app, raise_server_exceptions=False) as client:
            login = client.post("/api/auth/login", json={"usernameOrEmail": "admin", "password": "password123"})
            assert login.status_code == 200
            headers = {"Authorization": f"Bearer {login.json()['data']['token']}"}
            yield client, headers, app.state.runtime.db
    finally:
        app.state.runtime.db.engine.dispose()


def test_catalog_import_rejects_older_packages_and_records_atomically(catalog_client):
    client, headers, database = catalog_client
    first = {"package": {"id": "catalog", "revision": 2}, "genres": [
        {"id": "genre", "labels": {"vi": "Gia đình"}, "record": {"revision": 2}}
    ]}
    assert client.post("/api/admin/catalog/import", json=first, headers=headers).status_code == 200
    for package_id, package_revision, record_revision in [("catalog", 1, 2), ("catalog", 3, 1), ("other", 3, 2)]:
        genre = first["genres"][0] if package_revision == 1 else {
            "id": "genre", "labels": {"vi": "Sai phiên bản"}, "record": {"revision": record_revision},
        }
        stale = {"package": {"id": package_id, "revision": package_revision}, "genres": [
            genre, {"id": "new-genre", "labels": {"vi": "Chưa nhập"}},
        ]}
        preview = client.post("/api/admin/catalog/validate", json=stale, headers=headers)
        assert preview.status_code == 200 and preview.json()["conflicts"] == 1
        denied = client.post("/api/admin/catalog/import", json=stale, headers=headers)
        assert denied.status_code == 409
    exported = client.get("/api/admin/catalog/export", headers=headers).json()
    assert exported["package"]["revision"] == 2
    assert exported["genres"] == first["genres"]
    with database.session() as db:
        assert db.query(CatalogSnapshot).count() == 1


def test_parallel_catalog_imports_cannot_commit_the_same_revision(catalog_client):
    client, headers, database = catalog_client
    barrier = Barrier(2)

    def submit(label):
        package = {"package": {"id": "parallel", "revision": 1}, "genres": [
            {"id": "genre", "labels": {"vi": label}},
        ]}
        barrier.wait(timeout=5)
        return client.post("/api/admin/catalog/import", json=package, headers=headers).status_code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(submit, ["Gia đình", "Phiêu lưu"])) == [200, 409]
    with database.session() as db:
        assert db.query(CatalogSnapshot).count() == 1


@pytest.mark.parametrize("relative_path", ["../canary.mp4", "..\\canary.mp4", "C:/canary.mp4", "/canary.mp4", "canary.mp4:stream"])
def test_catalog_rejects_unsafe_media_paths_on_preview_and_import(catalog_client, relative_path):
    client, headers, _ = catalog_client
    package = {"package": {"id": "catalog", "revision": 1}, "media_assets": [
        {"id": "outside", "storage": {"provider": "local", "relative_path": relative_path}},
    ]}
    preview = client.post("/api/admin/catalog/validate", json=package, headers=headers)
    assert preview.status_code == 400
    assert preview.json()["errors"][0]["path"] == "media_assets[0].storage.relative_path"
    assert client.post("/api/admin/catalog/import", json=package, headers=headers).status_code == 400
    assert client.get("/api/media/stream/outside").status_code == 404


@pytest.mark.parametrize("provider", ["local", "drive"])
def test_stream_contains_existing_media_paths(catalog_client, provider):
    client, _, database = catalog_client
    with database.session() as db:
        asset = db.get(MediaAsset, "ast-orbit-feat")
        asset.storage_provider = provider
        asset.relative_path = "../canary.mp4"
        db.commit()
    url = "/api/media/stream/ast-orbit-feat"
    assert client.get(url).status_code == 404
    with database.session() as db:
        db.get(MediaAsset, "ast-orbit-feat").relative_path = "inside.mp4"
        db.commit()
    assert client.get(url).content == b"inside"


def test_stream_rejects_links_outside_media_root(catalog_client, tmp_path):
    client, _, database = catalog_client
    link = tmp_path / "media" / "link.mp4"
    try:
        link.symlink_to(tmp_path / "canary.mp4")
    except OSError as exc:
        if sys.platform != "win32" or getattr(exc, "winerror", None) != 1314:
            raise
        pytest.skip("Tạo liên kết tượng trưng trên Windows cần thêm quyền")
    with database.session() as db:
        db.get(MediaAsset, "ast-orbit-feat").relative_path = "link.mp4"
        db.commit()
    assert client.get("/api/media/stream/ast-orbit-feat").status_code == 404


@pytest.mark.parametrize("endpoint", ["validate", "import"])
def test_catalog_bad_revision_returns_400(catalog_client, endpoint):
    client, headers, _ = catalog_client
    response = client.post(
        f"/api/admin/catalog/{endpoint}", json={"package": {"id": "catalog", "revision": "bad"}}, headers=headers,
    )
    assert response.status_code == 400


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

        grant_as_auth = client.get("/api/auth/me", headers={"Authorization": f"Bearer {grant_body['grant']}"})
        assert grant_as_auth.status_code == 401

        head_res = client.head(grant_body["streamUrl"])
        assert head_res.status_code == 200
        assert head_res.headers.get("accept-ranges") == "bytes"
        assert int(head_res.headers.get("content-length", "0")) > 0

        token_stream_res = client.get(f"/api/media/stream/ast-orbit-feat?token={grant_body['token']}")
        assert token_stream_res.status_code == 200

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
        assert valid_val.json()["toCreate"] == 5
        assert valid_val.json()["toUpdate"] == 0
        assert valid_val.json()["unchanged"] == 0
        assert valid_val.json()["conflicts"] == 0

        imp_res = client.post("/api/admin/catalog/import", json=sample_package, headers=admin_headers)
        assert imp_res.status_code == 200
        assert imp_res.json()["success"] is True

        unchanged_val = client.post("/api/admin/catalog/validate", json=sample_package, headers=admin_headers)
        assert unchanged_val.status_code == 200
        assert unchanged_val.json()["unchanged"] == 5
        assert unchanged_val.json()["toCreate"] == 0

        updated_pkg = {
            **sample_package,
            "package": {"id": "pkg_mysql_test", "version": "1.0.1", "revision": 2},
            "series": [
                {
                    **sample_package["series"][0],
                    "synopsis": "Phim hoạt hình gia đình vui nhộn bản cập nhật",
                    "record": {"status": "ready", "revision": 2},
                }
            ],
        }
        update_val = client.post("/api/admin/catalog/validate", json=updated_pkg, headers=admin_headers)
        assert update_val.status_code == 200
        assert update_val.json()["toUpdate"] == 2
        assert update_val.json()["unchanged"] == 3
        assert update_val.json()["conflicts"] == 0

        conflict_pkg = {
            **sample_package,
            "series": [
                {
                    **sample_package["series"][0],
                    "synopsis": "Thay đổi nội dung nhưng không tăng revision",
                }
            ],
        }
        conflict_val = client.post("/api/admin/catalog/validate", json=conflict_pkg, headers=admin_headers)
        assert conflict_val.status_code == 200
        assert conflict_val.json()["conflicts"] == 2

        repeat = client.post("/api/admin/catalog/import", json=sample_package, headers=admin_headers)
        assert repeat.status_code == 200
        assert repeat.json()["importId"] == imp_res.json()["importId"]
        conflict_import = client.post("/api/admin/catalog/import", json=conflict_pkg, headers=admin_headers)
        assert conflict_import.status_code == 409

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
        assert {"id", "revision", "created_at", "default_language", "import_mode", "reference_scope", "description"}.issubset(
            set(export_res.json()["package"].keys())
        )

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
