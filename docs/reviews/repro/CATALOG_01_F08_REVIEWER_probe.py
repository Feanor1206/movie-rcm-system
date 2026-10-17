"""Real setter regression for retained recovery snapshot; no model/services/runtime writes."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[3]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def run():
    matrix = module('f08_reviewer_matrix', 'tests/test_f08_atomic_concurrency_matrix.py')
    sync, hybrid = matrix.load_sync_and_index_modules()
    payload = json.loads((ROOT / 'docs/fixtures/rehearsal_catalog.json').read_text(encoding='utf-8'))
    a, b = copy.deepcopy(payload), copy.deepcopy(payload)
    a['series'][0]['title'] = 'recovered-A'
    b['series'][0]['title'] = 'published-B'
    with tempfile.TemporaryDirectory(prefix='f08-reviewer-recovery-') as temp:
        ns, _, index, _, _ = matrix.create_test_context(Path(temp), sync, hybrid)
        manager = sync.catalog_sync_manager
        manager.load_from_payload(a, include_draft=False, include_private=False)
        index.build_from_catalog(manager.get_flattened_catalog(), save_to_disk=False)
        # Exact ownership used by main.py startup recovery: singleton manager in snapshot.
        recovered = sync.AcceptedSnapshot(1, manager.compute_hash(a), manager, index, a)
        sync.set_accepted_snapshot(recovered)
        retained = sync.get_accepted_snapshot()
        ns.update(catalog_sync_manager=manager, AcceptedSnapshot=sync.AcceptedSnapshot,
                  set_accepted_snapshot=sync.set_accepted_snapshot,
                  get_accepted_snapshot=sync.get_accepted_snapshot,
                  _current_sync_generation=1, _current_sync_hash=retained.content_hash)
        result = ns['sync_index'](SimpleNamespace(headers={'X-Service-Token': 'test-sync-secret-f08'}),
            SimpleNamespace(generation=2, catalog=b, content_hash=manager.compute_hash(b)))
        assert result.status == 'success'
        titles = lambda rows: [r['title'] for r in rows if r.get('item_type') == 'series']
        old = dict(generation=retained.generation,
                   manager_titles=titles(retained.get_flattened_catalog()),
                   index_titles=titles(retained.hybrid_index.documents.values()),
                   payload_titles=[r['title'] for r in retained.payload['series']])
        current = sync.get_accepted_snapshot()
        return dict(retained_recovery_snapshot=old,
                    new_generation=current.generation,
                    new_manager_titles=titles(current.get_flattened_catalog()),
                    retained_snapshot_mutated=('published-B' in old['manager_titles'] and 'recovered-A' in old['index_titles']),
                    scope='Production sync AST + REAL production AcceptedSnapshot/setter/getter/manager/index/BM25; fake encoder, temp state; retained snapshot models an in-flight request after startup recovery. No HTTP/model/browser/Drive.')


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    result = run()
    text = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    (ROOT / 'docs/reviews/evidence/CATALOG_01_F08_REVIEWER_probe.json').write_text(text, encoding='utf-8')
    print(text)
