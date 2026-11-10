import asyncio
import os
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.llm_client import LLMClient
from services.model_registry import ModelRegistry

pytestmark = pytest.mark.skipif(os.getenv('RUN_FULL_INTEGRATION') != '1', reason='External GPU llama-server integration requires RUN_FULL_INTEGRATION=1')


def test_full_model_live_stream_health_and_readiness():
    async def run():
        registry = ModelRegistry('full')
        client = LLMClient(registry)
        try:
            chunks = [part async for part in client.stream([{'role': 'user', 'content': 'Say hello in Vietnamese in one short sentence.'}])]
            assert ''.join(chunks).strip()
            health = registry.health()
            assert health['modelLoaded']
            assert health['activeInferenceBackend'] == 'llama-server'
            assert health['activeBaseModelName']
            assert not registry.readiness()['features']['search']['ready']
            assert registry.readiness()['features']['llm']['ready']
        finally:
            await client.aclose()
    asyncio.run(run())


def test_full_model_live_grammar_constrained_intent():
    async def run():
        client = LLMClient(ModelRegistry('full'))
        try:
            start = time.monotonic()
            intent = await client.parse_intent([{'role': 'system', 'content': 'Parse the user request into discovery intent. Preserve year and excluded genres.'}, {'role': 'user', 'content': 'Gợi ý phim hoạt hình trước năm 2010 không có kinh dị'}])
            assert time.monotonic() - start < 120
            assert intent['intent_type'] == 'DISCOVERY'
            assert intent['mode'] in {'find_moment', 'recommend'}
            assert intent['constraints']['year_max'] == 2009
            assert any(value.casefold() in {'horror', 'kinh dị'} for value in intent['constraints']['exclude_genres'])
        finally:
            await client.aclose()
    asyncio.run(run())
