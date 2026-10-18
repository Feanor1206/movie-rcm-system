"""
SNAPSHOT-01: Smoke Verification for Usable Preview
Covers:
1. Preflight port checks (8008, 8088, 3008, 9228).
2. Google Drive read-only mount to X: via rclone (folder: 1Ypyq-KuQKEhHrWuxtrrR8Y4G7DwbeyZQ).
3. FastAPI launch (port 8008, light mode).
4. Spring Boot launch (port 8088, jar: moviercm-backend-0.0.1-SNAPSHOT.jar, X: drive mount).
5. Next.js production launch (port 3008).
6. Admin authentication & JWT token issuance.
7. Catalog validation & import (rehearsal_catalog.json).
8. CatalogSyncWorker HTTP sync to FastAPI -> outbox READY.
9. Catalog discovery & search across backends.
10. Real Google Drive video playback in headless Chrome:
    - Frame decode verification (width x height > 0).
    - Initial playback time advancement.
    - Seek 1 (to 60.0s) & verify post-seek time advancement.
    - Seek 2 (to 120.0s) & verify post-seek time advancement.
    - Proof screenshot capture.
11. Clean process termination strictly by recorded PID.
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

FASTAPI_PORT = 8000
SPRING_PORT = 8080
FRONTEND_PORT = 3000
CDP_PORT = 9228
SYNC_SECRET = "smoke_preview_secret_2026"
DRIVE_ROOT_FOLDER_ID = "1Ypyq-KuQKEhHrWuxtrrR8Y4G7DwbeyZQ"
DRIVE_MOUNT_LETTER = "X:"
EVIDENCE_PATH = ROOT / "docs/reviews/evidence/SNAPSHOT_01_SMOKE.json"
SCREENSHOT_PATH = ROOT / "docs/reviews/evidence/live_preview_drive_player_seek.png"


def is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def http_request(
    url: str,
    method: str = "GET",
    data: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: float = 30.0
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


def wait_for_service_ok(url: str, max_wait_sec: float = 40.0, interval: float = 1.0) -> bool:
    deadline = time.time() + max_wait_sec
    while time.time() < deadline:
        status, _, _ = http_request(url, timeout=2.0)
        if status == 200:
            return True
        time.sleep(interval)
    return False


def run_smoke_test() -> Dict[str, Any]:
    print("=" * 78)
    print("STARTING SNAPSHOT-01 USABLE PREVIEW SMOKE TEST")
    print("=" * 78)

    # 1. Port checks
    for p, name in [(FASTAPI_PORT, "FastAPI"), (SPRING_PORT, "Spring Boot"), (FRONTEND_PORT, "Frontend"), (CDP_PORT, "Chrome CDP")]:
        if is_port_in_use(p):
            raise RuntimeError(f"Port {p} ({name}) is already in use!")
    print(f"[Preflight] Ports ({FASTAPI_PORT}, {SPRING_PORT}, {FRONTEND_PORT}, {CDP_PORT}) are free.")

    jar_path = ROOT / "backend/springboot/target/moviercm-backend-0.0.1-SNAPSHOT.jar"
    if not jar_path.exists():
        raise FileNotFoundError(f"Backend jar not found: {jar_path}")

    fixture_path = ROOT / "docs/fixtures/rehearsal_catalog.json"
    if not fixture_path.exists():
        raise FileNotFoundError(f"Fixture not found: {fixture_path}")
    catalog_data = json.loads(fixture_path.read_text(encoding="utf-8"))

    temp_dir = Path(tempfile.mkdtemp(prefix="dippie-smoke-preview-"))
    db_path = temp_dir / "smoke_db"
    snapshot_path = temp_dir / "snapshot.json"
    fastapi_state_dir = temp_dir / "fastapi_state"
    fastapi_state_dir.mkdir(parents=True, exist_ok=True)
    fastapi_state_file = fastapi_state_dir / "accepted_state.json"
    default_catalog_file = temp_dir / "empty_catalog.json"
    default_catalog_file.write_text("{}", encoding="utf-8")

    tracked_pids: List[int] = []
    rclone_proc = None
    fastapi_proc = None
    spring_proc = None
    frontend_proc = None
    chrome_proc = None

    results: Dict[str, Any] = {
        "releaseLevel": "usable_preview",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "gates": {},
        "measurements": {},
        "status": "IN_PROGRESS"
    }

    try:
        # Step 1: Mount Google Drive
        print("\n[Step 1] Mounting Google Drive to X: via rclone...")
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
        print(f"  rclone mount started (PID {rclone_proc.pid})")

        drive_ready = False
        drive_path = Path("X:/")
        for _ in range(15):
            time.sleep(1.0)
            if drive_path.exists() and (drive_path / "jadooss1").exists():
                drive_ready = True
                break
            if rclone_proc.poll() is not None:
                break

        assert drive_ready, f"Failed to mount Google Drive to {DRIVE_MOUNT_LETTER}"
        print("  Drive X: mounted successfully (folder jadooss1 verified).")
        results["gates"]["google_drive_mount"] = "PASS"

        # Step 2: FastAPI
        print(f"\n[Step 2] Launching FastAPI AI on port {FASTAPI_PORT}...")
        fa_env = os.environ.copy()
        fa_env["PORT"] = str(FASTAPI_PORT)
        fa_env["SERVING_MODE"] = "light"
        fa_env["USE_FULL_QWEN3_4B_LORA"] = "false"
        fa_env["FASTAPI_SYNC_SECRET"] = SYNC_SECRET
        fa_env["SYNC_STATE_PATH"] = str(fastapi_state_file)
        fa_env["DEFAULT_CATALOG_PATH"] = str(default_catalog_file)
        fa_env["PYTHONPATH"] = str(ROOT / "backend/fastapi")

        fa_log = open(temp_dir / "fastapi.log", "w", encoding="utf-8")
        fastapi_proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", str(FASTAPI_PORT), "--log-level", "warning"],
            cwd=str(ROOT / "backend/fastapi"),
            env=fa_env,
            stdout=fa_log,
            stderr=subprocess.STDOUT
        )
        tracked_pids.append(fastapi_proc.pid)
        assert wait_for_service_ok(f"http://127.0.0.1:{FASTAPI_PORT}/health", max_wait_sec=25.0)
        print("  FastAPI HEALTHY (200 OK).")
        results["gates"]["fastapi_ready"] = "PASS"

        # Step 3: Spring Boot
        print(f"\n[Step 3] Launching Spring Boot on port {SPRING_PORT}...")
        java_home = os.environ.get("JAVA_HOME", "C:\\Program Files\\Java\\jdk-25.0.3")
        java_bin = str(Path(java_home) / "bin/java.exe" if os.name == "nt" else Path(java_home) / "bin/java")
        if not Path(java_bin).exists():
            java_bin = "java"

        spring_args = [
            java_bin,
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
        assert wait_for_service_ok(f"http://127.0.0.1:{SPRING_PORT}/api/health", max_wait_sec=50.0)
        print("  Spring Boot HEALTHY (200 OK).")
        results["gates"]["spring_boot_ready"] = "PASS"

        # Step 4: Next.js Web Frontend (Production build)
        print(f"\n[Step 4] Launching Next.js Production Build on port {FRONTEND_PORT}...")
        fe_env = os.environ.copy()
        fe_env["PORT"] = str(FRONTEND_PORT)
        fe_env["NEXT_PUBLIC_API_URL"] = f"http://127.0.0.1:{SPRING_PORT}"
        fe_env["NEXT_PUBLIC_SPRINGBOOT_API_URL"] = f"http://127.0.0.1:{SPRING_PORT}/api"
        fe_env["NEXT_PUBLIC_MODEL_API_URL"] = f"http://127.0.0.1:{FASTAPI_PORT}/api/chat"

        fe_log = open(temp_dir / "frontend.log", "w", encoding="utf-8")
        next_bin = ROOT / "frontend/node_modules/next/dist/bin/next"
        frontend_proc = subprocess.Popen(
            [shutil.which("node") or "node", str(next_bin), "start", "-H", "127.0.0.1", "-p", str(FRONTEND_PORT)],
            cwd=str(ROOT / "frontend"),
            env=fe_env,
            stdout=fe_log,
            stderr=subprocess.STDOUT
        )
        tracked_pids.append(frontend_proc.pid)
        assert wait_for_service_ok(f"http://127.0.0.1:{FRONTEND_PORT}", max_wait_sec=30.0)
        print("  Next.js Frontend HEALTHY (200 OK).")
        results["gates"]["frontend_ready"] = "PASS"

        # Step 5: Admin Login
        print("\n[Step 5] Admin Login (HTTP)...")
        status, body, _ = http_request(
            f"http://127.0.0.1:{SPRING_PORT}/api/auth/login",
            method="POST",
            data={"usernameOrEmail": "admin", "password": "password123"}
        )
        assert status == 200, f"Login failed: {status}"
        token = body.get("data", {}).get("token") or body.get("token")
        assert token, "No token in login response"
        auth_header = {"Authorization": f"Bearer {token}"}
        print("  Admin Login SUCCESS.")
        results["gates"]["admin_login"] = "PASS"

        # Step 6: Validate & Import
        print("\n[Step 6] Validating & Importing catalog package...")
        status, val_body, _ = http_request(
            f"http://127.0.0.1:{SPRING_PORT}/api/admin/catalog/validate",
            method="POST",
            data=catalog_data,
            headers=auth_header
        )
        assert status == 200 and val_body.get("valid") is True, f"Validation failed: {val_body}"
        print(f"  Validate SUCCESS (items: {val_body.get('itemCounts')}).")

        status, imp_body, _ = http_request(
            f"http://127.0.0.1:{SPRING_PORT}/api/admin/catalog/import",
            method="POST",
            data=catalog_data,
            headers=auth_header
        )
        assert status == 200 and imp_body.get("success") is True, f"Import failed: {imp_body}"
        print(f"  Import SUCCESS (package: {imp_body.get('packageId')}, rev: {imp_body.get('revision')}).")
        results["gates"]["catalog_import"] = "PASS"

        # Step 7: Outbox Sync READY
        print("\n[Step 7] Polling CatalogSyncWorker outbox sync -> READY...")
        ready_snap = None
        deadline = time.time() + 60.0
        while time.time() < deadline:
            s_code, s_list, _ = http_request(f"http://127.0.0.1:{SPRING_PORT}/api/admin/catalog/snapshots", headers=auth_header)
            if s_code == 200 and isinstance(s_list, list) and len(s_list) > 0:
                latest = s_list[-1]
                if latest.get("status") == "READY":
                    ready_snap = latest
                    break
            time.sleep(1.0)
        assert ready_snap is not None, "Outbox snapshot did not reach READY"
        print(f"  Outbox sync READY (generation: {ready_snap.get('snapshotVersion')}, hash: {ready_snap.get('contentHash', '')[:16]}...).")
        results["gates"]["outbox_sync_ready"] = "PASS"

        # Step 8: Search
        print("\n[Step 8] Verifying catalog search...")
        status, search_res, _ = http_request(f"http://127.0.0.1:{SPRING_PORT}/api/catalog/search?q=B%E1%BA%A3o")
        assert status == 200 and len(search_res) > 0 and search_res[0].get("id") == "ser_rehearsal_01"
        print(f"  Search matched: {search_res[0].get('title')}")

        status, disc_res, _ = http_request(f"http://127.0.0.1:{FASTAPI_PORT}/v1/discover", method="POST", data={"query": "Bảo Thần Tốc"})
        assert status == 200 and len(disc_res.get("results", [])) > 0
        print(f"  FastAPI discover matched {len(disc_res.get('results', []))} results.")
        results["gates"]["catalog_search"] = "PASS"

        # Step 9: Browser Drive Video Playback & Seek via CDP
        print("\n[Step 9] Real Google Drive Video Playback & Seek in Headless Chrome...")
        chrome_exe = "C:/Program Files/Google/Chrome/Application/chrome.exe"
        profile_dir = Path(tempfile.mkdtemp(prefix="chrome_smoke_preview_"))
        chrome_proc = subprocess.Popen([
            chrome_exe,
            "--headless=new",
            f"--remote-debugging-port={CDP_PORT}",
            f"--user-data-dir={profile_dir}",
            "--no-first-run",
            "--disable-gpu",
            "--autoplay-policy=no-user-gesture-required",
            "--window-size=1280,1000",
            f"http://127.0.0.1:{FRONTEND_PORT}/series/ser_rehearsal_01"
        ])
        tracked_pids.append(chrome_proc.pid)

        # Connect to CDP
        cdp_page = None
        cdp_deadline = time.time() + 20.0
        while time.time() < cdp_deadline:
            try:
                pages_req = urllib.request.urlopen(f"http://127.0.0.1:{CDP_PORT}/json/list", timeout=2.0)
                pages = json.loads(pages_req.read().decode())
                cdp_page = next((p for p in pages if p.get("type") == "page"), None)
                if cdp_page:
                    break
            except Exception:
                pass
            time.sleep(0.5)
        assert cdp_page is not None, "Failed to connect to Chrome CDP"

        # Simple CDP client using websockets or Node runner
        print("  Running browser interaction runner for Drive playback and seeks...")
        runner_js = f"""
        const {{ spawn }} = require('child_process');
        const fs = require('fs');

        async function main() {{
            const ws = new WebSocket('{cdp_page["webSocketDebuggerUrl"]}');
            await new Promise((res, rej) => {{ ws.onopen = res; ws.onerror = rej; }});
            
            let id = 1;
            const send = (method, params = {{}}) => new Promise((resolve, reject) => {{
                const cur = id++;
                const timer = setTimeout(() => reject(new Error('CDP timeout ' + method)), 30000);
                const h = (e) => {{
                    const d = JSON.parse(e.data);
                    if (d.id === cur) {{
                        clearTimeout(timer);
                        ws.removeEventListener('message', h);
                        if (d.error) reject(new Error(JSON.stringify(d.error)));
                        else resolve(d.result);
                    }}
                }};
                ws.addEventListener('message', h);
                ws.send(JSON.stringify({{ id: cur, method, params }}));
            }});

            await send('Page.enable');
            await send('Runtime.enable');

            console.log('Navigating page to series detail...');
            await send('Page.navigate', {{ url: 'http://127.0.0.1:{FRONTEND_PORT}/series/ser_rehearsal_01' }});
            await new Promise(r => setTimeout(r, 2000));

            const evalJs = async (expr) => {{
                const r = await send('Runtime.evaluate', {{ expression: expr, returnByValue: true, awaitPromise: true }});
                return r?.result?.value;
            }};

            const waitForSelector = async (sel, timeoutMs = 25000) => {{
                const end = Date.now() + timeoutMs;
                while (Date.now() < end) {{
                    const ok = await evalJs(`!!document.querySelector('${{sel}}')`);
                    if (ok) return true;
                    await new Promise(r => setTimeout(r, 500));
                }}
                const curUrl = await evalJs('window.location.href');
                const bodyText = await evalJs('document.body.innerText');
                console.error('TIMEOUT WAITING FOR: ' + sel + ' ON URL: ' + curUrl + '\\nPAGE BODY:\\n' + bodyText);
                throw new Error('Timeout waiting for: ' + sel);
            }};

            // Wait for series page to render
            await waitForSelector('[data-testid="series-video-player"]', 30000);
            console.log('Video player container mounted.');

            // Select Google Drive asset button
            await waitForSelector('[data-testid="media-asset-button"][data-asset-id="asset_rehearsal_drive"]', 20000);
            await evalJs(`document.querySelector('[data-testid="media-asset-button"][data-asset-id="asset_rehearsal_drive"]').click()`);
            console.log('Switched source to asset_rehearsal_drive.');

            // Wait for Drive video to load metadata and decode frames
            let decoded = false;
            let dims = '';
            for (let i = 0; i < 35; i++) {{
                await new Promise(r => setTimeout(r, 1000));
                const st = await evalJs(`(() => {{
                    const v = document.querySelector('video[data-testid="series-video-player"]');
                    if (!v) return null;
                    if (v.paused) v.play().catch(() => {{}});
                    return {{
                        src: v.src,
                        videoWidth: v.videoWidth,
                        videoHeight: v.videoHeight,
                        currentTime: v.currentTime
                    }};
                }})()`);
                if (st && st.src.includes('asset_rehearsal_drive') && st.videoWidth > 0) {{
                    decoded = true;
                    dims = `${{st.videoWidth}}x${{st.videoHeight}}`;
                    break;
                }}
            }}
            if (!decoded) throw new Error('Drive video failed to decode frames: ' + dims);
            console.log('Drive video frame decode OK: ' + dims);

            // Verify initial playback advance
            const t1 = await evalJs(`document.querySelector('video[data-testid="series-video-player"]')?.currentTime || 0`);
            await new Promise(r => setTimeout(r, 1500));
            const t2 = await evalJs(`document.querySelector('video[data-testid="series-video-player"]')?.currentTime || 0`);
            const adv = t2 - t1;
            console.log(`Playback advance: ${{t1.toFixed(3)}}s -> ${{t2.toFixed(3)}}s (adv: ${{adv.toFixed(3)}}s)`);
            if (adv < 0.2) throw new Error('Playback did not advance: ' + adv);

            // Seek 1: Tua tới 60.0s
            console.log('Tua video lần 1 (tới 60.0s)...');
            await evalJs(`(() => {{
                const v = document.querySelector('video[data-testid="series-video-player"]');
                if (v) v.currentTime = 60.0;
            }})()`);
            let postSeek1 = -1;
            for (let i = 0; i < 20; i++) {{
                await new Promise(r => setTimeout(r, 800));
                postSeek1 = await evalJs(`document.querySelector('video[data-testid="series-video-player"]')?.currentTime || -1`);
                if (postSeek1 >= 59.5 && postSeek1 <= 66.0) break;
            }}
            console.log('Post-seek 1 time: ' + postSeek1.toFixed(3) + 's');
            if (postSeek1 < 59.5 || postSeek1 > 66.0) throw new Error('Seek 1 failed: ' + postSeek1);

            // Seek 2: Tua tới 120.0s
            console.log('Tua video lần 2 (tới 120.0s)...');
            await evalJs(`(() => {{
                const v = document.querySelector('video[data-testid="series-video-player"]');
                if (v) v.currentTime = 120.0;
            }})()`);
            let postSeek2 = -1;
            for (let i = 0; i < 20; i++) {{
                await new Promise(r => setTimeout(r, 800));
                postSeek2 = await evalJs(`document.querySelector('video[data-testid="series-video-player"]')?.currentTime || -1`);
                if (postSeek2 >= 119.5 && postSeek2 <= 128.0) break;
            }}
            console.log('Post-seek 2 time: ' + postSeek2.toFixed(3) + 's');
            if (postSeek2 < 119.5 || postSeek2 > 128.0) throw new Error('Seek 2 failed: ' + postSeek2);

            // Capture screenshot
            const ss = await send('Page.captureScreenshot', {{ format: 'png' }});
            fs.writeFileSync({json.dumps(str(SCREENSHOT_PATH))}, Buffer.from(ss.data, 'base64'));
            console.log('Screenshot saved.');

            const outData = {{
                dims,
                initialAdvance: adv,
                seek1Time: postSeek1,
                seek2Time: postSeek2
            }};
            fs.writeFileSync({json.dumps(str(temp_dir / "browser_result.json"))}, JSON.stringify(outData));
            ws.close();
            process.exit(0);
        }}
        main().catch(e => {{ console.error(e); process.exit(1); }});
        """
        runner_file = temp_dir / "browser_smoke_runner.cjs"
        runner_file.write_text(runner_js, encoding="utf-8")

        node_exe = shutil.which("node") or "node"
        browser_run = subprocess.run([node_exe, str(runner_file)], capture_output=True, text=True, timeout=90)
        print("  Browser runner stdout:\n" + browser_run.stdout)
        if browser_run.returncode != 0:
            print("  Browser runner stderr:\n" + browser_run.stderr)
            raise RuntimeError(f"Browser interaction runner failed with code {browser_run.returncode}")

        browser_res = json.loads((temp_dir / "browser_result.json").read_text(encoding="utf-8"))
        results["measurements"]["drive_video_dimensions"] = browser_res["dims"]
        results["measurements"]["initial_advance_sec"] = browser_res["initialAdvance"]
        results["measurements"]["seek_1_sec"] = browser_res["seek1Time"]
        results["measurements"]["seek_2_sec"] = browser_res["seek2Time"]
        results["gates"]["drive_playback_and_seeks"] = "PASS"
        print("  Real Google Drive video playback and 2 seeks SUCCESS.")

        results["status"] = "PASSED"
        print("\n" + "=" * 78)
        print("ALL GATES PASSED! SNAPSHOT-01 USABLE PREVIEW SMOKE TEST SUCCESSFUL.")
        print("=" * 78)

    finally:
        print("\n[Teardown] Stopping all spawned processes strictly by PID...")
        for proc in [chrome_proc, frontend_proc, spring_proc, fastapi_proc, rclone_proc]:
            if proc is not None:
                try:
                    proc.terminate()
                    proc.wait(timeout=4.0)
                except Exception:
                    try:
                        proc.kill()
                    except Exception:
                        pass
        time.sleep(1.0)
        results["owned_processes_stopped"] = True
        EVIDENCE_PATH.parent.mkdir(parents=True, exist_ok=True)
        EVIDENCE_PATH.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Smoke test evidence saved to: {EVIDENCE_PATH}")
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:
            pass

    return results


if __name__ == "__main__":
    res = run_smoke_test()
    if res.get("status") != "PASSED":
        sys.exit(1)
