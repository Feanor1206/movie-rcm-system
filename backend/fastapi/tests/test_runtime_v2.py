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
    monkeypatch.setenv("LLAMA_SERVER_URL", "http://local.invalid:8081/v1")
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
    assert str(requests[0].url) == "http://local.invalid:8081/v1/chat/completions"
    assert json.loads(requests[0].content)["stream"] is True


def test_llm_cloud_secret_never_leaks_and_readiness_recovers(monkeypatch):
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


def test_cancelled_provider_stream_closes_connection_and_releases_gpu():
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
            with registry.gpu_slot():
                pass
    asyncio.run(run())


@pytest.mark.parametrize("payload", [b'data: nope\n\n', b'data: {"choices": []}\n\n', b'data: {"choices":[{"delta":{"content":12}}]}\n\n'])
def test_llm_rejects_invalid_provider_stream(payload):
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200, headers={"content-type": "text/event-stream"}, content=payload))) as client:
            with pytest.raises(LLMProtocolError):
                _ = [part async for part in LLMClient(ModelRegistry("full"), client=client).stream([])]
    asyncio.run(run())


def test_intent_grammar_and_enum_are_validated():
    requests = []
    async def run():
        def handler(request):
            requests.append(json.loads(request.content))
            return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps({"intent_type": "UPDATE_CONSTRAINTS", "mode": "find_moment", "scope": "episode"})}}]})
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with pytest.raises(LLMProtocolError):
                await LLMClient(ModelRegistry("full"), client=client).parse_intent([])
    asyncio.run(run())
    schema = requests[0]["response_format"]["json_schema"]["schema"]
    assert schema["properties"]["intent_type"]["enum"] == ["DISCOVERY", "CONVERSATIONAL_PATCH", "CLARIFICATION", "NO_OP"]


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


def test_llm_hallucinated_episode_and_timestamp_are_not_exposed():
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


def test_chat_provider_error_falls_back_without_exposing_details():
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


def test_chat_delivers_text_before_provider_finishes():
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
        tokens = [data["text"]]
        while "Chi làm vỡ bình hoa." not in "".join(tokens):
            event, data = await asyncio.wait_for(anext(stream), 0.2)
            if event == "token":
                tokens.append(data["text"])
        finish.set()
        events = [item async for item in stream]
        assert events[-1][0] == "done"
        assert events[-1][1]["text"].startswith("".join(tokens))
    asyncio.run(run())


def test_full_chat_uses_intent_client_for_complex_queries_and_preserves_explicit_constraints():
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
    assert parsed
    assert searched[0] == ("bình hoa", {"year_max": 2009})
