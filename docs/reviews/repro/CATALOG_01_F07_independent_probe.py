"""Offline F07 checks; temp state, fake encoder, production manager/index and sync AST."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import threading
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[3]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def run():
    old = module('f06_review_reuse', 'docs/reviews/repro/CATALOG_01_F06_independent_probe.py')
    regression = old.run()  # Do not run old main or overwrite its evidence.
    matrix = module('f07_matrix_review', 'tests/test_f07_atomic_concurrency_matrix.py')
    sync, hybrid = matrix.load_sync_and_index_modules()
    payload = json.loads((ROOT / 'docs/fixtures/rehearsal_catalog.json').read_text(encoding='utf-8'))
    a, b = copy.deepcopy(payload), copy.deepcopy(payload)
    a['series'][0]['title'] = 'accepted-A'
    b['series'][0]['title'] = 'next-B'
    with tempfile.TemporaryDirectory(prefix='catalog-f07-reader-review-') as temp:
        ns, manager, index, _ = matrix.create_test_context(Path(temp), sync, hybrid)
        def call(gen, data):
            return ns['sync_index'](SimpleNamespace(headers={'X-Service-Token': 'test-sync-secret-f07'}),
                SimpleNamespace(generation=gen, catalog=data, content_hash=manager.compute_hash(data)))
        call(1, a)
        published_manager = threading.Event()
        resume = threading.Event()
        original_copy = manager.copy_from
        def pause_after_manager_copy(candidate):
            original_copy(candidate)
            published_manager.set()
            if not resume.wait(5):
                raise TimeoutError('review reader did not resume writer')
        manager.copy_from = pause_after_manager_copy
        errors = []
        def writer():
            try:
                call(2, b)
            except Exception as exc:
                errors.append(type(exc).__name__)
        thread = threading.Thread(target=writer)
        thread.start()
        try:
            assert published_manager.wait(5)
            titles = lambda rows: [r['title'] for r in rows if r.get('item_type') == 'series']
            observed = dict(manager_titles=titles(manager.get_flattened_catalog()),
                            index_titles=titles(index.documents.values()),
                            active_generation=ns['_current_sync_generation'],
                            persisted_generation=ns['_load_sync_state']()[0])
        finally:
            resume.set()
            thread.join(5)
        assert not thread.is_alive() and not errors, errors
        observed['mixed_snapshot_seen_by_reader'] = (
            'next-B' in observed['manager_titles'] and 'accepted-A' in observed['index_titles'])
        return dict(durable_failure_regression=regression, concurrent_publication=observed,
                    scope='Thread scheduling barrier after production manager copy, before production index assignments; real state getters/index, fake encoder and temporary disk. No HTTP/browser/model/Drive.')


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    rendered = json.dumps(run(), ensure_ascii=False, indent=2) + '\n'
    (ROOT / 'docs/reviews/evidence/CATALOG_01_F07_independent_probe.json').write_text(rendered, encoding='utf-8')
    print(rendered)
