"""Offline production sync/index failure repro. No services, model, GPU or runtime writes."""
import ast
import copy
import importlib.util
import json
import logging
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
    sync = module('f06_sync_review', 'backend/fastapi/services/catalog_sync.py')
    hybrid = module('f06_index_review', 'backend/fastapi/services/hybrid_retrieval.py')
    payload = json.loads((ROOT / 'docs/fixtures/rehearsal_catalog.json').read_text(encoding='utf-8'))
    a = copy.deepcopy(payload)
    b = copy.deepcopy(payload)
    a['series'][0]['title'] = 'accepted-A'
    b['series'][0]['title'] = 'rejected-B'
    manager = sync.CatalogSyncManager()
    index = hybrid.HybridMovieIndex()
    # Bypass encoder entirely; preserve production documents/BM25/build behavior.
    index.encoder = SimpleNamespace(encode_documents=lambda texts: [[1.0] for _ in texts])

    class ProbeError(Exception):
        def __init__(self, status_code, detail):
            self.status_code = status_code

    tree = ast.parse((ROOT / 'backend/fastapi/main.py').read_text(encoding='utf-8'))
    nodes = []
    for name in ['_save_sync_state', '_load_sync_state', 'sync_index']:
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
        node.decorator_list = []
        node.returns = None
        for arg in node.args.args:
            arg.annotation = None
        nodes.append(node)
    with tempfile.TemporaryDirectory(prefix='catalog-f06-review-') as temp:
        ns = dict(FASTAPI_SYNC_SECRET='fixture-only', _current_sync_generation=0,
                  _current_sync_hash='', _active_catalog_payload=None,
                  _publish_lock=threading.Lock(), HTTPException=ProbeError,
                  IndexSyncResponse=lambda **kw: SimpleNamespace(**kw),
                  catalog_sync_manager=manager, logger=logging.getLogger('f06-review'),
                  cascading_pipeline=SimpleNamespace(retrieval_node=SimpleNamespace(hybrid_index=index)),
                  SYNC_STATE_PATH=Path(temp) / 'state.json', json=json)
        exec(compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])), 'production-sync', 'exec'), ns)
        def call(gen, data):
            try:
                return vars(ns['sync_index'](SimpleNamespace(headers={'X-Service-Token': 'fixture-only'}),
                    SimpleNamespace(generation=gen, catalog=data, content_hash=manager.compute_hash(data))))
            except ProbeError as exc:
                return {'http_status': exc.status_code}
        baseline = call(1, a)
        def fail_save(*args):
            raise OSError('reviewer injected durable write failure')
        ns['_save_sync_state'] = fail_save
        rejected = call(2, b)
        titles = lambda items: [row['title'] for row in items if row.get('item_type') == 'series']
        generation, _, persisted = ns['_load_sync_state']()
        result = dict(baseline_status=baseline.get('status'), rejected=rejected,
                      active_generation=ns['_current_sync_generation'], persisted_generation=generation,
                      manager_titles=titles(manager.get_flattened_catalog()),
                      index_titles=titles(index.documents.values()),
                      persisted_titles=[row['title'] for row in persisted['series']],
                      scope='production sync/save/load AST, real manager and HybridMovieIndex/BM25; fake encoder; temp state; no HTTP/browser/model')
        assert baseline.get('status') == 'success'
        assert rejected.get('http_status') == 500
        result['rejected_candidate_leaked_into_active_index'] = 'rejected-B' in result['index_titles']
        return result


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    rendered = json.dumps(run(), ensure_ascii=False, indent=2) + '\n'
    (ROOT / 'docs/reviews/evidence/CATALOG_01_F06_independent_probe.json').write_text(rendered, encoding='utf-8')
    print(rendered)
