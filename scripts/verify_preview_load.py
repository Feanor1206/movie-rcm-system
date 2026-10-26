"""Bounded, read-only loopback load probe. Catalog sessions and Drive readers are measured separately."""
import argparse
import concurrent.futures
import json
import math
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path


def percentile(values, fraction):
    if not values:
        return None
    ordered = sorted(values)
    return round(ordered[max(0, math.ceil(len(ordered) * fraction) - 1)], 2)


def summarize(rows, elapsed):
    timings = [row["ms"] for row in rows]
    return {
        "requests": len(rows), "wall_seconds": round(elapsed, 3),
        "status_counts": dict(Counter(str(row["status"]) for row in rows)),
        "unexpected": sum(not row["valid"] for row in rows),
        "bytes": sum(row["bytes"] for row in rows),
        "latency_ms": {"p50": percentile(timings, .5), "p95": percentile(timings, .95),
                       "max": round(max(timings), 2) if timings else None},
        "rows": rows,
    }


class Probe:
    def __init__(self, base):
        self.base = base

    def request(self, path, *, method="GET", headers=None, expected=200, size=None):
        started = time.monotonic()
        row = {"path": path, "method": method, "status": 0, "bytes": 0, "valid": False}
        body = b""
        try:
            request = urllib.request.Request(self.base + path, method=method, headers=headers or {})
            with urllib.request.urlopen(request, timeout=35) as response:
                # No probe ever requests an unbounded video body.
                limit = 2 * 1024 * 1024 + 1 if size is not None else 4 * 1024 * 1024
                body = response.read(limit)
                row.update(status=response.status, bytes=len(body))
                row["valid"] = response.status == expected and (size is None or len(body) == size)
                if size is not None:
                    row["content_range"] = response.headers.get("Content-Range")
                    row["valid"] = row["valid"] and bool(row["content_range"])
        except urllib.error.HTTPError as error:
            row["status"] = error.code
            row["retry_after"] = error.headers.get("Retry-After")
        except Exception as error:
            row["error"] = type(error).__name__
        row["ms"] = round((time.monotonic() - started) * 1000, 2)
        return row, body

    def catalog_session(self, session, barrier, rounds):
        barrier.wait(timeout=15)
        paths = ["/api/catalog/series", "/api/catalog/search?q=Jadoo",
                 "/api/catalog/series/ser_jadoo",
                 f"/api/catalog/episodes/ep_jadoo_s01_000{1 + session % 2}"]
        rows = []
        for _ in range(rounds):
            for path in paths:
                row, body = self.request(path)
                try:
                    payload = json.loads(body)
                    row["valid"] = row["valid"] and isinstance(payload, (list, dict)) and bool(payload)
                except (ValueError, TypeError):
                    row["valid"] = False
                rows.append(row)
        return rows

    def drive_reader(self, reader, barrier, rounds):
        asset = f"asset_jadoo_s01_v000{1 + reader % 2}"
        path = f"/api/media/stream/{asset}"
        barrier.wait(timeout=15)
        rows = [self.request(path, method="HEAD")[0]]
        for turn in range(rounds):
            start = turn * 16 * 1024 * 1024
            size = 2 * 1024 * 1024
            row, _ = self.request(path, headers={"Range": f"bytes={start}-{start + size - 1}"},
                                  expected=206, size=size)
            rows.append(row)
        return rows


def concurrent_phase(count, run):
    barrier = threading.Barrier(count)
    started = time.monotonic()
    rows = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=count) as pool:
        futures = [pool.submit(run, index, barrier) for index in range(count)]
        for future in futures:
            rows.extend(future.result(timeout=180))
    return summarize(rows, time.monotonic() - started)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--rounds", type=int, choices=range(1, 6), default=3)
    parser.add_argument("--drive-readers", type=int, choices=range(0, 6), default=5)
    parser.add_argument("--output", type=Path, default=Path("target/preview-load.json"))
    args = parser.parse_args()
    url = urllib.parse.urlparse(args.base_url)
    if url.scheme != "http" or url.hostname not in {"localhost", "127.0.0.1", "::1"} or url.username or url.query or url.path not in {"", "/"}:
        parser.error("base-url must be an HTTP loopback origin")
    probe = Probe(args.base_url.rstrip("/"))
    result = {"measured_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
              "scope": "loopback HTTP catalog and bounded Range reads; not browser buffering or Internet capacity",
              "qwen": "not called", "phases": {}}
    for users in [10, 20]:
        phase = concurrent_phase(users, lambda index, barrier: probe.catalog_session(index, barrier, args.rounds))
        result["phases"][f"catalog_{users}_sessions"] = phase
        print(f"catalog {users}: requests={phase['requests']} unexpected={phase['unexpected']} p95={phase['latency_ms']['p95']}ms", flush=True)
    if args.drive_readers:
        phase = concurrent_phase(args.drive_readers, lambda index, barrier: probe.drive_reader(index, barrier, args.rounds))
        result["phases"][f"drive_{args.drive_readers}_readers"] = phase
        print(f"Drive {args.drive_readers}: requests={phase['requests']} unexpected={phase['unexpected']} p95={phase['latency_ms']['p95']}ms", flush=True)
    recovery, _ = probe.request("/api/catalog/series/ser_jadoo")
    result["recovery"] = recovery
    result["passed"] = recovery["valid"] and all(phase["unexpected"] == 0 for phase in result["phases"].values())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    raise SystemExit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
