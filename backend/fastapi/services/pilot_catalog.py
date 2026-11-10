import json
from functools import lru_cache

from services.catalog_sync import CatalogSyncError, CatalogSyncManager
from services.runtime import ROOT
from services.text_index import TextIndex


PILOT_EPISODES = frozenset({"ep_jadoo_s01_0022", "ep_jadoo_s04_0021"})
PILOT_SOURCES = (ROOT / "ai/artifacts/pilot-published.json", ROOT / "data/catalog.jadoo_all.json")


@lru_cache(maxsize=4)
def _read_documents(path, _version):
    with path.open(encoding="utf-8-sig") as stream:
        package = json.load(stream)
    manager = CatalogSyncManager()
    manager.load_from_payload(package, include_draft=False, include_private=False)
    items = [item for item in manager.get_flattened_catalog()
             if item.get("episode_id") in PILOT_EPISODES or item["id"] in PILOT_EPISODES]
    if path == PILOT_SOURCES[0]:
        package = {**package, "text_tracks": [track for track in package.get("text_tracks", [])
                   if (track.get("record") or {}).get("status") == "ready"]}
    index = TextIndex.build(items, payload=package, cache_dir=path.parent)
    return {document["id"]: document for document in index.documents}


def evidence_for_results(results):
    candidates = [result for result in results[:3] if result.get("episodeId") in PILOT_EPISODES]
    if not candidates:
        return []
    sources = []
    for path in PILOT_SOURCES:
        try:
            stat = path.stat()
            sources.append(_read_documents(path, (stat.st_mtime_ns, stat.st_size)))
        except (CatalogSyncError, OSError, ValueError, TypeError, KeyError, AttributeError):
            continue
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
