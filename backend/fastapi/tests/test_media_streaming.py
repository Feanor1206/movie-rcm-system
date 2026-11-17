from pathlib import Path
import sys

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "backend" / "fastapi"))
sys.path.insert(0, str(ROOT))

from main import create_app
from services.database import MediaAsset


def test_stream_reads_in_bounded_chunks_and_preserves_ranges(tmp_path, monkeypatch):
    media = tmp_path / "media" / "synthetic" / "feature_test.mp4"
    media.parent.mkdir(parents=True)
    payload = bytes(range(256)) * 4096
    media.write_bytes(payload)
    monkeypatch.setenv("APP_MEDIA_ROOT", str(tmp_path / "media"))
    app = create_app(
        sync_secret="test-secret",
        sync_path=tmp_path / "sync.json",
        cache_dir=tmp_path / "cache",
        model_mode="light",
        load_default=False,
        database_url=f"sqlite:///{tmp_path / 'test.db'}",
    )
    reads = []
    original_open = Path.open

    class CountingFile:
        def __init__(self, file):
            self.file = file

        def __enter__(self):
            self.file.__enter__()
            return self

        def __exit__(self, *args):
            return self.file.__exit__(*args)

        def seek(self, *args):
            return self.file.seek(*args)

        def read(self, size=-1):
            data = self.file.read(size)
            reads.append(len(data))
            return data

    def counting_open(path, *args, **kwargs):
        file = original_open(path, *args, **kwargs)
        if path == media and (args[0] if args else kwargs.get("mode")) == "rb":
            return CountingFile(file)
        return file

    with TestClient(app) as client:
        monkeypatch.setattr(Path, "open", counting_open)
        url = "/api/media/stream/ast-orbit-feat"
        full = client.get(url)
        assert full.status_code == 200
        assert full.content == payload
        assert full.headers["content-length"] == str(len(payload))
        print(f"largest media read: {max(reads)} bytes")
        assert max(reads) <= 65536

        for value, start, end in [
            ("bytes=10-29", 10, 29),
            ("bytes=100-", 100, len(payload) - 1),
            ("bytes=-15", len(payload) - 15, len(payload) - 1),
            (
                f"bytes={len(payload)-10}-{len(payload)+100}",
                len(payload) - 10,
                len(payload) - 1,
            ),
        ]:
            reads.clear()
            response = client.get(url, headers={"Range": value})
            assert response.status_code == 206
            assert response.content == payload[start : end + 1]
            assert (
                response.headers["content-range"]
                == f"bytes {start}-{end}/{len(payload)}"
            )
            assert int(response.headers["content-length"]) == end - start + 1
            assert max(reads) <= 65536
        assert (
            client.get(url, headers={"Range": f"bytes={len(payload)}-"}).status_code
            == 416
        )
        head = client.head(url, headers={"Range": "bytes=0-1"})
        assert head.status_code == 200
        assert head.content == b""
        assert head.headers["content-length"] == str(len(payload))

        media.write_bytes(b"")
        assert client.get(url).status_code == 200
        assert client.head(url).headers["content-length"] == "0"
        empty_range = client.get(url, headers={"Range": "bytes=-1"})
        assert empty_range.status_code == 416
        assert empty_range.headers["content-range"] == "bytes */0"

        media.write_bytes(payload)
        with app.state.runtime.db.session() as db:
            db.get(MediaAsset, "ast-orbit-feat").is_public = False
            db.commit()
        assert client.get(url).status_code == 404
        assert client.get(url, params={"grant": "invalid"}).status_code == 404
        login = client.post(
            "/api/auth/login",
            json={"usernameOrEmail": "admin", "password": "password123"},
        )
        headers = {"Authorization": f"Bearer {login.json()['data']['token']}"}
        grant = client.post("/api/media/grant/ast-orbit-feat", headers=headers)
        assert grant.status_code == 200
        response = client.get(grant.json()["streamUrl"], headers={"Range": "bytes=0-9"})
        assert response.status_code == 206
        assert response.content == payload[:10]
