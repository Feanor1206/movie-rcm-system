"""
=============================================================================
CATALOG-01-F08: END-TO-END PRODUCTION-STACK REHEARSAL & VERIFICATION
=============================================================================
Hermetic production stack rehearsal covering:
1. Preflight port & drive letter verification.
2. Read-only Google Drive mount to X: via rclone (folder: 1Ypyq-KuQKEhHrWuxtrrR8Y4G7DwbeyZQ).
3. FastAPI on port 8008 with isolated sync state & AcceptedSnapshot single reference swap.
4. Spring Boot on port 8088 with isolated H2 DB, snapshot, DriveMediaStorageAdapter (X:).
5. Next.js on port 3008 with isolated backend API URL.
6. Admin authentication & JWT token issuance via HTTP.
7. Catalog validation & preview (/api/admin/catalog/validate).
8. Catalog import into DB (/api/admin/catalog/import).
9. Worker HTTP sync to FastAPI (/api/index/sync) -> outbox READY.
10. Catalog discovery & search across both backends.
11. Media streaming security matrix (public, protected fail-closed, grant token,
    grant rejection as Bearer, grant asset-binding against real protected asset 03).
12. Real Google Drive media streaming through Spring Boot (HEAD, GET Range 206 1MB chunk, near-end chunk).
13. Fail-closed browser automation via Chrome CDP (Form login, Admin import UI,
    Search UI, Public playback, pause/resume, scene seek 15s without fallback,
    3 timeline seeks, protected episode 2 with grant, real Drive video playback & seek,
    negative control test, screenshot).
14. First service restart recovery (Spring Boot + FastAPI) verifying persistence.
15. Second service restart recovery verifying double-restart durability.
16. Clean process teardown strictly by recorded PID.
=============================================================================
"""

import os
import sys
import io
import json
import time
import shutil
import socket
import tempfile
import urllib.request
import urllib.error
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List

if sys.platform == "win32":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace", line_buffering=True)
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent.parent

FASTAPI_PORT = 8008
SPRING_PORT = 8088
FRONTEND_PORT = 3008
CDP_PORT = 9228
SYNC_SECRET = "rehearsal_f08_secret_2026"
DRIVE_ROOT_FOLDER_ID = "1Ypyq-KuQKEhHrWuxtrrR8Y4G7DwbeyZQ"
DRIVE_MOUNT_LETTER = "X:"


def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def http_request(
    url: str,
    method: str = "GET",
    data: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: float = 60.0
) -> Tuple[int, Dict[str, Any], bytes]:
    req_headers = headers.copy() if headers else {}
    req_body = None
    if data is not None:
        req_body = json.dumps(data).encode("utf-8")
        req_headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=req_body, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            status = resp.status
            raw = resp.read()
            parsed = {}
            if resp.headers.get_content_type() == "application/json":
                try:
                    parsed = json.loads(raw.decode("utf-8"))
                except Exception:
                    pass
            return status, parsed, raw
    except urllib.error.HTTPError as e:
        raw = e.read()
        parsed = {}
        try:
            parsed = json.loads(raw.decode("utf-8"))
        except Exception:
            pass
        return e.code, parsed, raw
    except Exception as e:
        return 0, {"error": str(e)}, b""


def wait_for_service_ok(url: str, max_wait_sec: float = 45.0, interval: float = 1.0) -> bool:
    deadline = time.time() + max_wait_sec
    while time.time() < deadline:
        status, _, _ = http_request(url, timeout=2.0)
        if status == 200:
            return True
        time.sleep(interval)
    return False


def get_git_commit() -> str:
    try:
        res = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(ROOT), capture_output=True, text=True)
        return res.stdout.strip()
    except Exception:
        return "UNKNOWN"


def get_file_sha256(p: Path) -> str:
    import hashlib
    if not p.exists():
        return "NOT_FOUND"
    return hashlib.sha256(p.read_bytes()).hexdigest()


def run_rehearsal_f08() -> Dict[str, Any]:
    print("=" * 78)
    print("STARTING CATALOG-01-F08 FULL PRODUCTION-STACK REHEARSAL")
    print("=" * 78)

    # 1. Preflight port checks
    for p, name in [(FASTAPI_PORT, "FastAPI"), (SPRING_PORT, "Spring Boot"), (FRONTEND_PORT, "Frontend"), (CDP_PORT, "Chrome CDP")]:
        if is_port_in_use(p):
            raise RuntimeError(f"Preflight error: Port {p} ({name}) is already in use by another process!")
    print("[Preflight] All target ports (8008, 8088, 3008, 9228) are free and available.")

    rehearsal_fixture_path = ROOT / "docs/fixtures/rehearsal_catalog.json"
    if not rehearsal_fixture_path.exists():
        raise FileNotFoundError(f"Fixture missing: {rehearsal_fixture_path}")
    rehearsal_catalog = json.loads(rehearsal_fixture_path.read_text(encoding="utf-8"))

    jar_path = ROOT / "backend/springboot/target/moviercm-backend-0.0.1-SNAPSHOT.jar"
    if not jar_path.exists():
        raise FileNotFoundError(f"Spring Boot jar not found at: {jar_path}")

    git_commit = get_git_commit()
    jar_hash = get_file_sha256(jar_path)
    fixture_hash = get_file_sha256(rehearsal_fixture_path)
    print(f"[Artifact Identity] Commit: {git_commit}")
    print(f"[Artifact Identity] Jar SHA-256: {jar_hash[:16]}... ({jar_path.stat().st_size} bytes)")
    print(f"[Artifact Identity] Fixture SHA-256: {fixture_hash[:16]}...")

    temp_dir = Path(tempfile.mkdtemp(prefix="dippie-rehearsal-f08-"))
    print(f"[Setup] Isolated temporary directory: {temp_dir}")

    db_path = temp_dir / "rehearsal_db"
    snapshot_path = temp_dir / "committed_catalog_snapshot.json"
    fastapi_state_dir = temp_dir / "fastapi_state"
    fastapi_state_dir.mkdir(parents=True, exist_ok=True)
    fastapi_state_file = fastapi_state_dir / "accepted_catalog_state.json"
    default_catalog_file = temp_dir / "default_empty_catalog.json"
    default_catalog_file.write_text("{}", encoding="utf-8")

    tracked_pids: List[int] = []
    fastapi_proc = None
    spring_proc = None
    frontend_proc = None
    rclone_proc = None

    results: Dict[str, Any] = {
        "status": "IN_PROGRESS",
        "commit": git_commit,
        "jar_sha256": jar_hash,
        "fixture_sha256": fixture_hash,
        "gates": {},
        "evidence": {}
    }

    try:
        # ---------------------------------------------------------------------
        # Step 0: Mount Google Drive via rclone (Finding R3)
        # ---------------------------------------------------------------------
        print(f"\n[Step 0] Mounting Google Drive to {DRIVE_MOUNT_LETTER} via rclone...")
        rclone_cmd = [
            "rclone", "mount",
            "--drive-root-folder-id", DRIVE_ROOT_FOLDER_ID,
            "--read-only",
            "--vfs-cache-mode", "off",
            "--buffer-size", "16M",
            "cinema-drive:", DRIVE_MOUNT_LETTER
        ]
        rclone_proc = subprocess.Popen(rclone_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        tracked_pids.append(rclone_proc.pid)
        print(f"  rclone mount process launched with PID {rclone_proc.pid}")

        drive_ready = False
        drive_path = Path("X:/")
        for _ in range(15):
            time.sleep(1.0)
            if drive_path.exists() and (drive_path / "jadooss1").exists():
                drive_ready = True
                break
            if rclone_proc.poll() is not None:
                break

        assert drive_ready, f"Failed to mount Google Drive to {DRIVE_MOUNT_LETTER} within 15 seconds"
        print(f"  Drive {DRIVE_MOUNT_LETTER} mounted successfully (folders: {[p.name for p in drive_path.iterdir()]}).")
        results["gates"]["google_drive_mount"] = "PASS"

        # ---------------------------------------------------------------------
        # Step 1: Launch FastAPI (Port 8008)
        # ---------------------------------------------------------------------
        print(f"\n[Step 1] Launching FastAPI on port {FASTAPI_PORT}...")
        fa_env = os.environ.copy()
        fa_env["PORT"] = str(FASTAPI_PORT)
        fa_env["SERVING_MODE"] = "light"
        fa_env["USE_FULL_QWEN3_4B_LORA"] = "false"
        fa_env["FASTAPI_SYNC_SECRET"] = SYNC_SECRET
        fa_env["SYNC_STATE_PATH"] = str(fastapi_state_file)
        fa_env["DEFAULT_CATALOG_PATH"] = str(default_catalog_file)
        fa_env["PYTHONPATH"] = str(ROOT / "backend/fastapi")

        fa_cmd = [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", str(FASTAPI_PORT), "--log-level", "warning"]
        fa_log = open(temp_dir / "fastapi.log", "w", encoding="utf-8")
        fastapi_proc = subprocess.Popen(fa_cmd, cwd=str(ROOT / "backend/fastapi"), env=fa_env, stdout=fa_log, stderr=subprocess.STDOUT)
        tracked_pids.append(fastapi_proc.pid)
        print(f"  FastAPI started with PID {fastapi_proc.pid}")

        if not wait_for_service_ok(f"http://127.0.0.1:{FASTAPI_PORT}/health", max_wait_sec=25.0):
            raise RuntimeError("FastAPI health check failed on port 8008")
        print("  FastAPI service is HEALTHY (200 OK).")

        # ---------------------------------------------------------------------
        # Step 2: Launch Spring Boot (Port 8088) with DriveMediaStorageAdapter
        # ---------------------------------------------------------------------
        print(f"\n[Step 2] Launching Spring Boot on port {SPRING_PORT} with Drive mount {DRIVE_MOUNT_LETTER}...")
        java_home = os.environ.get("JAVA_HOME", "C:\\Program Files\\Java\\jdk-25.0.3")
        java_bin = Path(java_home) / "bin/java.exe" if os.name == "nt" else Path(java_home) / "bin/java"
        if not java_bin.exists():
            java_bin = "java"

        spring_args = [
            str(java_bin),
            f"-Dserver.port={SPRING_PORT}",
            "-Dspring.profiles.active=dev",
            f"-Dspring.datasource.url=jdbc:h2:file:{db_path.as_posix()};DB_CLOSE_DELAY=-1;DB_CLOSE_ON_EXIT=FALSE;MODE=PostgreSQL;NON_KEYWORDS=YEAR,USER",
            f"-Dapp.catalog.sync-url=http://127.0.0.1:{FASTAPI_PORT}/api/index/sync",
            f"-Dapp.catalog.sync-token={SYNC_SECRET}",
            f"-Dapp.catalog.snapshot-path={snapshot_path.as_posix()}",
            f"-Dapp.media.root={(ROOT / 'media').as_posix()}",
            "-Dapp.media.drive-mount=X:",
            "-Dapp.media.drive.mount-path=X:\\",
            "-Dapp.media.drive-read-timeout-ms=60000",
            "-Dapp.media.drive-metadata-timeout-ms=60000",
            "-Dapp.seed.enabled=true",
            "-jar", str(jar_path)
        ]
        sb_log = open(temp_dir / "spring_boot.log", "w", encoding="utf-8")
        spring_proc = subprocess.Popen(spring_args, cwd=str(ROOT / "backend/springboot"), stdout=sb_log, stderr=subprocess.STDOUT)
        tracked_pids.append(spring_proc.pid)
        print(f"  Spring Boot started with PID {spring_proc.pid}")

        if not wait_for_service_ok(f"http://127.0.0.1:{SPRING_PORT}/api/health", max_wait_sec=50.0):
            raise RuntimeError("Spring Boot health check failed on port 8088")
        print("  Spring Boot service is HEALTHY (200 OK).")

        # ---------------------------------------------------------------------
        # Step 3: Launch Next.js Frontend (Port 3008)
        # ---------------------------------------------------------------------
        print(f"\n[Step 3] Launching Next.js frontend on port {FRONTEND_PORT}...")
        fe_env = os.environ.copy()
        fe_env["PORT"] = str(FRONTEND_PORT)
        fe_env["NEXT_PUBLIC_API_URL"] = f"http://127.0.0.1:{SPRING_PORT}"
        fe_env["NEXT_PUBLIC_SPRINGBOOT_API_URL"] = f"http://127.0.0.1:{SPRING_PORT}/api"
        fe_env["NEXT_PUBLIC_MODEL_API_URL"] = f"http://127.0.0.1:{FASTAPI_PORT}/api/chat"

        fe_log = open(temp_dir / "frontend.log", "w", encoding="utf-8")
        frontend_proc = subprocess.Popen(
            ["npx.cmd" if os.name == "nt" else "npx", "next", "dev", "-p", str(FRONTEND_PORT)],
            cwd=str(ROOT / "frontend"),
            env=fe_env,
            stdout=fe_log,
            stderr=subprocess.STDOUT
        )
        tracked_pids.append(frontend_proc.pid)
        print(f"  Frontend started with PID {frontend_proc.pid}")

        if not wait_for_service_ok(f"http://127.0.0.1:{FRONTEND_PORT}", max_wait_sec=40.0):
            raise RuntimeError(f"Frontend failed to respond on port {FRONTEND_PORT}")
        print("  Frontend service is HEALTHY (200 OK).")

        # ---------------------------------------------------------------------
        # Step 4: Admin Authentication (HTTP Direct)
        # ---------------------------------------------------------------------
        print("\n[Step 4] Authenticating as admin (admin / password123)...")
        status, body, _ = http_request(
            f"http://127.0.0.1:{SPRING_PORT}/api/auth/login",
            method="POST",
            data={"usernameOrEmail": "admin", "password": "password123"}
        )
        assert status == 200, f"Admin login failed: {status} -> {body}"
        admin_jwt = body.get("data", {}).get("token") or body.get("token")
        assert admin_jwt, f"No JWT token in login response: {body}"
        auth_header = {"Authorization": f"Bearer {admin_jwt}"}
        print(f"  Admin login SUCCESS (JWT acquired, len={len(admin_jwt)}).")
        results["gates"]["admin_login"] = "PASS"

        # ---------------------------------------------------------------------
        # Step 5: Validate Package (HTTP Direct)
        # ---------------------------------------------------------------------
        print("\n[Step 5] Validating catalog package (/api/admin/catalog/validate)...")
        status, body, _ = http_request(
            f"http://127.0.0.1:{SPRING_PORT}/api/admin/catalog/validate",
            method="POST",
            data=rehearsal_catalog,
            headers=auth_header
        )
        assert status == 200 and body.get("valid") is True, f"Validation failed: {status} -> {body}"
        print(f"  Catalog validation SUCCESS (valid: true, item_counts: {body.get('itemCounts')}).")
        results["gates"]["catalog_validation"] = "PASS"

        # ---------------------------------------------------------------------
        # Step 6: Import Package (HTTP Direct)
        # ---------------------------------------------------------------------
        print("\n[Step 6] Importing catalog package (/api/admin/catalog/import)...")
        status, body, _ = http_request(
            f"http://127.0.0.1:{SPRING_PORT}/api/admin/catalog/import",
            method="POST",
            data=rehearsal_catalog,
            headers=auth_header
        )
        assert status == 200 and body.get("success") is True, f"Import failed: {status} -> {body}"
        print(f"  Catalog import SUCCESS (package: {body.get('packageId')}, revision: {body.get('revision')}).")
        results["gates"]["catalog_import"] = "PASS"

        # ---------------------------------------------------------------------
        # Step 7: Worker HTTP Sync & Outbox READY
        # ---------------------------------------------------------------------
        print("\n[Step 7] Awaiting CatalogSyncWorker HTTP sync to FastAPI...")
        ready_snapshot = None
        deadline = time.time() + 90.0
        while time.time() < deadline:
            snap_status, snap_list, _ = http_request(f"http://127.0.0.1:{SPRING_PORT}/api/admin/catalog/snapshots", headers=auth_header)
            if snap_status == 200 and isinstance(snap_list, list) and len(snap_list) > 0:
                latest = snap_list[-1]
                if latest.get("status") == "READY":
                    ready_snapshot = latest
                    break
            time.sleep(1.0)

        assert ready_snapshot is not None, "Outbox snapshot did not reach READY status within deadline"
        committed_gen = ready_snapshot.get("snapshotVersion")
        committed_hash = ready_snapshot.get("contentHash")
        print(f"  Worker sync SUCCESS: outbox status=READY, generation={committed_gen}, hash={committed_hash[:16]}...")
        assert snapshot_path.exists(), f"Snapshot file not persisted at {snapshot_path}"
        results["gates"]["outbox_sync_ready"] = "PASS"
        results["evidence"]["snapshot"] = ready_snapshot

        # ---------------------------------------------------------------------
        # Step 8: Catalog Discovery & Search
        # ---------------------------------------------------------------------
        print("\n[Step 8] Verifying catalog search and discovery...")
        status, series_list, _ = http_request(f"http://127.0.0.1:{SPRING_PORT}/api/catalog/series")
        assert status == 200 and len(series_list) >= 2, f"Expected >= 2 series, got: {len(series_list)}"
        series_ids = [s.get("id") for s in series_list]
        assert "ser_rehearsal_01" in series_ids and "ser_rehearsal_02" in series_ids, f"Series IDs mismatch: {series_ids}"

        status, search_res, _ = http_request(f"http://127.0.0.1:{SPRING_PORT}/api/catalog/search?q=B%E1%BA%A3o")
        assert status == 200 and len(search_res) > 0 and search_res[0].get("id") == "ser_rehearsal_01"
        print(f"  Spring Boot search matched: {search_res[0].get('title')}")

        status, disc_body, _ = http_request(f"http://127.0.0.1:{FASTAPI_PORT}/v1/discover", method="POST", data={"query": "Bảo Thần Tốc"})
        assert status == 200 and len(disc_body.get("results", [])) > 0
        print(f"  FastAPI discover matched {len(disc_body.get('results', []))} items.")
        results["gates"]["catalog_search"] = "PASS"

        # ---------------------------------------------------------------------
        # Step 9: Media Streaming Security Matrix
        # ---------------------------------------------------------------------
        print("\n[Step 9] Verifying Media Streaming Security Matrix...")
        expected_feature_len = (ROOT / "media/synthetic/feature_test.mp4").stat().st_size

        # 9a. Public local stream
        status, _, raw = http_request(f"http://127.0.0.1:{SPRING_PORT}/api/media/stream/asset_feature_01")
        assert status == 200 and len(raw) == expected_feature_len
        print(f"  9a. Public asset stream: 200 OK ({len(raw)} bytes).")

        # 9b. Protected asset anonymous fail-closed
        status, _, _ = http_request(f"http://127.0.0.1:{SPRING_PORT}/api/media/stream/asset_feature_02")
        assert status in (401, 403, 404), f"Protected asset must deny anonymous, got {status}"
        print(f"  9b. Protected asset anonymous access denied (HTTP {status} fail-closed).")

        # 9c. Issue Playback Grant
        status, grant_body, _ = http_request(
            f"http://127.0.0.1:{SPRING_PORT}/api/media/grant/asset_feature_02",
            method="POST",
            headers=auth_header
        )
        assert status == 200 and grant_body.get("grant")
        grant_02 = grant_body["grant"]

        # 9d. Stream with grant
        status, _, raw = http_request(f"http://127.0.0.1:{SPRING_PORT}/api/media/stream/asset_feature_02?grant={grant_02}")
        assert status == 200 and len(raw) == expected_feature_len
        print("  9d. Protected stream with valid grant: 200 OK.")

        # 9e. Grant rejected as Bearer
        status, _, _ = http_request(f"http://127.0.0.1:{SPRING_PORT}/api/admin/catalog/snapshots", headers={"Authorization": f"Bearer {grant_02}"})
        assert status in (401, 403), f"Grant must not act as Bearer token! Got {status}"
        print("  9e. Playback grant rejected as Bearer token (HTTP 401/403).")

        # 9f. Grant strictly asset-bound (rejected on real asset 03)
        status, _, _ = http_request(f"http://127.0.0.1:{SPRING_PORT}/api/media/stream/asset_feature_03?grant={grant_02}")
        assert status in (401, 403, 404), f"Grant 02 must be rejected on asset 03! Got {status}"
        print("  9f. Playback grant asset binding verified: rejected on different asset.")

        # 9g. HTTP Range request on public stream
        status, _, raw = http_request(
            f"http://127.0.0.1:{SPRING_PORT}/api/media/stream/asset_feature_01",
            headers={"Range": "bytes=10000-20000"}
        )
        assert status == 206 and len(raw) == 10001
        print("  9g. HTTP Range bytes=10000-20000: 206 Partial Content (10,001 bytes).")
        results["gates"]["streaming_security_matrix"] = "PASS"

        # ---------------------------------------------------------------------
        # Step 10: Real Google Drive Video Streaming via Spring Boot (Finding R3)
        # ---------------------------------------------------------------------
        print("\n[Step 10] Testing Real Google Drive Video Streaming through Spring Boot (Finding R3)...")
        # 10a. HEAD request for Drive media asset
        status, _, _ = http_request(
            f"http://127.0.0.1:{SPRING_PORT}/api/media/stream/asset_rehearsal_drive",
            method="HEAD"
        )
        # Verify HEAD status 200
        req = urllib.request.Request(f"http://127.0.0.1:{SPRING_PORT}/api/media/stream/asset_rehearsal_drive", method="HEAD")
        with urllib.request.urlopen(req) as resp:
            head_status = resp.status
            head_len = int(resp.headers.get("Content-Length", "0"))
            head_accept_ranges = resp.headers.get("Accept-Ranges", "")
        print(f"  10a. Drive HEAD request: {head_status} OK, Content-Length={head_len:,} bytes, Accept-Ranges={head_accept_ranges}")
        assert head_status == 200 and head_len == 339074277 and head_accept_ranges == "bytes"

        # 10b. Range request for 1MB chunk (bytes 0 to 1,048,575)
        status, _, raw_chunk = http_request(
            f"http://127.0.0.1:{SPRING_PORT}/api/media/stream/asset_rehearsal_drive",
            headers={"Range": "bytes=0-1048575"}
        )
        assert status == 206 and len(raw_chunk) == 1048576, f"Expected 206 Partial Content with 1,048,576 bytes, got {status} ({len(raw_chunk)} bytes)"
        print(f"  10b. Drive Range 206 1MB chunk verified: 206 Partial Content ({len(raw_chunk):,} bytes).")
        time.sleep(2.0)

        # 10c. Near-end chunk (last 1MB of the 339MB file)
        status, err_body, raw_end = http_request(
            f"http://127.0.0.1:{SPRING_PORT}/api/media/stream/asset_rehearsal_drive",
            headers={"Range": "bytes=338000000-339074276"},
            timeout=60.0
        )
        expected_end_len = 339074277 - 338000000
        assert status == 206 and len(raw_end) == expected_end_len, (
            f"Drive near-end range failed: expected 206 with {expected_end_len} bytes, "
            f"got status={status}, len={len(raw_end)}, body={err_body}"
        )
        print(f"  10c. Drive near-end Range chunk verified: 206 Partial Content ({len(raw_end):,} bytes).")
        results["gates"]["drive_media_streaming_http"] = "PASS"
        results["evidence"]["drive_media"] = {
            "asset_id": "asset_rehearsal_drive",
            "file_size": head_len,
            "1mb_chunk_bytes": len(raw_chunk),
            "near_end_chunk_bytes": len(raw_end)
        }

        # ---------------------------------------------------------------------
        # Step 11: Real Browser Automation (Finding R2)
        # ---------------------------------------------------------------------
        print("\n[Step 11] Executing Fail-Closed Browser Automation Suite (scripts/rehearsal_browser_f08.cjs)...")
        browser_script = ROOT / "scripts/rehearsal_browser_f08.cjs"
        browser_res = subprocess.run(
            ["node", str(browser_script), str(FRONTEND_PORT), str(CDP_PORT)],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        print("--- BROWSER SUITE OUTPUT ---")
        print(browser_res.stdout)
        if browser_res.returncode != 0:
            print("--- BROWSER SUITE STDERR ---")
            print(browser_res.stderr)
            raise RuntimeError(f"Browser suite failed with exit code {browser_res.returncode}")

        # Check browser assertions file
        browser_evidence_path = ROOT / "docs/reviews/evidence/CATALOG_01_F08_browser_assertions.json"
        assert browser_evidence_path.exists(), "Browser assertions JSON file was not written"
        browser_data = json.loads(browser_evidence_path.read_text(encoding="utf-8"))
        assert browser_data.get("status") == "PASSED", "Browser suite status is not PASSED"
        results["gates"]["browser_e2e_playback_and_seek"] = "PASS"
        results["evidence"]["browser"] = browser_data

        # ---------------------------------------------------------------------
        # Step 12: First Service Restart Recovery (Durability & Isolation)
        # ---------------------------------------------------------------------
        print("\n[Step 12] Testing First Service Restart Recovery (Spring Boot + FastAPI)...")
        fastapi_proc.terminate()
        try:
            fastapi_proc.wait(timeout=10.0)
        except Exception:
            fastapi_proc.kill()
        fastapi_proc = None

        spring_proc.terminate()
        try:
            spring_proc.wait(timeout=10.0)
        except Exception:
            spring_proc.kill()
        spring_proc = None

        for _ in range(20):
            if not is_port_in_use(FASTAPI_PORT) and not is_port_in_use(SPRING_PORT):
                break
            time.sleep(0.5)
        time.sleep(1.5)

        # Assert state file persisted on disk
        assert fastapi_state_file.exists(), "FastAPI state file missing after shutdown"
        state_data = json.loads(fastapi_state_file.read_text(encoding="utf-8"))
        assert state_data.get("generation") in (committed_gen, committed_gen + 1), f"State generation mismatch: {state_data.get('generation')} not in ({committed_gen}, {committed_gen + 1})"

        # Restart FastAPI
        fa_r1_log = open(temp_dir / "fastapi_restart1.log", "w", encoding="utf-8")
        fastapi_proc = subprocess.Popen(fa_cmd, cwd=str(ROOT / "backend/fastapi"), env=fa_env, stdout=fa_r1_log, stderr=subprocess.STDOUT)
        tracked_pids.append(fastapi_proc.pid)
        assert wait_for_service_ok(f"http://127.0.0.1:{FASTAPI_PORT}/health", max_wait_sec=65.0)

        # Restart Spring Boot
        sb_r1_log = open(temp_dir / "spring_boot_restart1.log", "w", encoding="utf-8")
        spring_proc = subprocess.Popen(spring_args, cwd=str(ROOT / "backend/springboot"), stdout=sb_r1_log, stderr=subprocess.STDOUT)
        tracked_pids.append(spring_proc.pid)
        assert wait_for_service_ok(f"http://127.0.0.1:{SPRING_PORT}/api/health", max_wait_sec=65.0)

        # Verify discovery & catalog queries after restart
        status, disc_after, _ = http_request(f"http://127.0.0.1:{FASTAPI_PORT}/v1/discover", method="POST", data={"query": "Bảo Thần Tốc"})
        assert status == 200 and len(disc_after.get("results", [])) > 0

        status, series_after, _ = http_request(f"http://127.0.0.1:{SPRING_PORT}/api/catalog/series")
        assert status == 200 and len(series_after) >= 2

        # Verify Drive streaming continues working after restart
        status, _, raw_chunk_after = http_request(
            f"http://127.0.0.1:{SPRING_PORT}/api/media/stream/asset_rehearsal_drive",
            headers={"Range": "bytes=0-1048575"}
        )
        assert status == 206 and len(raw_chunk_after) == 1048576
        print("  First restart recovery verified: DB, accepted snapshot, and Drive media streaming preserved.")
        results["gates"]["restart_recovery_1"] = "PASS"

        # ---------------------------------------------------------------------
        # Step 13: Second Service Restart (Durability Double-Check)
        # ---------------------------------------------------------------------
        print("\n[Step 13] Testing Second Service Restart Recovery...")
        fastapi_proc.terminate()
        try:
            fastapi_proc.wait(timeout=10.0)
        except Exception:
            fastapi_proc.kill()
        fastapi_proc = None

        spring_proc.terminate()
        try:
            spring_proc.wait(timeout=10.0)
        except Exception:
            spring_proc.kill()
        spring_proc = None

        for _ in range(20):
            if not is_port_in_use(FASTAPI_PORT) and not is_port_in_use(SPRING_PORT):
                break
            time.sleep(0.5)
        time.sleep(1.5)

        # Restart FastAPI
        fa_r2_log = open(temp_dir / "fastapi_restart2.log", "w", encoding="utf-8")
        fastapi_proc = subprocess.Popen(fa_cmd, cwd=str(ROOT / "backend/fastapi"), env=fa_env, stdout=fa_r2_log, stderr=subprocess.STDOUT)
        tracked_pids.append(fastapi_proc.pid)
        assert wait_for_service_ok(f"http://127.0.0.1:{FASTAPI_PORT}/health", max_wait_sec=65.0)

        # Restart Spring Boot
        sb_r2_log = open(temp_dir / "spring_boot_restart2.log", "w", encoding="utf-8")
        spring_proc = subprocess.Popen(spring_args, cwd=str(ROOT / "backend/springboot"), stdout=sb_r2_log, stderr=subprocess.STDOUT)
        tracked_pids.append(spring_proc.pid)
        assert wait_for_service_ok(f"http://127.0.0.1:{SPRING_PORT}/api/health", max_wait_sec=65.0)

        status, disc_after2, _ = http_request(f"http://127.0.0.1:{FASTAPI_PORT}/v1/discover", method="POST", data={"query": "Bảo Thần Tốc"})
        assert status == 200 and len(disc_after2.get("results", [])) > 0
        results["gates"]["restart_recovery_2"] = "PASS"
        print("  Second restart verification: PASS.")

        results["status"] = "PASSED"
        print("\n" + "=" * 78)
        print("ALL GATES PASSED! FULL PRODUCTION-STACK REHEARSAL SUCCESSFUL (CATALOG-01-F08)")
        print("=" * 78)

    finally:
        print("\n[Teardown] Cleaning up processes by verified PID...")
        for proc in [frontend_proc, fastapi_proc, spring_proc, rclone_proc]:
            if proc is not None:
                try:
                    proc.terminate()
                    proc.wait(timeout=4.0)
                except Exception:
                    try:
                        proc.kill()
                    except Exception:
                        pass

        if results.get("status") != "PASSED":
            for log_name in ["spring_boot.log", "fastapi.log", "frontend.log", "fastapi_restart1.log", "spring_boot_restart1.log"]:
                lp = temp_dir / log_name
                if lp.exists():
                    try:
                        lines = lp.read_text(encoding="utf-8", errors="replace").splitlines()
                        print(f"\n--- TAIL OF {log_name} (last 25 lines) ---")
                        print("\n".join(lines[-25:]))
                    except Exception:
                        pass

        # Cleanup temp directory
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
            print(f"  Cleaned temporary directory: {temp_dir}")
        except Exception as e:
            print(f"  Warning cleaning temp dir: {e}")

    return results


if __name__ == "__main__":
    res = run_rehearsal_f08()
    evidence_path = ROOT / "docs/reviews/evidence/CATALOG_01_F08_rehearsal.json"
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nRehearsal summary written to: {evidence_path}")
    if res.get("status") != "PASSED":
        sys.exit(1)
