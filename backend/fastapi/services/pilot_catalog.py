import json
import os
from functools import lru_cache

from services.catalog_sync import CatalogSyncError, CatalogSyncManager
from services.runtime import ROOT
from services.text_index import TextIndex


PILOT_EPISODES = frozenset({"ep_jadoo_s01_0022", "ep_jadoo_s04_0021"})
PILOT_SOURCES = (ROOT / "ai/artifacts/pilot-published.json", ROOT / "data/catalog.jadoo_all.json")


def _allowed_episodes(package, is_published_package):
    if os.getenv("ALLOW_FULL_CATALOG_GROUNDING", "").lower() in {"1", "true", "yes"} or is_published_package:
        return {ep["id"] for ep in package.get("episodes", []) if isinstance(ep, dict) and ep.get("id")}
    extra = {ep.strip() for ep in os.getenv("APPROVED_CLOUD_EPISODES", "").split(",") if ep.strip()}
    return PILOT_EPISODES | extra


@lru_cache(maxsize=4)
def _read_documents(path, _version, full_grounding=False):
    with path.open(encoding="utf-8-sig") as stream:
        package = json.load(stream)
    manager = CatalogSyncManager()
    manager.load_from_payload(package, include_draft=False, include_private=False)
    is_published = path == PILOT_SOURCES[0]
    allowed = _allowed_episodes(package, is_published)
    items = [item for item in manager.get_flattened_catalog()
             if item.get("episode_id") in allowed or item["id"] in allowed]
    if is_published:
        package = {**package, "text_tracks": [track for track in package.get("text_tracks", [])
                   if (track.get("record") or {}).get("status") == "ready"]}
    index = TextIndex.build(items, payload=package, cache_dir=path.parent)
    return {document["id"]: document for document in index.documents}


def evidence_for_results(results):
    full_grounding = os.getenv("ALLOW_FULL_CATALOG_GROUNDING", "").lower() in {"1", "true", "yes"}
    extra = {ep.strip() for ep in os.getenv("APPROVED_CLOUD_EPISODES", "").split(",") if ep.strip()}
    allowed_base = PILOT_EPISODES | extra
    published_ids = set()
    sources = []
    for path in PILOT_SOURCES:
        try:
            stat = path.stat()
            docs = _read_documents(path, (stat.st_mtime_ns, stat.st_size), full_grounding)
            sources.append(docs)
            if path == PILOT_SOURCES[0]:
                published_ids.update(doc["id"] for doc in docs.values() if doc.get("item_type") == "episode")
        except (CatalogSyncError, OSError, ValueError, TypeError, KeyError, AttributeError):
            continue
    candidates = [
        result for result in results[:3]
        if full_grounding or result.get("episodeId") in (allowed_base | published_ids)
    ]
    if not candidates or not sources:
        return []
    evidence = []
    for result in candidates:
        episode_id = result["episodeId"]
        item = next(iter(result.get("evidence") or []), {})
        document_id = item.get("documentId")
        if not isinstance(document_id, str):
            continue
        for documents in sources:
            episode = documents.get(episode_id)
            document = documents.get(document_id)
            if not episode or not document or document.get("episode_id", document["id"]) != episode_id:
                continue
            if document.get("item_type") not in {"episode", "scene", "dialogue"}:
                continue
            start = document.get("_episode_start_ms", document.get("start_ms"))
            if start != result.get("startMs") or start is not None and type(start) is not int:
                continue
            text = document.get("dialogue_summary") or document.get("visual_summary") or document.get("description") or document.get("synopsis")
            if not isinstance(text, str) or not text.strip() or not episode.get("title"):
                continue
            evidence.append({"title": episode["title"], "startMs": start, "evidence": [text[:1200]]})
            break
    return evidence
