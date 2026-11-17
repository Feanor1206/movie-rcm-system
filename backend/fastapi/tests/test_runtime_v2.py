import asyncio
import json
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.model_registry import ModelRegistry, InferenceCapacityError
from services.llm_client import LLMClient, LLMUnavailableError, LLMProtocolError
from services.chat import ChatService, deterministic_intent


def test_readiness_does_not_couple_search_to_llm(monkeypatch):
    monkeypatch.setenv("STRICT_READINESS", "true")
    registry = ModelRegistry("full")
    snapshot = SimpleNamespace(is_ready=True, hybrid_index=SimpleNamespace(is_ready=True))
    status = registry.readiness(snapshot)
    assert status["ready"]
    assert status["features"]["search"]["ready"]
    assert status["features"]["recommend"]["ready"]
    assert not status["features"]["llm"]["ready"]
    assert not status["features"]["frameSearch"]["ready"]


def test_registry_loads_factory_once_and_reports_missing_assets():
    registry = ModelRegistry("light")
    calls = []
    registry.register("reranker", lambda: calls.append(True) or object())
    results = []
    threads = [threading.Thread(target=lambda: results.append(registry.get("reranker"))) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(calls) == 1
    assert len({id(result) for result in results}) == 1
    assert registry.get("frame_encoder") is None


def test_sync_and_async_gpu_users_share_capacity_and_cancel_safely():
    async def run():
        registry = ModelRegistry("full", gpu_timeout=0.05)
        with registry.gpu_slot():
            with pytest.raises(InferenceCapacityError):
                async with registry.async_gpu_slot():
                    pytest.fail("shared GPU capacity was bypassed")
            task = asyncio.create_task(registry.async_gpu_slot().__aenter__())
            await asyncio.sleep(0)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        async with registry.async_gpu_slot():
            pass
        with registry.gpu_slot():
            pass
    asyncio.run(run())


class EventStream(httpx.AsyncByteStream):
    def __init__(self, chunks):
        self.chunks = chunks
        self.closed = False

    async def __aiter__(self):
        for chunk in self.chunks:
            yield chunk

    async def aclose(self):
        self.closed = True


def test_llm_stream_uses_external_server_and_closes_response(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://local.invalid:8081/v1")
    monkeypatch.setenv("DEEPSEEK_MODEL", "test-model")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    stream = EventStream([
        b'data: {"choices":[{"delta":{"content":"Xin "}}]}\n\n',
        'data: {"choices":[{"delta":{"content":"chào"}}]}\n\n'.encode(),
        b'data: [DONE]\n\n',
    ])
    requests = []
    async def run():
        def handler(request):
            requests.append(request)
            return httpx.Response(200, headers={"content-type": "text/event-stream"}, stream=stream)
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            registry = ModelRegistry("full")
            llm = LLMClient(registry, client=client)
            pieces = [text async for text in llm.stream([{"role": "user", "content": "hi"}])]
            assert pieces == ["Xin ", "chào"]
            assert registry.llm_ready
        assert stream.closed
    asyncio.run(run())
    assert str(requests[0].url) == "https://local.invalid:8081/v1/chat/completions"
    assert json.loads(requests[0].content)["stream"] is True
    assert json.loads(requests[0].content)["model"] == "test-model"
    assert requests[0].headers["authorization"] == "Bearer test-key"


def test_llm_cloud_secret_never_leaks_and_readiness_recovers(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_MODEL", "test-model")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "private-api-key")
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(401, text="private-api-key"))) as client:
            registry = ModelRegistry("cloud")
            llm = LLMClient(registry, client=client)
            with pytest.raises(LLMUnavailableError) as error:
                _ = [part async for part in llm.stream([{"role": "user", "content": "hello"}])]
            assert "private-api-key" not in str(error.value)
            assert "private-api-key" not in str(registry.health())
            assert not registry.llm_ready
    asyncio.run(run())


def test_cancelled_provider_stream_closes_connection(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_MODEL", "test-model")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    class WaitingStream(EventStream):
        async def __aiter__(self):
            yield b'data: {"choices":[{"delta":{"content":"hello"}}]}\n\n'
            await asyncio.Event().wait()
    async def run():
        provider = WaitingStream([])
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200, headers={"content-type": "text/event-stream"}, stream=provider))) as client:
            registry = ModelRegistry("full", gpu_timeout=0.05)
            stream = LLMClient(registry, client=client).stream([])
            assert await anext(stream) == "hello"
            task = asyncio.create_task(anext(stream))
            await asyncio.sleep(0)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            assert provider.closed
    asyncio.run(run())


@pytest.mark.parametrize("payload", [b'data: nope\n\n', b'data: {"choices": []}\n\n', b'data: {"choices":[{"delta":{"content":12}}]}\n\n'])
def test_llm_rejects_invalid_provider_stream(payload, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_MODEL", "test-model")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200, headers={"content-type": "text/event-stream"}, content=payload))) as client:
            with pytest.raises(LLMProtocolError):
                _ = [part async for part in LLMClient(ModelRegistry("full"), client=client).stream([])]
    asyncio.run(run())


def test_intent_grammar_and_enum_are_validated(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_MODEL", "test-model")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    requests = []
    async def run():
        def handler(request):
            requests.append(json.loads(request.content))
            return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps({"intent_type": "UPDATE_CONSTRAINTS", "mode": "find_moment", "scope": "episode"})}}]})
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with pytest.raises(LLMProtocolError):
                await LLMClient(ModelRegistry("full"), client=client).parse_intent([])
    asyncio.run(run())
    assert requests[0]["response_format"] == {"type": "json_object"}
    assert "CONVERSATIONAL_PATCH" in requests[0]["messages"][0]["content"]


MOVIE = {"id": "episode-12", "episodeId": "episode-12", "title": "Tập 12: Bình hoa", "startMs": 520000,
         "evidence": [{"documentId": "scene-12", "text": "Chi làm vỡ bình hoa.", "startMs": 520000, "endMs": 530000, "itemType": "scene"}]}


def test_light_chat_streams_same_grounded_contract_without_llm():
    calls = []
    def search(snapshot, query, limit=8, constraints=None):
        calls.append((threading.current_thread().name, snapshot, query, constraints))
        return [MOVIE]
    async def run():
        events = [event async for event in ChatService(ModelRegistry("light"), search).stream("Chi làm vỡ bình hoa", snapshot="captured")]
        assert events[0][0] == "metadata"
        assert events[-1][0] == "done"
        text = "".join(data["text"] for event, data in events if event == "token")
        assert events[-1][1]["text"] == text
        assert "08:40" in text
        assert "Chi làm vỡ bình hoa." in text
        assert events[-1][1]["recommendedMovies"] == [MOVIE]
    asyncio.run(run())
    assert calls[0][0] != threading.main_thread().name
    assert calls[0][1] == "captured"


def test_llm_hallucinated_episode_and_timestamp_are_not_exposed(monkeypatch):
    import services.chat as chat_module
    monkeypatch.setattr(chat_module, "evidence_for_results", lambda results: [{"title": MOVIE["title"], "startMs": MOVIE["startMs"], "evidence": ["Chi làm vỡ bình hoa."]}])
    class FakeLLM:
        async def stream(self, messages):
            for text in ["Tập 999 ", "ở 55:55 có trận đánh."]:
                yield text
    async def run():
        events = [event async for event in ChatService(ModelRegistry("full"), lambda *args, **kwargs: [MOVIE], FakeLLM()).stream("bình hoa")]
        serialized = json.dumps(events, ensure_ascii=False)
        assert "999" not in serialized
        assert "55:55" not in serialized
        assert "Chi làm vỡ bình hoa." in serialized
    asyncio.run(run())


def test_chat_patch_uses_request_history_without_global_sessions():
    intent = deterministic_intent("không lấy phim kinh dị, chỉ 2 kết quả", [{"role": "user", "content": "Chi làm vỡ bình hoa trước năm 2010"}])
    assert intent["intent_type"] == "CONVERSATIONAL_PATCH"
    assert "bình hoa" in intent["semantic_query"]
    assert intent["constraints"]["year_max"] == 2009
    assert "horror" in intent["constraints"]["exclude_genres"]
    assert intent["requested_k"] == 2


def test_chat_provider_error_falls_back_without_exposing_details(monkeypatch):
    import services.chat as chat_module
    monkeypatch.setattr(chat_module, "evidence_for_results", lambda results: [{"title": MOVIE["title"], "startMs": MOVIE["startMs"], "evidence": ["Chi làm vỡ bình hoa."]}])
    class FakeLLM:
        async def stream(self, messages):
            raise LLMUnavailableError("private server detail")
            yield
    async def run():
        events = [event async for event in ChatService(ModelRegistry("full"), lambda *args, **kwargs: [MOVIE], FakeLLM()).stream("bình hoa")]
        assert events[-1][0] == "done"
        assert "private server detail" not in json.dumps(events)
        assert "Chi làm vỡ bình hoa." in events[-1][1]["text"]
    asyncio.run(run())


def test_chat_delivers_text_before_provider_finishes(monkeypatch):
    import services.chat as chat_module
    monkeypatch.setattr(chat_module, "evidence_for_results", lambda results: [{"title": MOVIE["title"], "startMs": MOVIE["startMs"], "evidence": ["Chi làm vỡ bình hoa."]}])
    async def run():
        waiting = asyncio.Event()
        finish = asyncio.Event()
        class FakeLLM:
            async def stream(self, messages):
                yield "Chi làm vỡ bình hoa. "
                waiting.set()
                await finish.wait()
        stream = ChatService(ModelRegistry("full"), lambda *args, **kwargs: [MOVIE], FakeLLM()).stream("bình hoa")
        assert (await anext(stream))[0] == "metadata"
        event, data = await asyncio.wait_for(anext(stream), 0.2)
        assert event == "token"
        assert data["text"]
        finish.set()
        events = [item async for item in stream]
        assert events[-1][0] == "done"
        assert events[-1][1]["text"].startswith(data["text"])
        assert "Chi làm vỡ bình hoa." in events[-1][1]["text"]
    asyncio.run(run())


def test_cloud_chat_keeps_query_local_and_preserves_explicit_constraints():
    parsed = []
    searched = []
    class FakeLLM:
        async def parse_intent(self, messages):
            parsed.append(messages)
            return {"intent_type": "DISCOVERY", "mode": "find_moment", "scope": "scene", "semantic_query": "bình hoa", "constraints": {"year_max": 2020}}
        async def stream(self, messages):
            yield "Chi làm vỡ bình hoa."
    def search(snapshot, query, limit=8, constraints=None):
        searched.append((query, constraints))
        return [MOVIE]
    async def run():
        _ = [event async for event in ChatService(ModelRegistry("full"), search, FakeLLM()).stream("bình hoa trước năm 2010")]
    asyncio.run(run())
    assert not parsed
    assert searched[0] == ("bình hoa trước năm 2010", {"year_max": 2009})


def test_cloud_only_sends_trusted_pilot_evidence_and_rejects_invented_reference(monkeypatch):
    import services.chat as chat_module
    sent = []
    trusted = [{"title": "Tập 12: Bình hoa", "startMs": 520000, "evidence": ["Chi làm vỡ bình hoa."]}]
    monkeypatch.setattr(chat_module, "evidence_for_results", lambda results: trusted)
    class FakeLLM:
        async def stream(self, messages):
            sent.extend(messages)
            yield "Tập 999 ở 55:55."
    private = {**MOVIE, "evidence": [{"text": "DATABASE SECRET"}]}
    async def run():
        events = [item async for item in ChatService(ModelRegistry("cloud"), lambda *a, **k: [private], FakeLLM()).stream("PRIVATE QUERY", history=[{"role": "user", "content": "PRIVATE HISTORY"}])]
        assert "999" not in events[-1][1]["text"]
        assert "55:55" not in events[-1][1]["text"]
        assert "Bình hoa" in events[-1][1]["text"]
    asyncio.run(run())
    serialized = json.dumps(sent, ensure_ascii=False)
    assert "PRIVATE QUERY" not in serialized
    assert "PRIVATE HISTORY" not in serialized
    assert "DATABASE SECRET" not in serialized
    assert "Chi làm vỡ bình hoa" in serialized


def test_cloud_does_not_call_provider_without_trusted_evidence(monkeypatch):
    import services.chat as chat_module
    monkeypatch.setattr(chat_module, "evidence_for_results", lambda results: [])
    class FakeLLM:
        async def stream(self, messages):
            pytest.fail("untrusted data reached provider")
            yield
    async def run():
        events = [item async for item in ChatService(ModelRegistry("cloud"), lambda *a, **k: [MOVIE], FakeLLM()).stream("bình hoa")]
        assert "Chi làm vỡ bình hoa" in events[-1][1]["text"]
    asyncio.run(run())


def test_followups_reuse_previous_search_locally():
    history = [{"role": "user", "content": "Chi làm vỡ bình hoa"}]
    for query in ["không, tập khác", "cảnh sau đó thì sao"]:
        intent = deterministic_intent(query, history)
        assert intent["intent_type"] == "CONVERSATIONAL_PATCH"
        assert "Chi làm vỡ bình hoa" in intent["semantic_query"]


def test_cloud_accepts_bounded_paraphrase_and_falls_back_on_new_facts(monkeypatch):
    import services.chat as chat_module
    monkeypatch.setattr(chat_module, "evidence_for_results", lambda results: [{"title": "Tập 12: Bình hoa", "startMs": 520000, "evidence": ["Chi làm vỡ bình hoa."]}])
    class FakeLLM:
        def __init__(self, response):
            self.response = response
        async def stream(self, messages):
            yield self.response
    async def run():
        async def answer(response):
            events = [item async for item in ChatService(ModelRegistry("cloud"), lambda *a, **k: [MOVIE], FakeLLM(response)).stream("bình hoa")]
            return events[-1][1]["text"]
        assert "Chi đã làm vỡ bình hoa." in await answer("Chi đã làm vỡ bình hoa.")
        result = await answer("Chi giết người.")
        assert "giết người" not in result
        assert "Chi làm vỡ bình hoa." in result
    asyncio.run(run())


def test_official_deepseek_disables_thinking_for_bounded_response(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
    assert LLMClient(ModelRegistry("cloud"))._payload([])["thinking"] == {"type": "disabled"}
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://gateway.example/v1")
    assert "thinking" not in LLMClient(ModelRegistry("cloud"))._payload([])


def test_provider_echo_of_api_key_is_not_emitted(monkeypatch):
    import services.chat as chat_module
    monkeypatch.setenv("DEEPSEEK_API_KEY", "Chi")
    monkeypatch.setattr(chat_module, "evidence_for_results", lambda results: [{"title": "Tập 12", "startMs": 520000, "evidence": ["Chi làm vỡ bình hoa."]}])
    class FakeLLM:
        async def stream(self, messages):
            yield "Chi"
    async def run():
        events = [item async for item in ChatService(ModelRegistry("cloud"), lambda *a, **k: [MOVIE], FakeLLM()).stream("bình hoa")]
        assert events[-1][1]["text"].endswith("Chi làm vỡ bình hoa.")
        assert events[-1][1]["pipelineStages"]["conversation"] == "template"
    asyncio.run(run())


def test_cloud_requires_explicit_model_before_request(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_MODEL", raising=False)
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    def handler(request):
        pytest.fail("request sent without configured model")
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with pytest.raises(LLMUnavailableError):
                _ = [part async for part in LLMClient(ModelRegistry("cloud"), client).stream([])]
    asyncio.run(run())


def test_pilot_intent_receives_only_enums_and_catalog_and_rejects_mismatch(monkeypatch):
    import services.chat as chat_module
    monkeypatch.setattr(chat_module, "evidence_for_results", lambda results: [{"title": "Tập 12", "startMs": 520000, "evidence": ["Chi làm vỡ bình hoa."]}])
    requests = []
    class FakeLLM:
        async def parse_intent(self, messages):
            requests.extend(messages)
            return {"intent_type": "NO_OP", "mode": "chitchat", "scope": "series", "semantic_query": "invented"}
        async def stream(self, messages):
            yield "Chi làm vỡ bình hoa."
    async def run():
        events = [item async for item in ChatService(ModelRegistry("cloud"), lambda *a, **k: [MOVIE], FakeLLM()).stream("PRIVATE QUERY", history=[{"role": "user", "content": "PRIVATE HISTORY"}])]
        intent = events[-1][1]["structuredIntent"]
        assert intent["intent_type"] == "DISCOVERY"
        assert intent["semantic_query"] == "PRIVATE QUERY"
    asyncio.run(run())
    assert requests
    assert "PRIVATE" not in json.dumps(requests)
    assert "Chi làm vỡ bình hoa" in json.dumps(requests, ensure_ascii=False)


def test_intent_provider_outage_uses_template_without_second_call(monkeypatch):
    import services.chat as chat_module
    monkeypatch.setattr(chat_module, "evidence_for_results", lambda results: [{"title": "Tập 12", "startMs": 520000, "evidence": ["Chi làm vỡ bình hoa."]}])
    class FakeLLM:
        async def parse_intent(self, messages):
            raise LLMUnavailableError("private detail")
        async def stream(self, messages):
            pytest.fail("should not retry after outage")
            yield
    async def run():
        events = [item async for item in ChatService(ModelRegistry("cloud"), lambda *a, **k: [MOVIE], FakeLLM()).stream("bình hoa")]
        assert "chưa sẵn sàng" in events[-1][1]["text"]
        assert "private detail" not in events[-1][1]["text"]
    asyncio.run(run())


def test_valid_pilot_intent_refines_scope_but_keeps_local_followup(monkeypatch):
    import services.chat as chat_module
    monkeypatch.setattr(chat_module, "evidence_for_results", lambda results: [{"title": "Tập 12", "startMs": 520000, "evidence": ["Chi làm vỡ bình hoa."]}])
    class FakeLLM:
        async def parse_intent(self, messages):
            return {"intent_type": "CONVERSATIONAL_PATCH", "mode": "find_moment", "scope": "scene", "semantic_query": "wrong", "requested_k": 100}
        async def stream(self, messages):
            yield "Chi làm vỡ bình hoa."
    async def run():
        events = [item async for item in ChatService(ModelRegistry("cloud"), lambda *a, **k: [MOVIE], FakeLLM()).stream("không, tập khác", history=[{"role": "user", "content": "bình hoa"}])]
        intent = events[-1][1]["structuredIntent"]
        assert intent["intent_type"] == "CONVERSATIONAL_PATCH"
        assert intent["scope"] == "scene"
        assert intent["semantic_query"] == "bình hoa không, tập khác"
        assert intent["requested_k"] == 8
    asyncio.run(run())
