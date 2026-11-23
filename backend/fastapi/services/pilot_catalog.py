import json
import os
import re
from functools import lru_cache

from services.catalog_sync import CatalogSyncError, CatalogSyncManager
from services.runtime import ROOT
from services.text_index import TextIndex


PILOT_EPISODES = frozenset({"ep_jadoo_s01_0022", "ep_jadoo_s04_0021"})
PILOT_SOURCES = (ROOT / "ai/artifacts/pilot-published.json", ROOT / "data/catalog.jadoo_all.json")
EXPANSION_SOURCES = (ROOT / "data/catalog.larva.json", ROOT / "data/catalog.ori.json")


def _allowed_episodes(package, is_published_package):
    if os.getenv("ALLOW_FULL_CATALOG_GROUNDING", "").lower() in {"1", "true", "yes"} or is_published_package:
        return {ep["id"] for ep in package.get("episodes", []) if isinstance(ep, dict) and ep.get("id")}
    extra = {ep.strip() for ep in os.getenv("APPROVED_CLOUD_EPISODES", "").split(",") if ep.strip()}
    return PILOT_EPISODES | extra


@lru_cache(maxsize=4)
def _read_documents(path, _version, full_grounding=False):
    with path.open(encoding="utf-8-sig") as stream:
        package = json.load(stream)
    if path in EXPANSION_SOURCES:
        documents = {}
        for episode in package.get("episodes", []):
            record = episode.get("record") or {}
            provenance = record.get("provenance") or {}
            synopsis = episode.get("synopsis")
            if (record.get("status") == "ready" and provenance.get("source_ids")
                    and provenance.get("verification") in {"source_verified", "human_verified"}
                    and isinstance(synopsis, str) and synopsis.strip()):
                documents[episode["id"]] = {
                    "id": episode["id"], "title": episode["title"], "item_type": "episode", "synopsis": synopsis,
                }
        return documents
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
    for path in (*PILOT_SOURCES, *EXPANSION_SOURCES):
        try:
            stat = path.stat()
            docs = _read_documents(path, (stat.st_mtime_ns, stat.st_size), full_grounding)
            sources.append(docs)
            if path == PILOT_SOURCES[0] or path in EXPANSION_SOURCES:
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
            if document.get("item_type") not in {"episode", "segment", "scene", "dialogue"}:
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


def _verified(row, sources):
    record = row.get("record") or {}
    if not isinstance(record, dict) or record.get("status") != "ready":
        return False
    provenance = record.get("provenance")
    if not isinstance(provenance, dict):
        return False
    refs = provenance.get("source_ids")
    return (provenance.get("verification") in ("source_verified", "human_verified")
            and isinstance(refs, list) and bool(refs)
            and all(isinstance(ref, str) and ref in sources for ref in refs))


def _public_video(episode, asset):
    if any(isinstance(entry, dict) and entry.get("namespace") in {"youtube_playback", "youtube_watch"}
           and isinstance(entry.get("value"), str) and re.fullmatch(r"[A-Za-z0-9_-]{11}", entry["value"])
           for entry in episode.get("external_ids", [])):
        return True
    return (
        asset.get("enabled", True) is True
        and asset.get("access_policy", "public") == "public"
        and asset.get("content_type") == "video"
        and asset.get("role") not in {"dub", "audio_description"}
        and (asset.get("record") or {}).get("status") == "ready"
        and any(part.get("episode_id") == episode["id"] and part.get("scope") == "full_episode"
                for part in asset.get("coverage", []) if isinstance(part, dict))
    )


def _snapshot_source(snapshot, result, quote):
    records = snapshot.catalog_records
    episode_id = result.get("episodeId")
    episode = records["episodes"].get(episode_id, {})
    visible = snapshot.get_item_by_id(episode_id)
    if not visible or not _verified(episode, records["sources"]):
        return None
    asset = records["media_assets"].get(visible.get("primary_media_asset_id"), {})
    if not _public_video(episode, asset):
        return None

    document_id = quote.get("documentId")
    if quote.get("itemType") == "episode":
        if document_id != episode_id:
            return None
        document, start = episode, None
    else:
        document = records["segments"].get(document_id, {})
        if (document.get("episode_id") != episode_id or not snapshot.get_item_by_id(document_id)
                or not _verified(document, records["sources"])):
            return None
        start = document.get("episode_start_ms")
    if start != result.get("startMs") or (start is not None and type(start) is not int):
        return None
    text, title = document.get("synopsis"), episode.get("title")
    if not isinstance(text, str) or not text.strip() or not isinstance(title, str) or not title.strip():
        return None
    return {"title": title, "startMs": start, "evidence": [text[:1200]]}


def evidence_for_snapshot_results(snapshot, results):
    full = os.getenv("ALLOW_FULL_CATALOG_GROUNDING", "").lower() in {"1", "true", "yes"}
    selected = {part.strip() for part in os.getenv("APPROVED_CLOUD_EPISODES", "").split(",") if part.strip()}
    if not (full or selected) or snapshot is None or not snapshot.is_ready:
        return None
    evidence = []
    for result in results[:3]:
        quote = next(iter(result.get("evidence") or []), {})
        if not isinstance(quote, dict):
            continue
        if (full or result.get("episodeId") in selected) and quote.get("itemType") in {"episode", "segment"}:
            source = _snapshot_source(snapshot, result, quote)
            if source:
                evidence.append(source)
        else:
            evidence.extend(evidence_for_results([result]))
    return evidence
