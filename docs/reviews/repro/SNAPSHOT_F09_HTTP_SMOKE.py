"""Production Spring/Next HTTP smoke with isolated H2/media; no model/Drive/live DB."""
import json
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import time
import urllib.request
import urllib.error

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / 'docs/reviews/evidence/SNAPSHOT_F09_CURRENT_HTTP.json'


def request(url, data=None, headers=None, method=None):
    headers = dict(headers or {})
    if data is not None:
        data = json.dumps(data).encode()
        headers['Content-Type'] = 'application/json'
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=8) as response:
            raw = response.read()
            return response.status, json.loads(raw) if 'application/json' in response.headers.get('Content-Type', '') else raw
    except urllib.error.HTTPError as exc:
        return exc.code, None


def run():
    for port in (8080, 3008):
        with socket.socket() as sock:
            assert sock.connect_ex(('127.0.0.1', port)) != 0, f'Port occupied: {port}'
    temp = Path(tempfile.mkdtemp(prefix='dippie-current-http-'))
    media = temp / 'media'
    (media / 'synthetic').mkdir(parents=True)
    for name in ('feature_test.mp4', 'trailer_test.mp4'):
        shutil.copyfile(ROOT / 'media' / 'synthetic' / name if (ROOT / 'media' / 'synthetic' / name).exists() else ROOT / 'media' / name, media / 'synthetic' / name)
    cp = str(ROOT / 'backend/springboot/target/classes') + ';' + (ROOT / 'backend/springboot/target/cp.txt').read_text().strip()
    java = r'C:\Program Files\Java\jdk-25.0.3\bin\java.exe'
    args = [java, '-Dserver.address=127.0.0.1', '-Dserver.port=8080', '-Dspring.profiles.active=dev',
            f'-Dspring.datasource.url=jdbc:h2:file:{(temp / "db").as_posix()};MODE=PostgreSQL;NON_KEYWORDS=YEAR,USER',
            f'-Dapp.media.root={media.as_posix()}', f'-Dapp.catalog.snapshot-path={(temp / "snapshot.json").as_posix()}',
            '-Dapp.catalog.sync-url=http://127.0.0.1:18999/api/index/sync', '-Dapp.catalog.sync-token=',
            '-Dapp.seed.enabled=true', '-cp', cp, 'com.dippie.moviercm.MovieRcmApplication']
    processes = []
    logs = []
    result = {'gates': {}, 'scope': 'Production Spring compiled classes and Next production build; isolated H2/media. Sync/model/Drive/browser decoder NOT_RUN.', 'logs_dir': str(temp)}
    try:
        log = open(temp / 'spring.log', 'w', encoding='utf-8'); logs.append(log)
        proc = subprocess.Popen(args, cwd=ROOT / 'backend/springboot', stdout=log, stderr=subprocess.STDOUT)
        processes.append(proc)
        for _ in range(60):
            assert proc.poll() is None, 'Spring exited; inspect log'
            try:
                if request('http://127.0.0.1:8080/api/health')[0] == 200:
                    break
            except Exception:
                pass
            time.sleep(0.5)
        else:
            raise TimeoutError('Spring readiness')
        result['gates']['spring_start'] = 'PASS'
        status, body = request('http://127.0.0.1:8080/api/auth/login', {'usernameOrEmail': 'admin', 'password': 'password123'})
        assert status == 200
        token = body.get('data', {}).get('token') or body.get('token')
        assert token
        auth = {'Authorization': f'Bearer {token}'}
        result['gates']['login_http'] = 'PASS'
        fixture = json.loads((ROOT / 'docs/fixtures/rehearsal_catalog.json').read_text(encoding='utf-8'))
        status, body = request('http://127.0.0.1:8080/api/admin/catalog/validate', fixture, auth)
        assert status == 200 and body['valid']
        status, body = request('http://127.0.0.1:8080/api/admin/catalog/import', fixture, auth)
        assert status == 200 and body['success']
        result['gates']['validate_import_http'] = 'PASS'
        status, body = request('http://127.0.0.1:8080/api/catalog/search?q=B%E1%BA%A3o')
        assert status == 200 and any(row['id'] == 'ser_rehearsal_01' for row in body)
        result['gates']['search_exact_id_http'] = 'PASS'
        status, body = request('http://127.0.0.1:8080/api/media/stream/asset_feature_01', headers={'Range': 'bytes=0-1023'})
        assert status == 206 and len(body) == 1024
        result['gates']['local_range_http'] = 'PASS'
        status, _ = request('http://127.0.0.1:8080/api/media/stream/asset_feature_02')
        assert status in (401, 403, 404)
        status, body = request('http://127.0.0.1:8080/api/media/grant/asset_feature_02', headers=auth, method='POST')
        assert status == 200 and body.get('grant')
        status, body = request('http://127.0.0.1:8080/api/media/stream/asset_feature_02?grant=' + body['grant'], headers={'Range': 'bytes=0-1023'})
        assert status == 206 and len(body) == 1024
        result['gates']['protected_grant_range_http'] = 'PASS'
        log = open(temp / 'frontend.log', 'w', encoding='utf-8'); logs.append(log)
        node = shutil.which('node')
        proc = subprocess.Popen([node, str(ROOT / 'frontend/node_modules/next/dist/bin/next'), 'start', '-H', '127.0.0.1', '-p', '3008'], cwd=ROOT / 'frontend', stdout=log, stderr=subprocess.STDOUT)
        processes.append(proc)
        for _ in range(30):
            assert proc.poll() is None, 'Next exited'
            try:
                if request('http://127.0.0.1:3008')[0] == 200:
                    break
            except Exception:
                pass
            time.sleep(0.5)
        else:
            raise TimeoutError('Next readiness')
        for route in ('/admin/import', '/search', '/series/ser_rehearsal_01'):
            assert request('http://127.0.0.1:3008' + route)[0] == 200, route
        result['gates']['next_production_pages_http'] = 'PASS'
        result['status'] = 'PASS'
    except Exception as exc:
        result.update(status='FAIL', error=type(exc).__name__ + ': ' + str(exc))
        raise
    finally:
        for proc in reversed(processes):
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(8)
                except subprocess.TimeoutExpired:
                    proc.kill(); proc.wait(5)
        for log in logs:
            log.close()
        result['owned_processes_stopped'] = all(proc.poll() is not None for proc in processes)
        OUT.write_text(json.dumps(result, indent=2), encoding='utf-8')
        print(json.dumps(result))


if __name__ == '__main__':
    run()
