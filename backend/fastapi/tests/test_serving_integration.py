import asyncio
import os
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.llm_client import LLMClient
from services.model_registry import ModelRegistry
from services.pilot_catalog import evidence_for_results

pytestmark = pytest.mark.skipif(os.getenv('RUN_DEEPSEEK_INTEGRATION') != '1', reason='Live paid DeepSeek integration requires RUN_DEEPSEEK_INTEGRATION=1')


def pilot_message():
    episode = 'ep_jadoo_s01_0022'
    evidence = evidence_for_results([{'episodeId': episode, 'evidence': [{'documentId': episode}]}])
    return {'role': 'user', 'content': evidence[0]['title']}


def test_cloud_model_live_stream_health_and_readiness():
    async def run():
        registry = ModelRegistry('cloud')
        client = LLMClient(registry)
        try:
            chunks = [part async for part in client.stream([{'role': 'system', 'content': 'Repeat the pilot episode title.'}, pilot_message()])]
            assert ''.join(chunks).strip()
            health = registry.health()
            assert health['modelLoaded']
            assert health['activeInferenceBackend'] == 'deepseek'
            assert health['activeBaseModelName']
            assert not registry.readiness()['features']['search']['ready']
            assert registry.readiness()['features']['llm']['ready']
        finally:
            await client.aclose()
    asyncio.run(run())


def test_cloud_model_live_validated_json_intent():
    async def run():
        client = LLMClient(ModelRegistry('cloud'))
        try:
            start = time.monotonic()
            intent = await client.parse_intent([{'role': 'system', 'content': 'Parse the pilot title into a catalog discovery intent.'}, pilot_message()])
            assert time.monotonic() - start < 120
            assert intent['intent_type'] == 'DISCOVERY'
            assert intent['mode'] in {'find_moment', 'recommend', 'catalog_question'}
        finally:
            await client.aclose()
    asyncio.run(run())
