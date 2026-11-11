import os
import tempfile
from pathlib import Path

os.environ.setdefault("DATABASE_URL", f"sqlite:///{Path(tempfile.gettempdir()).as_posix()}/dippie_pytest.db")
