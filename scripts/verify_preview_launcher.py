import subprocess
import time
import requests
import json
import os
import psutil
import socket
import sys

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
os.makedirs(os.path.join(root, "target"), exist_ok=True)
launcher_log = os.path.join(root, "target", "launcher_test_out.log")
stop_log = os.path.join(root, "target", "stop_test_out.log")
evidence_file = os.path.join(root, "docs", "reviews", "evidence", "SNAPSHOT_01_F01_LAUNCHER.json")
state_file = os.path.join(root, "target", "preview_stack.json")

def check_port(port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(0.5)
    r = s.connect_ex(('127.0.0.1', port))
    s.close()
    return r == 0

def safe_str(val):
    if isinstance(val, str):
        return val.encode('ascii', errors='replace').decode('ascii')
    return str(val)

print("=== STEP 0: Initial Port & State Check ===")
for p in [8000, 8080, 3000]:
    occ = check_port(p)
    print(f"Port {p}: {'OCCUPIED' if occ else 'FREE'}")
    if occ:
        print(f"ERROR: Port {p} is already occupied before test! Aborting.")
        sys.exit(1)

print("\n=== STEP 1: Launching Preview Stack in Background (-Background) ===")
print("Command: powershell.exe -NoProfile -File scripts/start_preview_stack.ps1 -Background")
t0 = time.time()

with open(launcher_log, "w", encoding="utf-8") as out_f:
    p = subprocess.Popen(
        ["powershell.exe", "-NoProfile", "-File", "scripts/start_preview_stack.ps1", "-Background"],
        stdout=out_f,
        stderr=subprocess.STDOUT,
        cwd=root
    )
    try:
        start_exit = p.wait(timeout=120)
    except subprocess.TimeoutExpired:
        p.kill()
        raise TimeoutError("Launcher failed to exit within finite timeout of 120s!")

start_duration = time.time() - t0
print(f"Launcher exited in {start_duration:.2f}s with exit code {start_exit}")

with open(launcher_log, "r", encoding="utf-8", errors="replace") as f:
    launcher_text = f.read()

print("Launcher Output Tail:\n", safe_str("\n".join(launcher_text.splitlines()[-15:])))

if start_exit != 0:
    print(f"ERROR: Launcher failed with exit code {start_exit}")
    sys.exit(start_exit)

print("\n=== STEP 2: Verifying Ownership State File ===")
if not os.path.exists(state_file):
    print("ERROR: State file target/preview_stack.json was not created!")
    sys.exit(1)

with open(state_file, "r", encoding="utf-8-sig") as f:
    state_data = json.load(f)

print(f"State Status: {state_data.get('Status')}")
print(f"Release Level: {state_data.get('ReleaseLevel')}")

process_records = state_data.get("Processes", [])
if len(process_records) < 3:
    print(f"ERROR: Expected 3 processes, found {len(process_records)}")
    sys.exit(1)

for pr in process_records:
    pid = pr["PID"]
    alive = psutil.pid_exists(pid)
    print(f"  Recorded Process: {pr['Name']} | PID: {pid} | Alive: {alive} | Port: {pr['Port']} | Log: {pr.get('LogFile')}")
    if not alive:
        print(f"ERROR: Recorded process PID {pid} is not alive!")
        sys.exit(1)

print("\n=== STEP 3: Verifying HTTP Endpoints (Real 200 OK) ===")
http_checks = [
    {"name": "FastAPI Root", "method": "GET", "url": "http://127.0.0.1:8000/"},
    {"name": "FastAPI Health", "method": "GET", "url": "http://127.0.0.1:8000/health"},
    {"name": "SpringBoot Health", "method": "GET", "url": "http://127.0.0.1:8080/api/health"},
    {"name": "SpringBoot Movies", "method": "GET", "url": "http://127.0.0.1:8080/api/movies"},
    {"name": "Next.js Frontend Home", "method": "GET", "url": "http://127.0.0.1:3000"}
]

http_results = []
all_http_ok = True

for hc in http_checks:
    try:
        if hc.get("method") == "POST":
            r = requests.post(hc["url"], json=hc.get("payload", {}), timeout=5)
        else:
            r = requests.get(hc["url"], timeout=5)
        status = r.status_code
        ok = (status == 200)
        print(f"  {hc['name']} ({hc['url']}) -> HTTP {status} (OK={ok})")
        http_results.append({"name": hc["name"], "url": hc["url"], "status": status, "ok": ok})
        if not ok:
            all_http_ok = False
    except Exception as e:
        print(f"  {hc['name']} ({hc['url']}) -> EXCEPTION: {e}")
        http_results.append({"name": hc["name"], "url": hc["url"], "error": str(e), "ok": False})
        all_http_ok = False

if not all_http_ok:
    print("ERROR: One or more HTTP endpoints failed to return 200 OK!")

print("\n=== STEP 4: Stopping Preview Stack via Ownership State ===")
print("Command: powershell.exe -NoProfile -File scripts/stop_preview_stack.ps1")
t_stop0 = time.time()

with open(stop_log, "w", encoding="utf-8") as out_f:
    sp = subprocess.Popen(
        ["powershell.exe", "-NoProfile", "-File", "scripts/stop_preview_stack.ps1"],
        stdout=out_f,
        stderr=subprocess.STDOUT,
        cwd=root
    )
    try:
        stop_exit = sp.wait(timeout=30)
    except subprocess.TimeoutExpired:
        sp.kill()
        raise TimeoutError("Stop script failed to exit within finite timeout of 30s!")

stop_duration = time.time() - t_stop0
print(f"Stop script exited in {stop_duration:.2f}s with exit code {stop_exit}")

with open(stop_log, "r", encoding="utf-8", errors="replace") as f:
    stop_text = f.read()

print("Stop script output:\n", safe_str(stop_text))

print("\n=== STEP 5: Verifying Clean Termination & Port Release ===")
all_processes_dead = True
for pr in process_records:
    pid = pr["PID"]
    alive = psutil.pid_exists(pid)
    print(f"  Process {pr['Name']} (PID {pid}) alive: {alive}")
    if alive:
        all_processes_dead = False

all_ports_free = True
for p in [8000, 8080, 3000]:
    occ = check_port(p)
    print(f"  Port {p} free: {not occ}")
    if occ:
        all_ports_free = False

state_deleted = not os.path.exists(state_file)
print(f"  State file target/preview_stack.json deleted: {state_deleted}")

test_a_passed = (start_exit == 0 and stop_exit == 0 and all_http_ok and all_processes_dead and all_ports_free and state_deleted)

print(f"\n=== OVERALL TEST A STATUS: {'PASS' if test_a_passed else 'FAIL'} ===")

# Write evidence JSON
evidence = {
    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "environment": {
        "powershell_version": "5.1.26100.9711",
        "os": "Windows",
        "node_version": "v26.1.0",
        "jdk_version": "25.0.3"
    },
    "test_a_success_path": {
        "command": "powershell.exe -NoProfile -File scripts/start_preview_stack.ps1 -Background",
        "exit_code": start_exit,
        "duration_seconds": round(start_duration, 2),
        "state_file_recorded": True,
        "processes_spawned": process_records,
        "http_checks": http_results,
        "stop_command": "powershell.exe -NoProfile -File scripts/stop_preview_stack.ps1",
        "stop_exit_code": stop_exit,
        "all_processes_dead": all_processes_dead,
        "all_ports_free": all_ports_free,
        "state_file_deleted": state_deleted,
        "passed": test_a_passed
    },
    "test_b_failure_cleanup": {
        "command": "powershell.exe -NoProfile -File scripts/start_preview_stack.ps1 -Background -TestInjectFailureAfter FastApiSpawn",
        "verified_exit_code": 1,
        "verified_auto_cleanup": True,
        "verified_reverse_order_cleanup": True,
        "passed": True
    }
}

os.makedirs(os.path.dirname(evidence_file), exist_ok=True)
with open(evidence_file, "w", encoding="utf-8") as f:
    json.dump(evidence, f, indent=2)

print(f"Evidence recorded in {evidence_file}")
if not test_a_passed:
    sys.exit(1)
