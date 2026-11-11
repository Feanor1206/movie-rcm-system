import asyncio
import json
import os
from contextlib import aclosing, asynccontextmanager
from urllib.parse import urlsplit

import httpx
from jsonschema import ValidationError, validate


class LLMUnavailableError(Exception):
    pass


class LLMProtocolError(Exception):
    pass


INTENT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["intent_type", "mode", "scope"],
    "properties": {
        "intent_type": {"type": "string", "enum": ["DISCOVERY", "CONVERSATIONAL_PATCH", "CLARIFICATION", "NO_OP"]},
        "mode": {"type": "string", "enum": ["find_moment", "recommend", "catalog_question", "chitchat"]},
        "scope": {"type": "string", "enum": ["series", "episode", "scene"]},
        "semantic_query": {"type": "string", "maxLength": 4000},
        "requested_k": {"type": "integer", "minimum": 1, "maximum": 100},
        "constraints": {
            "type": "object", "additionalProperties": False,
            "properties": {
                "include_genres": {"type": "array", "maxItems": 20, "items": {"type": "string", "maxLength": 80}},
                "exclude_genres": {"type": "array", "maxItems": 20, "items": {"type": "string", "maxLength": 80}},
                "year_min": {"type": "integer", "minimum": 1800, "maximum": 2200},
                "year_max": {"type": "integer", "minimum": 1800, "maximum": 2200},
            },
        },
    },
}


class LLMClient:
    def __init__(self, registry, client=None):
        self.registry = registry
        self._client = client
        self._owns_client = client is None
        self.base_url = (os.getenv("LLM_BASE_URL") or os.getenv("DEEPSEEK_BASE_URL") or "https://api.deepseek.com").rstrip("/")
        self.model = (os.getenv("LLM_MODEL") or os.getenv("DEEPSEEK_MODEL") or "").strip()
        self.max_response_chars = 16000

    @property
    def client(self):
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=5.0, pool=5.0), limits=httpx.Limits(max_connections=4, max_keepalive_connections=2), follow_redirects=False, trust_env=False)
        return self._client

    def _headers(self, stream=False):
        headers = {"Content-Type": "application/json", "Accept": "text/event-stream" if stream else "application/json"}
        try:
            endpoint = urlsplit(self.base_url)
            is_local_http = endpoint.scheme == "http" and endpoint.hostname in {"localhost", "127.0.0.1", "::1"}
            if (not (endpoint.scheme == "https" or is_local_http)
                    or not endpoint.hostname or endpoint.username is not None
                    or endpoint.password is not None or endpoint.query or endpoint.fragment):
                raise ValueError
        except ValueError:
            raise LLMUnavailableError("Địa chỉ dịch vụ hội thoại không hợp lệ.") from None
        secret = os.getenv("LLM_API_KEY") or os.getenv("DEEPSEEK_API_KEY") or ("local" if is_local_http else "")
        if not secret or not self.model:
            raise LLMUnavailableError("CineBot chưa được cấu hình dịch vụ hội thoại.")
        headers["Authorization"] = f"Bearer {secret}"
        return headers

    @asynccontextmanager
    async def _slot(self):
        if self.registry.mode == "light":
            raise LLMUnavailableError("LLM is disabled in light mode")
        yield

    def _payload(self, messages, stream=False):
        payload = {"model": self.model, "messages": messages, "stream": stream, "max_tokens": 512, "temperature": 0.1}
        if urlsplit(self.base_url).hostname == "api.deepseek.com":
            payload["thinking"] = {"type": "disabled"}
        return payload

    async def stream(self, messages):
        try:
            async with asyncio.timeout(60):
                async with aclosing(self._stream(messages)) as stream:
                    async for part in stream:
                        yield part
        except TimeoutError:
            self.registry.set_llm_status(False, "Conversation provider timed out")
            raise LLMUnavailableError("Dịch vụ hội thoại phản hồi quá lâu. Vui lòng thử lại.") from None

    async def _stream(self, messages):
        try:
            async with self._slot():
                async with self.client.stream("POST", self.base_url + "/chat/completions", headers=self._headers(True), json=self._payload(messages, True)) as response:
                    if response.status_code != 200:
                        raise LLMUnavailableError("Dịch vụ hội thoại hiện chưa sẵn sàng.")
                    if "text/event-stream" not in response.headers.get("content-type", ""):
                        raise LLMProtocolError("Dịch vụ hội thoại trả về định dạng không hợp lệ.")
                    total = 0
                    saw_content = False
                    completed = False
                    async for line in response.aiter_lines():
                        if len(line) > 65536:
                            raise LLMProtocolError("Dữ liệu hội thoại vượt giới hạn.")
                        if not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if data == "[DONE]":
                            completed = True
                            break
                        if not data:
                            continue
                        try:
                            event = json.loads(data)
                            choices = event["choices"]
                            if not choices and "usage" in event:
                                continue
                            choice = choices[0]
                            delta = choice["delta"]
                            text = delta.get("content")
                            if text is not None and not isinstance(text, str):
                                raise TypeError
                            finish_reason = choice.get("finish_reason")
                            if finish_reason == "stop":
                                completed = True
                            elif finish_reason is not None:
                                raise ValueError
                        except (ValueError, KeyError, IndexError, TypeError, AttributeError):
                            raise LLMProtocolError("Dịch vụ hội thoại trả về dữ liệu không hợp lệ.") from None
                        if text:
                            total += len(text)
                            if total > self.max_response_chars:
                                raise LLMProtocolError("Nội dung hội thoại vượt giới hạn.")
                            self.registry.set_llm_status(True)
                            saw_content = True
                            yield text
                    if not saw_content or not completed:
                        raise LLMProtocolError("Luồng hội thoại kết thúc trước khi hoàn tất.")
        except (httpx.HTTPError, LLMUnavailableError):
            self.registry.set_llm_status(False, "Conversation provider is unavailable")
            raise LLMUnavailableError("Dịch vụ hội thoại hiện chưa sẵn sàng.") from None
        except LLMProtocolError:
            self.registry.set_llm_status(False, "Conversation provider returned invalid output")
            raise

    async def parse_intent(self, messages):
        try:
            async with asyncio.timeout(15):
                return await self._parse_intent(messages)
        except TimeoutError:
            self.registry.set_llm_status(False, "Intent provider timed out")
            raise LLMUnavailableError("Dịch vụ phân tích yêu cầu phản hồi quá lâu.") from None

    async def _parse_intent(self, messages):
        try:
            async with self._slot():
                headers = self._headers()
                payload = self._payload(messages)
                payload["response_format"] = {"type": "json_object"}
                payload["messages"] = [{"role": "system", "content": "Return only JSON matching this schema: " + json.dumps(INTENT_SCHEMA, ensure_ascii=False)}] + messages
                response = await self.client.post(self.base_url + "/chat/completions", headers=headers, json=payload)
                if response.status_code != 200:
                    raise LLMUnavailableError("Dịch vụ phân tích yêu cầu hiện chưa sẵn sàng.")
                if len(response.content) > 65536:
                    raise LLMProtocolError("Dữ liệu phân tích vượt giới hạn.")
                data = response.json()
                parsed = json.loads(data["choices"][0]["message"]["content"])
                validate(parsed, INTENT_SCHEMA)
                self.registry.set_llm_status(True)
                return parsed
        except (httpx.HTTPError, LLMUnavailableError):
            self.registry.set_llm_status(False, "Conversation provider is unavailable")
            raise LLMUnavailableError("Dịch vụ hội thoại hiện chưa sẵn sàng.") from None
        except (ValueError, KeyError, IndexError, TypeError, ValidationError):
            self.registry.set_llm_status(False, "Conversation provider returned invalid intent")
            raise LLMProtocolError("Dịch vụ phân tích trả về dữ liệu không hợp lệ.") from None

    async def aclose(self):
        if self._owns_client and self._client is not None:
            await self._client.aclose()
