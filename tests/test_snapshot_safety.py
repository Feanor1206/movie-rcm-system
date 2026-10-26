"""Offline regressions for parser boundaries and retained catalog ownership."""
import copy
import importlib.util
import json
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend/fastapi'))
from services.catalog_sync import CatalogSyncManager, AcceptedSnapshot
from services.hybrid_retrieval import HybridMovieIndex
from services.qwen_service import QwenRecommendationService
from services.ai_pipeline import NLUUnderstandingNode, qwen_service


@pytest.mark.parametrize('value', [None, [], 'wrong', 1, {'query': [], 'reference': [], 'constraints': 'x'},
    {'requested_k': float('inf'), 'constraints': {'year_min': float('-inf')}},
    {'requested_k': 3.7, 'constraints': {'include_genres': 'Family', 'exclude_genres': [None, 1, 'Horror']}}])
def test_malformed_typed_intent_never_crashes(value):
    service = QwenRecommendationService(serving_mode='full', device='cpu')
    intent = service.normalize_phase23_intent(value, 'Tìm Jadoo', [])
    assert isinstance(intent['constraints']['include_genres'], list)
    assert all(isinstance(g, str) for g in intent['constraints']['exclude_genres'])
    assert intent['requested_k'] is None


def test_snapshot_owns_nested_state_and_bootstrap_is_ready():
    payload = json.loads((ROOT / 'docs/fixtures/rehearsal_catalog.json').read_text(encoding='utf-8'))
    manager = CatalogSyncManager()
    manager.load_from_payload(payload)
    snapshot = AcceptedSnapshot(0, manager.content_hash, manager, None, payload)
    assert snapshot.is_ready
    original = snapshot.get_flattened_catalog()
    rows = snapshot.get_flattened_catalog()
    rows[0]['genres'].append('MUTATED')
    manager._flattened_items[0]['title'] = 'MUTATED'
    payload['series'][0]['title'] = 'MUTATED'
    assert snapshot.get_flattened_catalog() == original
    assert snapshot.payload['series'][0]['title'] != 'MUTATED'
    one = snapshot.get_item_by_id(original[0]['id'])
    one['genres'].append('ALSO MUTATED')
    assert snapshot.get_flattened_catalog() == original


def test_custom_request_does_not_replace_shared_index(tmp_path):
    index = HybridMovieIndex(tmp_path / 'index.json')
    index.encoder = SimpleNamespace(encode_documents=lambda texts: [[1.0] for _ in texts],
        encode_queries=lambda texts: [[1.0] for _ in texts], is_loaded=True)
    first = [{'id': 'a', 'title': 'First story', 'genres': ['Animation'], 'description': 'family story'}]
    second = [{'id': 'b', 'title': 'Second story', 'genres': ['Animation'], 'description': 'family story'}]
    index.build_from_catalog(first, save_to_disk=False)
    original = copy.deepcopy(index.documents)
    index.search_hybrid('Second story', {}, catalog=second)
    assert index.documents == original
    assert not index.index_path.exists()


def test_anonymous_default_session_does_not_reuse_other_intent(monkeypatch):
    node = NLUUnderstandingNode()
    discovery = {'intent_type': 'DISCOVERY', 'constraints': {'year_min': 2010}}
    patch = {'intent_type': 'CONVERSATIONAL_PATCH', 'patch_ops': []}
    outputs = iter([discovery, patch])
    monkeypatch.setattr(qwen_service, 'parse_discovery_intent', lambda **kwargs: next(outputs))
    node.process('first')
    assert node.process('second')['intent_type'] == 'CONVERSATIONAL_PATCH'
    assert node.session_state == {}


def test_generation_metrics_are_thread_local():
    service = QwenRecommendationService(serving_mode='full', device='cpu')
    service._request_context.inference_stats = {'completion_tokens': 12}
    seen = []
    def other_request():
        seen.append(service.get_request_inference_stats()['completion_tokens'])
        service._request_context.inference_stats = {'completion_tokens': 99}
    thread = threading.Thread(target=other_request)
    thread.start()
    thread.join()
    assert seen == [0]
    assert service.get_request_inference_stats()['completion_tokens'] == 12


@pytest.mark.parametrize('headers,expected', [
    ({}, 401), ({'X-Service-Token': ''}, 403), ({'X-Service-Token': 'tiếng Việt'}, 403),
    ({'Authorization': 'Basic test-sync-secret-f08'}, 403),
    ({'Authorization': 'bearer test-sync-secret-f08'}, 200),
])
def test_sync_auth_rejects_bad_tokens_without_touching_catalog(tmp_path, headers, expected):
    spec = importlib.util.spec_from_file_location('snapshot_matrix', ROOT / 'tests/test_f08_atomic_concurrency_matrix.py')
    matrix = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(matrix)
    sync, hybrid = matrix.load_sync_and_index_modules()
    ns, manager, _, _, _ = matrix.create_test_context(tmp_path, sync, hybrid)
    payload = json.loads((ROOT / 'docs/fixtures/rehearsal_catalog.json').read_text(encoding='utf-8'))
    request = SimpleNamespace(generation=1, catalog=payload, content_hash=manager.compute_hash(payload))
    if expected == 200:
        assert ns['sync_index'](SimpleNamespace(headers=headers), request).status == 'success'
    else:
        with pytest.raises(matrix.ProbeError) as caught:
            ns['sync_index'](SimpleNamespace(headers=headers), request)
        assert caught.value.status_code == expected
        assert ns['_current_sync_generation'] == 0
