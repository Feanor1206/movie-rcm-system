import asyncio
import re

from services.intent import deterministic_intent, fold_text
from services.llm_client import LLMProtocolError, LLMUnavailableError
from services.model_registry import InferenceCapacityError
from services.pilot_catalog import evidence_for_results, evidence_for_snapshot_results
from services.rag import catalog_reply, series_reply, source_intro, summarize_sources


_TOKEN_STREAM_RE = re.compile(r"\S+\s*")
_CHEERFUL_RE = re.compile(r"\b(?:vui|hai huoc|hai|comedy|funny|cheerful|humor|humour|laugh|tich cuc|am ap)\b")
_SAD_RE = re.compile(r"\b(?:buon|sad|sadness|melancholy|bi kich|tragic|tragedy)\b")


def mood_evidence_score(item, target):
    values = []
    for field in ("genres", "keywords", "themes", "mood", "moods", "emotion", "emotions", "plot_facts"):
        value = item.get(field)
        if isinstance(value, str):
            values.append(value)
        elif isinstance(value, list):
            values.extend(entry for entry in value if isinstance(entry, str))
    for field in ("description", "synopsis", "visual_summary", "dialogue_summary"):
        value = item.get(field)
        if isinstance(value, str):
            title = item.get("title") or ""
            values.append(value.replace(title, "") if title else value)
    for evidence in item.get("evidence") or []:
        if isinstance(evidence, dict) and evidence.get("itemType") in ("scene", "segment", "dialogue") and isinstance(evidence.get("text"), str):
            values.append(evidence["text"])
    pattern = _SAD_RE if target == "sad" else _CHEERFUL_RE
    return len(pattern.findall(fold_text(" ".join(values))))


def build_follow_ups(results):
    if not results:
        return ["Gợi ý tập phim nổi bật", "Tìm phim hài gia đình"]
    top = results[0]
    suggestions = []
    characters = top.get("characters") or []
    if isinstance(characters, list) and characters and isinstance(characters[0], str):
        suggestions.append(f"Tìm thêm cảnh có {characters[0]}")
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

    async def _approved_sources(self, results, snapshot):
        if self.registry.mode != "cloud" or self.llm is None or not results:
            return []
        try:
            evidence = await asyncio.to_thread(evidence_for_snapshot_results, snapshot, results)
            if evidence is not None:
                return evidence
            return await asyncio.to_thread(evidence_for_results, results)
        except (OSError, ValueError, KeyError, TypeError):
            return []

    async def stream(self, query, history=None, session_id="default", snapshot=None):
        intent = deterministic_intent(query, history)
        mode = intent["mode"]
        mood = intent["mood_recommendation"]
        target = intent["mood_target"]
        series_info = intent["series_info"]
        try:
            results = [] if mode == "chitchat" else await asyncio.to_thread(
                self.search, snapshot, intent["semantic_query"] + ((" buồn bi kịch sad" if target == "sad" else " hài hước vui nhộn comedy") if mood else ""),
                limit=100 if mood else intent["requested_k"], constraints=intent["constraints"],
            )
            if mood:
                episode_request = bool(re.search(r"\b(?:tap|episode)\b", fold_text(intent["semantic_query"])))
                ranked = [(mood_evidence_score(item, target), index, item) for index, item in enumerate(results)
                          if not episode_request or item.get("item_type") != "series"]
                def rank(entry):
                    score, index, item = entry
                    runtime = re.fullmatch(r"(\d+)m", str(item.get("runtime") or ""))
                    long_episode = episode_request and runtime is not None and int(runtime.group(1)) > 90
                    return (long_episode, -score, index)
                results = [item for score, _, item in sorted(ranked, key=rank) if score > 0][:intent["requested_k"]]
        except InferenceCapacityError:
            yield "error", {"text": "CineBot đang bận. Thử lại sau."}
            return
        except Exception:
            yield "error", {"text": "CineBot hiện chưa sẵn sàng. Bạn có thể tìm trong Kho phim."}
            return

        metadata = {
            "recommendedMovies": [dict(item) for item in results],
            "followUps": [] if results and (mood or series_info) else build_follow_ups(results),
            "structuredIntent": intent,
            "pipelineStages": {"retrieval": "accepted-snapshot", "conversation": "template", "grounded": True},
        }
        yield "metadata", metadata

        sources = await self._approved_sources(results, snapshot) if not (mood or series_info) else []
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
            if series_info:
                text = series_reply(results, series_info)
            elif mood and results:
                text = "Bạn thử tập này nhé." if len(results) == 1 else "Bạn thử mấy tập này nhé."
            else:
                text = catalog_reply(results, mode)
            for match in _TOKEN_STREAM_RE.finditer(text):
                yield "token", {"text": match.group(0)}
                await asyncio.sleep(0)
        yield "done", {"text": text, **metadata}
