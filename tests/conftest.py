"""Keep rule, catalog and API regressions independent of downloaded model weights."""
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend" / "fastapi"))


@pytest.fixture(scope="session", autouse=True)
def lexical_retrieval_only():
    # These suites verify deterministic catalog rules; live models have separate opt-in tests.
    from services.hybrid_retrieval import DenseEncoder

    with patch.object(DenseEncoder, "load"):
        yield
