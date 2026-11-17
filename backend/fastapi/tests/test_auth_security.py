import base64
from pathlib import Path
import sys

import pytest
import jwt
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "backend/fastapi"))
from main import create_app
from services.database import User, verify_password

VALID_KEY = base64.b64encode(bytes(range(32))).decode()
OLD_KEY = "404E635266556A586E3272357538782F413F4428472B4B6250645367566B5970"


def make_app(tmp_path):
    return create_app(
        database_url=f"sqlite:///{tmp_path / 'auth.db'}",
        sync_path=tmp_path / "sync.json",
        cache_dir=tmp_path / "cache",
        model_mode="light",
        load_default=False,
    )


@pytest.mark.parametrize(
    "key",
    [
        "",
        OLD_KEY,
        "invalid!",
        base64.b64encode(b"short").decode(),
        "dippieSecretKeyForJwtAuthentication2026MustBeLongEnoughForHmacSha256",
    ],
)
def test_production_rejects_missing_known_or_invalid_key(tmp_path, monkeypatch, key):
    monkeypatch.delenv("APP_DEMO_MODE", raising=False)
    monkeypatch.setenv("APP_JWT_SECRET", key)
    with pytest.raises(RuntimeError):
        with TestClient(make_app(tmp_path)):
            pass


def test_production_bootstraps_without_demo_users_and_preserves_existing_admin(
    tmp_path, monkeypatch
):
    monkeypatch.delenv("APP_DEMO_MODE", raising=False)
    monkeypatch.setenv("APP_JWT_SECRET", VALID_KEY)
    monkeypatch.setenv("APP_BOOTSTRAP_ADMIN_USERNAME", "owner")
    monkeypatch.setenv("APP_BOOTSTRAP_ADMIN_EMAIL", "owner@example.com")
    monkeypatch.setenv("APP_BOOTSTRAP_ADMIN_PASSWORD", "A-strong-private-password-123")
    app = make_app(tmp_path)
    with TestClient(app):
        with app.state.runtime.db.session() as db:
            users = db.query(User).all()
            assert [(u.username, u.role) for u in users] == [("owner", "ROLE_ADMIN")]
            assert verify_password("A-strong-private-password-123", users[0].password)
    monkeypatch.setenv("APP_BOOTSTRAP_ADMIN_PASSWORD", "another-strong-password-456")
    with TestClient(make_app(tmp_path)) as client:
        assert (
            client.post(
                "/api/auth/login",
                json={
                    "usernameOrEmail": "owner",
                    "password": "A-strong-private-password-123",
                },
            ).status_code
            == 200
        )


def test_old_demo_admin_requires_explicit_reset(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_DEMO_MODE", "true")
    monkeypatch.setenv("APP_JWT_SECRET", VALID_KEY)
    with TestClient(make_app(tmp_path)):
        pass
    monkeypatch.delenv("APP_DEMO_MODE")
    with pytest.raises(RuntimeError):
        with TestClient(make_app(tmp_path)):
            pass
    monkeypatch.setenv("APP_BOOTSTRAP_ADMIN_USERNAME", "admin")
    monkeypatch.setenv("APP_BOOTSTRAP_ADMIN_PASSWORD", "A-strong-private-password-123")
    with TestClient(make_app(tmp_path)) as client:
        assert (
            client.post(
                "/api/auth/login",
                json={"usernameOrEmail": "admin", "password": "password123"},
            ).status_code
            == 401
        )
        assert (
            client.post(
                "/api/auth/login",
                json={
                    "usernameOrEmail": "admin",
                    "password": "A-strong-private-password-123",
                },
            ).status_code
            == 200
        )
        assert (
            client.post(
                "/api/auth/login",
                json={"usernameOrEmail": "user", "password": "password123"},
            ).status_code
            == 401
        )
        forged = jwt.encode(
            {"sub": "admin"}, base64.b64decode(OLD_KEY), algorithm="HS256"
        )
        assert (
            client.get(
                "/api/auth/me", headers={"Authorization": f"Bearer {forged}"}
            ).status_code
            == 401
        )


def test_incomplete_bootstrap_is_rejected(tmp_path, monkeypatch):
    monkeypatch.delenv("APP_DEMO_MODE", raising=False)
    monkeypatch.setenv("APP_JWT_SECRET", VALID_KEY)
    monkeypatch.setenv("APP_BOOTSTRAP_ADMIN_USERNAME", "owner")
    with pytest.raises(RuntimeError, match="APP_BOOTSTRAP_ADMIN_PASSWORD"):
        with TestClient(make_app(tmp_path)):
            pass
