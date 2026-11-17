from fastapi.testclient import TestClient

from main import create_app


def test_static_web_shares_a_process_with_api(tmp_path):
    dist = tmp_path / "web"
    (dist / "assets").mkdir(parents=True)
    (dist / "illustrations").mkdir()
    (dist / "index.html").write_text("<title>Dippie</title>", encoding="utf-8")
    (dist / "assets/app.js").write_text("export {};", encoding="utf-8")
    (dist / "illustrations/cover.svg").write_text("<svg/>", encoding="utf-8")
    app = create_app(web_dist=dist, model_mode="light", load_default=False,
                     database_url=f"sqlite:///{tmp_path / 'web.db'}",
                     sync_path=tmp_path / "state.json", cache_dir=tmp_path / "cache")

    with TestClient(app) as client:
        for path in ("/", "/search?q=jadoo", "/profile", "/admin/import", "/movies/m1", "/series/s1?episode=e1"):
            response = client.get(path)
            assert response.status_code == 200
            assert response.text == "<title>Dippie</title>"
            assert response.headers["cache-control"] == "no-cache"
        assert client.head("/series/s1").status_code == 200
        assert client.get("/assets/app.js").text == "export {};"
        assert client.get("/illustrations/cover.svg").text == "<svg/>"
        assert client.get("/api/health").json()["success"] is True
        assert client.get("/api/missing").status_code == 404
        assert client.get("/assets/missing.js").status_code == 404
