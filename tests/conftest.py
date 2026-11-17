import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend/fastapi"))
from main import create_app


@pytest.fixture
def catalog_payload():
    return json.loads((ROOT / "docs/fixtures/rehearsal_catalog.json").read_text(encoding="utf-8"))


@pytest.fixture
def serving_app(tmp_path):
    return create_app(sync_secret="snapshot-token", sync_path=tmp_path / "accepted.json",
                      cache_dir=tmp_path / "vectors", load_default=False, model_mode="light")


@pytest.fixture
def client(serving_app):
    with TestClient(serving_app) as client:
        yield client


@pytest.fixture
def accept(client):
    def accept(payload, generation=1, **extra):
        return client.post("/api/index/sync", headers={"X-Service-Token": "snapshot-token"},
                           json={"catalog": payload, "generation": generation, **extra})
    return accept
