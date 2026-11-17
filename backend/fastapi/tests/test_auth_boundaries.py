from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from main import create_app
from services.auth_limit import AuthRateLimiter


def test_auth_limits_attempts_and_recovers(monkeypatch):
    application = create_app(load_default=False)
    application.state.auth_limiter = AuthRateLimiter(limit=2)
    clock = [0]
    monkeypatch.setattr("services.auth_limit.monotonic", lambda: clock[0])
    with TestClient(application) as client:
        for _ in range(2):
            assert client.post("/api/auth/login", json={}).status_code == 400
        denied = client.post("/api/auth/login", json={})
        assert denied.status_code == 429
        assert int(denied.headers["retry-after"]) > 0
        assert client.get("/api/health").status_code == 200
        clock[0] = 61
        assert client.post("/api/auth/login", json={}).status_code == 400


def test_auth_limiter_capacity_keeps_other_accounts_available():
    limiter = AuthRateLimiter(limit=1, max_clients=2)
    assert limiter.retry_after(("127.0.0.1", "one")) == 0
    assert limiter.retry_after(("127.0.0.1", "two")) == 0
    assert limiter.retry_after(("127.0.0.1", "three")) == 0
    assert limiter.retry_after(("127.0.0.1", "two")) > 0
    assert len(limiter.clients) == 2


def test_registration_size_limits_preserve_raw_password():
    application = create_app(load_default=False)
    payload = {"username": "viewer", "email": "viewer@example.com", "password": " abcdef "}
    with TestClient(application) as client:
        invalid = [{**payload, "password": "ế" * 25},
                   {**payload, "email": "x" * 101 + "@example.com"},
                   {**payload, "fullName": "x" * 101}]
        for body in invalid:
            assert client.post("/api/auth/register", json=body).status_code in (400, 422)
        registered = client.post("/api/auth/register", json=payload)
        assert registered.status_code == 201
        assert client.post("/api/auth/login", json={
            "usernameOrEmail": "viewer", "password": payload["password"],
        }).status_code == 200


def test_duplicate_registration_remains_a_client_error():
    application = create_app(load_default=False)
    payload = {"username": "parallel", "email": "parallel@example.com", "password": "abcdef"}
    with TestClient(application, raise_server_exceptions=False) as client:
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(lambda _: client.post("/api/auth/register", json=payload), range(2)))
        assert sorted(response.status_code for response in responses) == [201, 400]
