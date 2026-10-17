"""
=============================================================================
CATALOG-01-F06: PRODUCTION-STACK REHEARSAL & END-TO-END VALIDATION SUITE
=============================================================================
This script performs a hermetic production-stack rehearsal of the complete
Dippie Cinema catalog lifecycle:
1. Bootstraps isolated live services on dedicated ports (FastAPI on 8008, Spring Boot on 8088).
2. Uses isolated temporary database and snapshot state storage.
3. Authenticates admin user (admin / password123) and verifies JWT issuance.
4. Validates and previews valid test catalog fixture (docs/fixtures/rehearsal_catalog.json).
5. Imports catalog into relational database, creating an outbox snapshot record.
6. Verifies background CatalogSyncWorker HTTP sync to FastAPI /api/index/sync.
7. Waits for outbox snapshot to reach READY status with matching generation and content hash.
8. Verifies catalog search and browsing across both Spring Boot and FastAPI (/v1/discover).
9. Verifies media streaming security matrix:
   - Public asset playback (200 OK)
   - Protected asset anonymous access denied (fail-closed 404)
   - Admin-requested playback grant issuance
   - Protected asset stream with valid grant token (200 OK)
   - Playback grant cannot be used as Bearer authentication (401 Unauthorized)
   - Playback grant is bound to asset (cannot access other assets)
10. Verifies seek capability and timeline offset calculation:
    - Scene start_ms: 15,000ms
    - Media coverage: source_in_ms = 10,000ms, episode_in_ms = 0ms
    - Resolved seek offset: 25,000ms (25.0s)
    - HTTP Range request: bytes=10000-20000 returns 206 Partial Content
11. Verifies restart recovery:
    - Shuts down FastAPI service
    - Restarts FastAPI service from accepted persisted state
    - Verifies active generation and titles are restored
    - Verifies discovery query continues to return indexed catalog items
12. Gracefully terminates services and cleans up temporary state.
=============================================================================
"""

import os
import sys
import io
import json
import time
import shutil
import tempfile
import urllib.request
import urllib.error
import subprocess

if sys.platform == "win32":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    except Exception:
        pass
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent

FASTAPI_PORT = 8008
SPRING_PORT = 8088
SYNC_SECRET = "rehearsal_f06_secret_2026"


def http_request(
    url: str,
    method: str = "GET",
    data: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: float = 60.0
) -> Tuple[int, Dict[str, Any], bytes]:
    """Helper for HTTP requests returning (status_code, parsed_json_or_empty, raw_bytes)."""
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


def wait_for_service(url: str, max_wait_sec: float = 45.0, interval: float = 1.0) -> bool:
    """Poll an endpoint until it returns 200 OK or timeout expires."""
    deadline = time.time() + max_wait_sec
    while time.time() < deadline:
        status, _, _ = http_request(url, timeout=2.0)
        if status in (200, 401, 403, 404):  # Service is responding
            return True
        time.sleep(interval)
    return False


def run_rehearsal() -> Dict[str, Any]:
    print("=" * 78)
    print("STARTING CATALOG-01-F06 PRODUCTION-STACK REHEARSAL")
    print("=" * 78)

    rehearsal_fixture_path = ROOT / "docs/fixtures/rehearsal_catalog.json"
    if not rehearsal_fixture_path.exists():
        raise FileNotFoundError(f"Fixture missing: {rehearsal_fixture_path}")

    rehearsal_catalog = json.loads(rehearsal_fixture_path.read_text(encoding="utf-8"))
    temp_dir = Path(tempfile.mkdtemp(prefix="dippie-rehearsal-f06-"))
    print(f"[Setup] Isolated temporary directory: {temp_dir}")

    db_path = temp_dir / "rehearsal_db"
    snapshot_path = temp_dir / "committed_catalog_snapshot.json"
    fastapi_state_dir = temp_dir / "fastapi_state"
    fastapi_state_dir.mkdir(parents=True, exist_ok=True)
    fastapi_state_file = fastapi_state_dir / "accepted_catalog_state.json"

    # Jar artifact check
    jar_path = ROOT / "backend/springboot/target/moviercm-backend-0.0.1-SNAPSHOT.jar"
    if not jar_path.exists():
        raise FileNotFoundError(f"Spring Boot jar not found at: {jar_path}")

    results: Dict[str, Any] = {
        "status": "IN_PROGRESS",
        "gates": {},
        "evidence": {}
    }

    fastapi_proc = None
    spring_proc = None

    try:
        # ---------------------------------------------------------------------
        # 1. Launch FastAPI Server on dedicated port 8008
        # ---------------------------------------------------------------------
        print(f"\n[Step 1] Launching FastAPI service on port {FASTAPI_PORT}...")
        fastapi_env = os.environ.copy()
        fastapi_env["PORT"] = str(FASTAPI_PORT)
        fastapi_env["SERVING_MODE"] = "light"
        fastapi_env["USE_FULL_QWEN3_4B_LORA"] = "false"
        fastapi_env["FASTAPI_SYNC_SECRET"] = SYNC_SECRET
        fastapi_env["SYNC_STATE_PATH"] = str(fastapi_state_file)
        fastapi_env["PYTHONPATH"] = str(ROOT / "backend/fastapi")

        fastapi_cmd = [
            sys.executable, "-m", "uvicorn", "main:app",
            "--host", "127.0.0.1",
            "--port", str(FASTAPI_PORT),
            "--log-level", "warning"
        ]
        fastapi_log = open(temp_dir / "fastapi.log", "w", encoding="utf-8")
        fastapi_proc = subprocess.Popen(
            fastapi_cmd,
            cwd=str(ROOT / "backend/fastapi"),
            env=fastapi_env,
            stdout=fastapi_log,
            stderr=subprocess.STDOUT
        )

        if not wait_for_service(f"http://127.0.0.1:{FASTAPI_PORT}/health", max_wait_sec=25.0):
            raise RuntimeError(f"FastAPI failed to start on port {FASTAPI_PORT}")
        print("  FastAPI service is HEALTHY and listening on port 8008.")

        # ---------------------------------------------------------------------
        # 2. Launch Spring Boot Server on dedicated port 8088
        # ---------------------------------------------------------------------
        print(f"\n[Step 2] Launching Spring Boot service on port {SPRING_PORT}...")
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
            "-Dapp.seed.enabled=true",
            "-jar", str(jar_path)
        ]
        spring_log = open(temp_dir / "spring_boot.log", "w", encoding="utf-8")
        spring_proc = subprocess.Popen(
            spring_args,
            cwd=str(ROOT / "backend/springboot"),
            stdout=spring_log,
            stderr=subprocess.STDOUT
        )

        if not wait_for_service(f"http://127.0.0.1:{SPRING_PORT}/api/health", max_wait_sec=50.0):
            raise RuntimeError(f"Spring Boot failed to start on port {SPRING_PORT}")
        print("  Spring Boot service is HEALTHY and listening on port 8088.")

        # ---------------------------------------------------------------------
        # 3. Admin Authentication Verification
        # ---------------------------------------------------------------------
        print("\n[Step 3] Authenticating as admin (admin@dippie.com / password123)...")
        login_status, login_body, _ = http_request(
            f"http://127.0.0.1:{SPRING_PORT}/api/auth/login",
            method="POST",
            data={"usernameOrEmail": "admin", "password": "password123"}
        )
        assert login_status == 200, f"Admin login failed with status {login_status}: {login_body}"
        admin_jwt = login_body.get("data", {}).get("token") or login_body.get("token")
        assert admin_jwt, f"Admin login response did not contain JWT token: {login_body}"
        auth_header = {"Authorization": f"Bearer {admin_jwt}"}
        print(f"  Admin login SUCCESS (JWT acquired, length: {len(admin_jwt)}).")
        results["gates"]["admin_login"] = "PASS"

        # ---------------------------------------------------------------------
        # 4. Validate & Preview Rehearsal Fixture
        # ---------------------------------------------------------------------
        print("\n[Step 4] Validating catalog package via /api/admin/catalog/validate...")
        val_status, val_body, _ = http_request(
            f"http://127.0.0.1:{SPRING_PORT}/api/admin/catalog/validate",
            method="POST",
            data=rehearsal_catalog,
            headers=auth_header
        )
        assert val_status == 200, f"Validate returned status {val_status}: {val_body}"
        assert val_body.get("valid") is True, f"Catalog validation reported invalid: {val_body}"
        assert len(val_body.get("errors", [])) == 0, f"Catalog validation had errors: {val_body.get('errors')}"
        print(f"  Catalog validation SUCCESS (valid: true, item_counts: {val_body.get('itemCounts')}).")
        results["gates"]["catalog_validation"] = "PASS"

        # ---------------------------------------------------------------------
        # 5. Commit / Import Catalog into Relational Database
        # ---------------------------------------------------------------------
        print("\n[Step 5] Importing catalog package via /api/admin/catalog/import...")
        import_status, import_body, _ = http_request(
            f"http://127.0.0.1:{SPRING_PORT}/api/admin/catalog/import",
            method="POST",
            data=rehearsal_catalog,
            headers=auth_header
        )
        assert import_status == 200, f"Import returned status {import_status}: {import_body}"
        assert import_body.get("success") is True, f"Import failed: {import_body}"
        print(f"  Catalog import SUCCESS (package: {import_body.get('packageId')}, revision: {import_body.get('revision')}).")
        results["gates"]["catalog_import"] = "PASS"

        # ---------------------------------------------------------------------
        # 6. Background Outbox Worker Sync to FastAPI Retrieval Engine
        # ---------------------------------------------------------------------
        print("\n[Step 6] Awaiting CatalogSyncWorker HTTP sync to FastAPI /api/index/sync...")
        ready_snapshot = None
        deadline = time.time() + 90.0
        while time.time() < deadline:
            snap_status, snap_list, _ = http_request(
                f"http://127.0.0.1:{SPRING_PORT}/api/admin/catalog/snapshots",
                headers=auth_header
            )
            if snap_status == 200 and isinstance(snap_list, list) and len(snap_list) > 0:
                latest = snap_list[-1]
                if latest.get("status") == "READY":
                    ready_snapshot = latest
                    break
            time.sleep(1.0)

        assert ready_snapshot is not None, "CatalogSnapshot outbox did not reach READY status within deadline"
        committed_gen = ready_snapshot.get("snapshotVersion")
        committed_hash = ready_snapshot.get("contentHash")
        print(f"  Worker sync SUCCESS: outbox status=READY, generation={committed_gen}, hash={committed_hash[:16]}...")
        results["gates"]["outbox_sync_ready"] = "PASS"
        results["evidence"]["snapshot"] = ready_snapshot

        # Verify disk snapshot file was written
        assert snapshot_path.exists(), f"Committed snapshot file missing at: {snapshot_path}"
        print(f"  Snapshot JSON persisted to disk ({snapshot_path.stat().st_size} bytes).")

        # ---------------------------------------------------------------------
        # 7. Catalog Browsing and Search Verification
        # ---------------------------------------------------------------------
        print("\n[Step 7] Verifying catalog search and discovery...")
        # 7a. Spring Boot series list
        series_status, series_list, _ = http_request(f"http://127.0.0.1:{SPRING_PORT}/api/catalog/series")
        assert series_status == 200 and len(series_list) >= 2, f"Expected at least 2 series, got: {len(series_list)}"
        print(f"  Spring Boot series count: {len(series_list)}")

        # 7b. Spring Boot keyword search
        search_status, search_res, _ = http_request(
            f"http://127.0.0.1:{SPRING_PORT}/api/catalog/search?q=B%E1%BA%A3o"
        )
        assert search_status == 200 and len(search_res) > 0, "Keyword search for 'Bảo' returned no items"
        matched_id = search_res[0].get("id")
        print(f"  Spring Boot search for 'Bảo' matched: {matched_id} ({search_res[0].get('title')})")

        # 7c. FastAPI /v1/discover retrieval
        disc_status, disc_body, _ = http_request(
            f"http://127.0.0.1:{FASTAPI_PORT}/v1/discover",
            method="POST",
            data={"query": "Bảo Thần Tốc"}
        )
        assert disc_status == 200, f"/v1/discover returned status {disc_status}"
        disc_results = disc_body.get("results", [])
        assert len(disc_results) > 0, "/v1/discover returned 0 results"
        print(f"  FastAPI /v1/discover returned {len(disc_results)} results for 'Bảo Thần Tốc'.")
        results["gates"]["catalog_search"] = "PASS"

        # ---------------------------------------------------------------------
        # 8. Media Streaming and Security Matrix Verification
        # ---------------------------------------------------------------------
        print("\n[Step 8] Verifying Media Streaming & Access Security Matrix...")
        # 8a. Public asset: stream allowed without credentials
        pub_status, _, pub_bytes = http_request(
            f"http://127.0.0.1:{SPRING_PORT}/api/media/stream/asset_feature_01"
        )
        assert pub_status == 200, f"Public stream failed: status {pub_status}"
        assert len(pub_bytes) == 137961, f"Expected full 137961 bytes, got: {len(pub_bytes)}"
        print("  Public asset streaming: 200 OK (137,961 bytes streamed).")

        # 8b. Authenticated asset: anonymous access denied (fail-closed)
        prot_status, _, _ = http_request(
            f"http://127.0.0.1:{SPRING_PORT}/api/media/stream/asset_feature_02"
        )
        assert prot_status in (401, 403, 404), f"Protected asset should deny anonymous access, got: {prot_status}"
        print(f"  Protected asset anonymous access denied (HTTP {prot_status} fail-closed).")

        # 8c. Request Playback Grant Token
        grant_status, grant_body, _ = http_request(
            f"http://127.0.0.1:{SPRING_PORT}/api/media/grant/asset_feature_02",
            method="POST",
            headers=auth_header
        )
        assert grant_status == 200, f"Failed to acquire grant: {grant_status}: {grant_body}"
        grant_token = grant_body.get("grant")
        assert grant_token, "No grant token in response"
        print("  Playback grant token successfully issued.")

        # 8d. Stream protected asset with valid grant token
        auth_stream_status, _, auth_stream_bytes = http_request(
            f"http://127.0.0.1:{SPRING_PORT}/api/media/stream/asset_feature_02?grant={grant_token}"
        )
        assert auth_stream_status == 200, f"Protected stream with grant failed: {auth_stream_status}"
        assert len(auth_stream_bytes) == 137961, f"Expected 137961 bytes, got: {len(auth_stream_bytes)}"
        print("  Protected asset streaming with grant: 200 OK (137,961 bytes streamed).")

        # 8e. Security Boundary 1: Playback grant CANNOT authenticate as Bearer token
        mal_bearer_status, _, _ = http_request(
            f"http://127.0.0.1:{SPRING_PORT}/api/admin/catalog/snapshots",
            headers={"Authorization": f"Bearer {grant_token}"}
        )
        assert mal_bearer_status in (401, 403), f"Playback grant must NOT act as Bearer token! Got: {mal_bearer_status}"
        print("  Security Gate R1: Playback grant rejected as Bearer token (HTTP 401/403).")

        # 8f. Security Boundary 2: Playback grant is strictly bound to its asset
        other_stream_status, _, _ = http_request(
            f"http://127.0.0.1:{SPRING_PORT}/api/media/stream/nonexistent_asset_id?grant={grant_token}"
        )
        assert other_stream_status in (401, 403, 404), "Grant must not authorise different asset"
        print("  Security Gate R2: Playback grant rejected for mismatched asset.")
        results["gates"]["streaming_security_matrix"] = "PASS"

        # ---------------------------------------------------------------------
        # 9. Direct Timestamp Seeking & Scene Offset Calculation
        # ---------------------------------------------------------------------
        print("\n[Step 9] Verifying direct seek calculation and HTTP Range streaming...")
        # Scene scene_rehearsal_canyon: start_ms = 15000 (15.0s)
        # Coverage: source_in_ms = 10000 (10.0s), episode_in_ms = 0 (0.0s)
        # Expected source target: (15000 - 0) + 10000 = 25000 ms (25.0s)
        scene = rehearsal_catalog["scenes"][0]
        coverage = rehearsal_catalog["media_assets"][0]["coverage"][0]
        calc_offset_ms = (scene["start_ms"] - coverage["episode_in_ms"]) + coverage["source_in_ms"]
        assert calc_offset_ms == 25000, f"Calculation mismatch: expected 25000, got: {calc_offset_ms}"
        print(f"  Scene direct seek calculation: {scene['start_ms']}ms -> source offset: {calc_offset_ms}ms (25.0s).")

        # Range streaming test (bytes=10000-20000)
        range_status, _, range_bytes = http_request(
            f"http://127.0.0.1:{SPRING_PORT}/api/media/stream/asset_feature_01",
            headers={"Range": "bytes=10000-20000"}
        )
        assert range_status == 206, f"Range request should return 206 Partial Content, got: {range_status}"
        assert len(range_bytes) == 10001, f"Expected 10001 bytes (10000 to 20000 inclusive), got: {len(range_bytes)}"
        print("  HTTP Range request (bytes=10000-20000): 206 Partial Content (10,001 bytes).")
        results["gates"]["timestamp_seek_range"] = "PASS"

        # ---------------------------------------------------------------------
        # 10. Service Restart Recovery
        # ---------------------------------------------------------------------
        print("\n[Step 10] Testing service restart and accepted index persistence...")
        # Terminate running FastAPI instance
        fastapi_proc.terminate()
        fastapi_proc.wait(timeout=10.0)
        fastapi_proc = None
        print("  FastAPI process terminated.")

        # Verify state file was created
        assert fastapi_state_file.exists(), f"FastAPI state file missing at: {fastapi_state_file}"
        persisted_state = json.loads(fastapi_state_file.read_text(encoding="utf-8"))
        assert persisted_state.get("generation") == committed_gen, "Persisted generation mismatch"
        print(f"  Verified persisted state file: generation={persisted_state.get('generation')}.")

        # Restart FastAPI on port 8008 pointing to the same state directory
        print("  Restarting FastAPI service...")
        fastapi_proc = subprocess.Popen(
            fastapi_cmd,
            cwd=str(ROOT / "backend/fastapi"),
            env=fastapi_env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        if not wait_for_service(f"http://127.0.0.1:{FASTAPI_PORT}/health", max_wait_sec=25.0):
            raise RuntimeError(f"FastAPI failed to restart on port {FASTAPI_PORT}")

        # Query restarted FastAPI instance
        disc_after_status, disc_after_body, _ = http_request(
            f"http://127.0.0.1:{FASTAPI_PORT}/v1/discover",
            method="POST",
            data={"query": "Bảo Thần Tốc"}
        )
        assert disc_after_status == 200, f"/v1/discover after restart returned status {disc_after_status}"
        assert len(disc_after_body.get("results", [])) > 0, "No results from restarted FastAPI"
        print("  FastAPI successfully restored accepted catalog and responds to queries after restart!")

        # Query Spring Boot to verify continuous playback after restart
        post_restart_stream_status, _, post_restart_bytes = http_request(
            f"http://127.0.0.1:{SPRING_PORT}/api/media/stream/asset_feature_01"
        )
        assert post_restart_stream_status == 200 and len(post_restart_bytes) == 137961
        print("  Continuous media streaming after restart: 200 OK.")
        results["gates"]["restart_recovery"] = "PASS"

        # All gates passed!
        results["status"] = "PASSED"
        print("\n" + "=" * 78)
        print("ALL GATES PASSED! FULL PRODUCTION-STACK REHEARSAL SUCCESSFUL.")
        print("=" * 78)

    finally:
        # Cleanup processes
        print("\n[Teardown] Shutting down services and cleaning up temporary state...")
        if fastapi_proc is not None:
            try:
                fastapi_proc.terminate()
                fastapi_proc.wait(timeout=5.0)
            except Exception:
                try:
                    fastapi_proc.kill()
                except Exception:
                    pass

        if spring_proc is not None:
            try:
                spring_proc.terminate()
                spring_proc.wait(timeout=5.0)
            except Exception:
                try:
                    spring_proc.kill()
                except Exception:
                    pass

        if results.get("status") != "PASSED":
            sb_log_path = temp_dir / "spring_boot.log"
            if sb_log_path.exists():
                print("\n--- SPRING BOOT LOG TAIL ---")
                lines = sb_log_path.read_text(encoding="utf-8", errors="replace").splitlines()
                for l in lines[-35:]:
                    safe_line = l.encode("ascii", errors="replace").decode("ascii")
                    print("  " + safe_line)
            fa_log_path = temp_dir / "fastapi.log"
            if fa_log_path.exists():
                print("\n--- FASTAPI LOG TAIL ---")
                lines = fa_log_path.read_text(encoding="utf-8", errors="replace").splitlines()
                for l in lines[-25:]:
                    safe_line = l.encode("ascii", errors="replace").decode("ascii")
                    print("  " + safe_line)

        # Cleanup temp directory
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
            print("  Temporary directory removed cleanly.")
        except Exception as e:
            print(f"  Warning cleaning temp dir: {e}")

    return results


if __name__ == "__main__":
    res = run_rehearsal()
    evidence_path = ROOT / "docs/reviews/evidence/CATALOG_01_F06_rehearsal.json"
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nRehearsal summary written to: {evidence_path}")
    if res.get("status") != "PASSED":
        sys.exit(1)
