import asyncio
import re

from services.intent import deterministic_intent
from services.llm_client import LLMProtocolError, LLMUnavailableError
from services.model_registry import InferenceCapacityError
from services.pilot_catalog import evidence_for_results
from services.rag import catalog_reply, source_intro, summarize_sources


_TOKEN_STREAM_RE = re.compile(r"\S+\s*")


def build_follow_ups(results):
    if not results:
        return ["Gợi ý tập phim nổi bật", "Tìm phim hài gia đình"]
    top = results[0]
    suggestions = []
    characters = top.get("characters") or []
    if isinstance(characters, list) and characters and isinstance(characters[0], str):
        suggestions.append(f"Tìm thêm cảnh có {characters[0]}")
    genres = top.get("genres") or []
    if isinstance(genres, list) and genres and isinstance(genres[0], str):
        suggestions.append(f"Gợi ý thêm phim thể loại {genres[0]}")
    if len(results) > 1:
        suggestions.append("Không, tập khác")
    if top.get("startMs") is not None or top.get("start_ms") is not None:
        suggestions.append("Cảnh sau đó thì sao")
    return list(dict.fromkeys(suggestions))[:3]


class ChatService:
    def __init__(self, registry, search_callable, llm_client=None):
        self.registry = registry
        self.search = search_callable
        self.llm = llm_client

    async def _approved_sources(self, results):
        if self.registry.mode != "cloud" or self.llm is None or not results:
            return []
        try:
            return await asyncio.to_thread(evidence_for_results, results)
        except (OSError, ValueError, KeyError, TypeError):
            return []

    async def stream(self, query, history=None, session_id="default", snapshot=None):
        intent = deterministic_intent(query, history)
        mode = intent["mode"]
        try:
            results = [] if mode == "chitchat" else await asyncio.to_thread(
                self.search, snapshot, intent["semantic_query"],
                limit=intent["requested_k"], constraints=intent["constraints"],
            )
        except InferenceCapacityError:
            yield "error", {"text": "CineBot đang bận. Thử lại sau."}
            return
        except Exception:
            yield "error", {"text": "CineBot hiện chưa sẵn sàng. Bạn có thể tìm trong Kho phim."}
            return

        metadata = {
            "recommendedMovies": [dict(item) for item in results],
            "followUps": build_follow_ups(results),
            "structuredIntent": intent,
            "pipelineStages": {"retrieval": "accepted-snapshot", "conversation": "template", "grounded": True},
        }
        yield "metadata", metadata

        sources = await self._approved_sources(results)
        if sources:
            first = sources[0]
            prefix = source_intro(first["title"], first.get("startMs"), mode) + " "
            yield "token", {"text": prefix}
            try:
                answer = await summarize_sources(self.llm, intent, sources)
            except (LLMUnavailableError, InferenceCapacityError):
                answer = "Dịch vụ hội thoại hiện chưa sẵn sàng. " + " ".join(first["evidence"])
            except LLMProtocolError:
                answer = " ".join(first["evidence"])
            else:
                metadata["pipelineStages"]["conversation"] = "cloud"
            text = prefix + answer
            yield "token", {"text": answer}
        else:
            text = catalog_reply(results, mode)
            for match in _TOKEN_STREAM_RE.finditer(text):
                yield "token", {"text": match.group(0)}
                await asyncio.sleep(0)
        yield "done", {"text": text, **metadata}
