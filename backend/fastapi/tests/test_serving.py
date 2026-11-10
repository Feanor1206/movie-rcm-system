import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import httpx
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from schemas import HealthResponse, ReadinessResponse
from services.llm_client import LLMClient, LLMProtocolError, LLMUnavailableError
from services.model_registry import ModelRegistry, TorchScriptReranker


@pytest.mark.parametrize('mode,backend', [('light', 'template'), ('full', 'llama-server'), ('cloud', 'deepseek')])
def test_model_modes_keep_external_llm_identity_truthful(mode, backend):
    registry = ModelRegistry(mode)
    health = HealthResponse(**registry.health()).model_dump()
    assert health['activeInferenceBackend'] == backend
    assert not health['modelLoaded']
    assert health['activeBaseModelName'] is None
    assert not health['phase23AdapterLoaded']
    assert health['activeAdapterPath'] is None


def test_mode_environment_precedence_and_invalid_mode(monkeypatch):
    monkeypatch.setenv('MODEL_MODE', 'cloud')
    monkeypatch.setenv('SERVING_MODE', 'full')
    assert ModelRegistry().mode == 'cloud'
    assert ModelRegistry('light').mode == 'light'
    with pytest.raises(ValueError):
        ModelRegistry('unknown')


def test_missing_model_failure_is_cached_without_exposing_private_paths():
    registry = ModelRegistry('light')
    attempts = []
    def failing_model():
        attempts.append(True)
        raise RuntimeError('private filesystem path')
    registry.register('reranker', failing_model)
    assert registry.get('reranker') is None
    assert registry.get('reranker') is None
    assert attempts == [True]
    assert 'private filesystem path' not in json.dumps(registry.readiness())
    assert not registry.readiness()['features']['rerank']['ready']


def test_configured_encoder_does_not_load_before_initialization(monkeypatch):
    monkeypatch.setenv('TEXT_ENCODER_PATH', 'missing-local-artifact')
    registry = ModelRegistry('full')
    assert registry.models == {}
    asyncio.run(registry.initialize())
    assert registry.get('embedder') is None
    assert 'embedder' in registry.errors
    assert not registry.llm_ready


def test_readiness_schema_exposes_independent_capabilities():
    registry = ModelRegistry('full')
    snapshot = SimpleNamespace(is_ready=True, hybrid_index=SimpleNamespace(is_ready=True, dense_ready=False))
    response = ReadinessResponse(**registry.readiness(snapshot)).model_dump()
    assert response['ready']
    assert response['features']['search']['ready']
    assert response['features']['recommend']['ready']
    assert response['features']['chat']['ready']
    assert not response['features']['llm']['ready']
    assert not response['features']['frameSearch']['ready']


def test_missing_snapshot_does_not_claim_search_or_recommend_ready():
    registry = ModelRegistry('light')
    ready = registry.readiness()
    assert not ready['ready']
    assert not ready['features']['search']['ready']
    assert not ready['features']['recommend']['ready']
    assert not ready['features']['chat']['ready']


def test_frame_and_reranker_readiness_requires_loaded_assets():
    registry = ModelRegistry('light')
    registry.register('frame_search', lambda: object())
    registry.register('reranker', lambda: object())
    snapshot = SimpleNamespace(is_ready=True, hybrid_index=SimpleNamespace(is_ready=True))
    assert not registry.readiness(snapshot)['features']['frameSearch']['ready']
    asyncio.run(registry.initialize())
    assert registry.readiness(snapshot)['features']['frameSearch']['ready']
    assert registry.readiness(snapshot)['features']['rerank']['ready']


def test_torchscript_reranker_uses_local_tokenizer_and_cpu_when_requested(tmp_path, monkeypatch):
    import torch
    from tokenizers import Tokenizer
    from tokenizers.models import WordLevel
    from tokenizers.pre_tokenizers import Whitespace
    class PairScorer(torch.nn.Module):
        def forward(self, input_ids, attention_mask):
            return (input_ids * attention_mask).float().sum(dim=1)
    tokenizer = Tokenizer(WordLevel({'[UNK]': 0, '[PAD]': 1, 'flower': 2, 'broken': 3}, unk_token='[UNK]'))
    tokenizer.pre_tokenizer = Whitespace()
    tokenizer.save(str(tmp_path / 'tokenizer.json'))
    model = torch.jit.trace(PairScorer(), (torch.ones((1, 2), dtype=torch.long), torch.ones((1, 2), dtype=torch.long)))
    model.save(str(tmp_path / 'model.pt'))
    (tmp_path / 'reranker.json').write_text(json.dumps({'model_file': 'model.pt', 'tokenizer_file': 'tokenizer.json', 'max_length': 16}), encoding='utf-8')
    monkeypatch.setenv('RERANKER_DEVICE', 'cpu')
    monkeypatch.setattr(torch.cuda, 'is_available', lambda: True)
    reranker = TorchScriptReranker(tmp_path)
    assert reranker.device == 'cpu'
    assert reranker('flower', ['broken', 'flower']) == [5.0, 4.0]
    assert reranker('flower', []) == []
    assert np.isfinite(reranker('flower', ['broken'])).all()


def test_torchscript_reranker_rejects_model_outside_artifact(tmp_path):
    (tmp_path / 'reranker.json').write_text(json.dumps({'model_file': '../outside.pt'}), encoding='utf-8')
    with pytest.raises(ValueError):
        TorchScriptReranker(tmp_path)


def test_full_provider_failure_clears_active_identity():
    async def run():
        registry = ModelRegistry('full')
        registry.set_llm_status(True)
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(503, text='internal GPU path'))) as client:
            llm = LLMClient(registry, client)
            with pytest.raises(LLMUnavailableError):
                _ = [part async for part in llm.stream([])]
        health = registry.health()
        assert not health['modelLoaded']
        assert health['activeBaseModelName'] is None
        assert health['degraded']
        assert 'internal GPU path' not in json.dumps(health)
    asyncio.run(run())


def test_truncated_generation_is_rejected():
    async def run():
        payload = 'data: {"choices":[{"delta":{"content":"partial"},"finish_reason":"length"}]}\n\n'
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200, headers={'content-type': 'text/event-stream'}, text=payload))) as client:
            with pytest.raises(LLMProtocolError):
                _ = [part async for part in LLMClient(ModelRegistry('full'), client).stream([])]
    asyncio.run(run())


def test_cloud_intent_uses_json_mode_and_secret_only_in_header(monkeypatch):
    monkeypatch.setenv('DEEPSEEK_API_KEY', 'test-cloud-secret')
    requests = []
    async def run():
        def handler(request):
            requests.append(request)
            return httpx.Response(200, json={'choices': [{'message': {'content': json.dumps({'intent_type': 'DISCOVERY', 'mode': 'find_moment', 'scope': 'scene'})}}]})
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            intent = await LLMClient(ModelRegistry('cloud'), client).parse_intent([{'role': 'user', 'content': 'flower'}])
        assert intent['intent_type'] == 'DISCOVERY'
    asyncio.run(run())
    assert requests[0].headers['authorization'] == 'Bearer test-cloud-secret'
    body = json.loads(requests[0].content)
    assert body['response_format'] == {'type': 'json_object'}
    assert 'test-cloud-secret' not in requests[0].content.decode()


def test_llm_client_does_not_close_shared_injected_transport():
    async def run():
        async with httpx.AsyncClient() as client:
            await LLMClient(ModelRegistry('full'), client).aclose()
            assert not client.is_closed
    asyncio.run(run())
