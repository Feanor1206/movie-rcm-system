import httpx
import pytest
from ai.enrich import deepseek_offline as offline
from ai.enrich.caption import DurableBudget, Image


def frame(tmp_path):
    import hashlib
    path = tmp_path / 'frame.jpg'
    path.write_bytes(b'frame')
    return Image(path, 0, hashlib.sha256(b'frame').hexdigest(), 'image/jpeg')


def test_probe_is_durable_and_reused(tmp_path):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={'choices': [{'message': {'content': 'ok'}}], 'usage': {'total_tokens': 7}})
    budget = DurableBudget(tmp_path / 'budget.sqlite', 'pilot', 40)
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert offline.capability_probe(frame(tmp_path), 'model', 'https://api.example', 'secret', budget, client) == 'vision'
        assert offline.capability_probe(frame(tmp_path), 'model', 'https://api.example', 'secret', budget, client) == 'vision'
    assert len(calls) == 1
    assert budget.sent == 1


def test_explicit_image_rejection_enables_local_only(tmp_path):
    budget = DurableBudget(tmp_path / 'budget.sqlite', 'pilot', 40)
    transport = httpx.MockTransport(lambda request: httpx.Response(400, json={'error': {'message': 'image_url is not supported'}}))
    with httpx.Client(transport=transport) as client:
        assert offline.capability_probe(frame(tmp_path), 'model', 'https://api.example', 'secret', budget, client) == 'local'


@pytest.mark.parametrize('status', [401, 429, 500])
def test_unknown_probe_stops_and_never_retries(tmp_path, status):
    budget = DurableBudget(tmp_path / 'budget.sqlite', 'pilot', 40)
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(status, json={'error': {'message': 'image_url is not supported'}})
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(ValueError, match='inconclusive'):
            offline.capability_probe(frame(tmp_path), 'model', 'https://api.example', 'secret', budget, client)
        with pytest.raises(ValueError, match='inconclusive'):
            offline.capability_probe(frame(tmp_path), 'model', 'https://api.example', 'secret', budget, client)
    assert len(calls) == 1


def test_local_endpoint_must_be_loopback():
    assert offline.local_endpoint('http://127.0.0.1:8080/v1') == 'http://127.0.0.1:8080/v1'
    with pytest.raises(ValueError):
        offline.local_endpoint('https://example.com/v1')

def test_deepseek_json_mode_includes_schema():
    seen = []
    class Client:
        def post(self, url, **kwargs):
            seen.append(kwargs['json'])
    offline.DeepSeekClient(Client()).post('https://api.example', json={
        'messages': [{'role': 'system', 'content': 'Return JSON'}],
        'response_format': {'type': 'json_schema', 'json_schema': {'schema': {'type': 'object', 'required': ['summary']}}},
    })
    assert seen[0]['response_format'] == {'type': 'json_object'}
    assert 'summary' in seen[0]['messages'][0]['content']


def test_network_failure_is_inconclusive_and_not_retried(tmp_path):
    budget = DurableBudget(tmp_path / 'budget.sqlite', 'pilot', 40)
    calls = []
    def handler(request):
        calls.append(request)
        raise httpx.ReadTimeout('secret must not be logged')
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        for _ in range(2):
            with pytest.raises(ValueError, match='inconclusive') as exc:
                offline.capability_probe(frame(tmp_path), 'model', 'https://api.example', 'secret', budget, client)
            assert 'secret' not in str(exc.value)
    assert len(calls) == 1

def test_deepseek_response_with_escaped_secret_is_not_cached():
    secret = 'test-secret'
    class Client:
        def post(self, url, **kwargs):
            return httpx.Response(200, text='{"message":"test-\\u0073ecret"}')
    with pytest.raises(ValueError, match='credential'):
        offline.DeepSeekClient(Client(), secret).post('https://api.example', json={
            'messages': [{'role': 'system', 'content': 'Return JSON'}],
            'response_format': {'type': 'json_schema', 'json_schema': {'schema': {'type': 'object'}}},
        })
