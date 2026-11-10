import hashlib
import json
import os
import re
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS = ROOT / "ai/artifacts"
CATALOG = ROOT / "data/catalog.jadoo_all.json"


def load_deepseek_env():
    path = ROOT / ".env.deepseek.local"
    if not path.is_file():
        return
    keys = {"DEEPSEEK_BASE_URL", "DEEPSEEK_MODEL", "DEEPSEEK_API_KEY"}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        name, separator, value = line.partition("=")
        if separator and name in keys:
            os.environ[name] = value


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        except BaseException:
            stream.close()
            temporary.unlink(missing_ok=True)
            raise
    try:
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


def episodes(path, requested=None):
    rows = read(path)["pilot"]
    identifiers = [row["episode_id"] for row in rows]
    if len(rows) != 5 or len(set(identifiers)) != 5 or any(not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", key) for key in identifiers):
        raise ValueError("Expected an inventory with exactly five distinct pilot episodes")
    if requested:
        wanted = set(requested)
        if not wanted <= set(identifiers):
            raise ValueError("Requested episode is outside the pilot inventory")
        rows = [row for row in rows if row["episode_id"] in wanted]
    return rows


def run(*args):
    return subprocess.run([str(arg) for arg in args], capture_output=True, text=True, encoding="utf-8", check=True).stdout


def probe(path):
    fields = read_probe(path)
    return round(float(fields["format"]["duration"]) * 1000)


def read_probe(path):
    return json.loads(run("ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type",
                          "-of", "json", path))


def pilot_options(parser):
    parser.add_argument("--inventory", type=Path, default=ARTIFACTS / "inventory.json")
    parser.add_argument("--artifacts", type=Path, default=ARTIFACTS)
    parser.add_argument("--episode", action="append")
