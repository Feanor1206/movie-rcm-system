import base64

import pytest


@pytest.fixture(autouse=True)
def demo_configuration(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'test.db').as_posix()}")
    monkeypatch.setenv("APP_DEMO_MODE", "true")
    monkeypatch.setenv("APP_JWT_SECRET", base64.b64encode(bytes(range(32))).decode())
    monkeypatch.delenv("APP_BOOTSTRAP_ADMIN_USERNAME", raising=False)
    monkeypatch.delenv("APP_BOOTSTRAP_ADMIN_EMAIL", raising=False)
    monkeypatch.delenv("APP_BOOTSTRAP_ADMIN_PASSWORD", raising=False)
