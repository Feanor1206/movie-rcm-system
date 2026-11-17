import argparse
import base64
import hashlib
import json
import os
import sqlite3
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from .caption import RequestBudget, caption_jobs, durable_budget, reply, save_output
from .common import ARTIFACTS, CATALOG, episodes, load_deepseek_env, pilot_options, read
from .summarize import summary_job


APPROVED = ('ep_jadoo_s01_0022', 'ep_jadoo_s04_0021')
RUN_ID = 'pilot-two-episodes'
MAX_REQUESTS = 40


def local_endpoint(value):
    value = value.strip().rstrip('/')
    parsed = urlsplit(value)
    if (parsed.scheme != 'http' or parsed.hostname not in {'localhost', '127.0.0.1', '::1'}
            or parsed.username or parsed.password or parsed.query or parsed.fragment):
        raise ValueError('LOCAL_VISION_BASE_URL must be a loopback HTTP URL')
    return value


def contains_secret(response, secret):
    if not secret:
        return False
    if secret in response.text:
        return True
    try:
        decoded = json.dumps(response.json(), ensure_ascii=False)
    except ValueError:
        return False
    return secret in decoded


def capability_probe(image, model, endpoint, secret, budget, client):
    fingerprint = hashlib.sha256((endpoint + '\0' + model).encode()).hexdigest()
    with sqlite3.connect(budget.path) as db:
        db.execute('CREATE TABLE IF NOT EXISTS vision_probe (run_id TEXT PRIMARY KEY, config_hash TEXT NOT NULL, result TEXT NOT NULL)')
        if 'status' not in {row[1] for row in db.execute('PRAGMA table_info(vision_probe)')}:
            db.execute("ALTER TABLE vision_probe ADD COLUMN status TEXT NOT NULL DEFAULT 'started'")
        db.execute('INSERT OR IGNORE INTO vision_probe (run_id, config_hash, result) VALUES (?, ?, ?)', (budget.run_id, fingerprint, 'inconclusive'))
        inserted = db.execute('SELECT changes()').fetchone()[0]
        stored_hash, result, status = db.execute('SELECT config_hash, result, status FROM vision_probe WHERE run_id = ?', (budget.run_id,)).fetchone()
    if stored_hash != fingerprint:
        raise ValueError('Probe configuration changed; the existing run cannot be reused')
    if not inserted:
        if result == 'inconclusive':
            raise ValueError(f'Vision probe inconclusive ({status}); stopped without retry; investigate locally and seek authorization before any new probe')
        return result
    content = image.path.read_bytes()
    if hashlib.sha256(content).hexdigest() != image.sha256 or len(content) > 1024 * 1024:
        raise ValueError('Probe requires an unchanged keyframe no larger than 1 MiB')
    payload = {'model': model, 'messages': [{'role': 'user', 'content': [
        {'type': 'text', 'text': 'Describe this image briefly.'},
        {'type': 'image_url', 'image_url': {'url': f'data:{image.mime};base64,{base64.b64encode(content).decode("ascii")}'}},
    ]}], 'max_tokens': 32}
    if urlsplit(endpoint).hostname == 'api.deepseek.com':
        payload['thinking'] = {'type': 'disabled'}
    budget.consume(1)
    try:
        response = client.post(endpoint + '/chat/completions', headers={'Authorization': f'Bearer {secret}'}, json=payload)
    except httpx.HTTPError:
        with sqlite3.connect(budget.path) as db:
            db.execute("UPDATE vision_probe SET status = 'network failure' WHERE run_id = ?", (budget.run_id,))
        raise ValueError('Vision probe inconclusive (network failure); stopped without retry') from None
    if contains_secret(response, secret):
        with sqlite3.connect(budget.path) as db:
            db.execute("UPDATE vision_probe SET status = 'credential in response' WHERE run_id = ?", (budget.run_id,))
        raise ValueError('Vision probe inconclusive (credential in response); stopped without retry')
    try:
        provider = response.json()
    except ValueError:
        provider = {}
    if isinstance(provider, dict):
        budget.record_response(provider)
    result = 'inconclusive'
    if response.is_success:
        try:
            if isinstance(provider['choices'][0]['message']['content'], str) and provider['choices'][0]['message']['content'].strip():
                result = 'vision'
        except (KeyError, IndexError, TypeError):
            pass
    elif response.status_code in (400, 415, 422):
        error = provider.get('error', {}) if isinstance(provider, dict) else {}
        message = str(error.get('message', '') if isinstance(error, dict) else '').lower()
        if ('image' in message or 'vision' in message) and any(word in message for word in ('not support', 'unsupported', 'does not support')):
            result = 'local'
    with sqlite3.connect(budget.path) as db:
        db.execute('UPDATE vision_probe SET result = ?, status = ? WHERE run_id = ?', (result, f'HTTP {response.status_code}', budget.run_id))
    if result == 'inconclusive':
        raise ValueError(f'Vision probe inconclusive (HTTP {response.status_code}); stopped without retry; investigate locally and seek authorization before any new probe')
    return result


class DeepSeekClient:
    def __init__(self, client, secret=''):
        self.client = client
        self.secret = secret

    def post(self, url, **kwargs):
        body = kwargs['json']
        schema = body['response_format']['json_schema']['schema']
        body['messages'][0]['content'] += '\nJSON schema: ' + json.dumps(schema, ensure_ascii=False)
        body['response_format'] = {'type': 'json_object'}
        if urlsplit(url).hostname == 'api.deepseek.com':
            body['thinking'] = {'type': 'disabled'}
        response = self.client.post(url, **kwargs)
        if contains_secret(response, self.secret):
            raise ValueError('Teacher response contained a credential; stopped without caching')
        return response


def main():
    parser = argparse.ArgumentParser(description='Run the authorized two-episode DeepSeek offline pilot.')
    pilot_options(parser)
    parser.add_argument('--catalog', type=Path, default=CATALOG)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    try:
        if (args.inventory.resolve() != (ARTIFACTS / 'inventory.json').resolve()
                or args.artifacts.resolve() != ARTIFACTS.resolve() or args.catalog.resolve() != CATALOG.resolve()):
            raise ValueError('Only the canonical pilot inventory, artifacts and catalog are authorized')
        if args.episode and not set(args.episode) <= set(APPROVED):
            raise ValueError('Only S01E22 and S04E21 are authorized')
        selected = args.episode or list(APPROVED)
        rows = episodes(args.inventory, selected)
        if {row['episode_id'] for row in rows} != set(selected):
            raise ValueError('Approved episode missing from inventory')
        load_deepseek_env()
        model = os.getenv('DEEPSEEK_MODEL', '').strip()
        endpoint = os.getenv('DEEPSEEK_BASE_URL', '').strip().rstrip('/')
        secret = os.getenv('DEEPSEEK_API_KEY', '').strip()
        parsed = urlsplit(endpoint)
        if args.execute and (not model or not secret or parsed.scheme != 'https' or not parsed.hostname
                             or parsed.username or parsed.password or parsed.query or parsed.fragment):
            raise ValueError('Configure DEEPSEEK_MODEL, DEEPSEEK_API_KEY and an HTTPS DEEPSEEK_BASE_URL')
        catalog = read(args.catalog)
        series = {row['id']: row['series_id'] for row in catalog['episodes']}
        groups = []
        for row in rows:
            characters = {char['id']: char['name'] for char in catalog['characters'] if series[row['episode_id']] in char.get('series_ids', [])}
            directory = args.artifacts / row['episode_id']
            jobs, skipped = caption_jobs(directory, row, characters, model, endpoint)
            groups.append((directory, row, characters, jobs, skipped))
        jobs = [job for _, _, _, group, _ in groups for _, job in group]
        if not args.execute:
            print(json.dumps({'mode': 'dry-run', 'episodes': selected, 'caption_requests': len(jobs),
                              'caption_images': sum(len(job.images) for job in jobs), 'probe_requests': int(bool(jobs)),
                              'summary_requests': sum(bool(group) for _, _, _, group, _ in groups), 'external_requests': 0}))
            return
        if any(not group for _, _, _, group, _ in groups):
            raise ValueError('An approved episode has no eligible scenes with four unique keyframes')
        frames = [image for job in jobs for image in job.images if image.path.stat().st_size <= 1024 * 1024]
        if not frames:
            raise ValueError('No probe keyframe at most 1 MiB')
        budget = durable_budget(args.artifacts, RUN_ID, MAX_REQUESTS)
        with httpx.Client(timeout=120, follow_redirects=False, trust_env=False) as client:
            mode = capability_probe(frames[0], model, endpoint, secret, budget, client)
            local_model = os.getenv('LOCAL_VISION_MODEL', '').strip()
            if mode == 'local':
                local_url = local_endpoint(os.getenv('LOCAL_VISION_BASE_URL', ''))
                if not local_model:
                    raise ValueError('Configure LOCAL_VISION_MODEL for the local llama-server')
                groups = [(directory, row, chars, *caption_jobs(directory, row, chars, local_model, local_url))
                          for directory, row, chars, _, _ in groups]
            missing = sum(not job.cache.is_file() for _, _, _, group, _ in groups for _, job in group) if mode == 'vision' else 0
            with sqlite3.connect(budget.path) as db:
                sent = db.execute('SELECT sent FROM budgets WHERE run_id = ?', (RUN_ID,)).fetchone()[0]
            if sent + missing > MAX_REQUESTS:
                raise ValueError('Remaining shared budget cannot cover captioning')
            for directory, row, chars, group, skipped in groups:
                results = []
                for scene, job in group:
                    value, created = reply(job, DeepSeekClient(client, secret) if mode == 'vision' else client,
                                           secret if mode == 'vision' else 'local', budget if mode == 'vision' else RequestBudget(100000))
                    results.append({key: scene[key] for key in ('scene_id', 'start_ms', 'end_ms', 'transcript_cue_ids')}
                                   | value | {'created_at': created, 'input_hash': job.input_hash})
                if not results:
                    raise ValueError('No eligible captions for an approved episode')
                save_output(directory / 'captions.json', {'model': model if mode == 'vision' else local_model,
                            'prompt_version': 'dippie-caption-v1', 'created_at': max(item['created_at'] for item in results),
                            'scenes': results, 'skipped': skipped})
            for directory, row, _, _, _ in groups:
                job = summary_job(directory, row, model, endpoint)
                value, created = reply(job, DeepSeekClient(client, secret), secret, budget)
                save_output(directory / 'synopsis.json', {**value, 'model': model, 'prompt_version': job.prompt_version,
                            'created_at': created, 'input_hash': job.input_hash})
        with sqlite3.connect(budget.path) as db:
            sent = db.execute('SELECT sent FROM budgets WHERE run_id = ?', (RUN_ID,)).fetchone()[0]
            usage = [{'usage': json.loads(u) if u else None, 'cost': json.loads(c) if c else None}
                     for u, c in db.execute('SELECT usage_json, cost_json FROM requests WHERE run_id = ?', (RUN_ID,)) if u or c]
        print(json.dumps({'mode': mode, 'total_external_requests': sent, 'provider_usage_and_cost': usage}, ensure_ascii=False))
    except (OSError, ValueError, KeyError, TypeError) as error:
        parser.error(str(error))


if __name__ == '__main__':
    main()
