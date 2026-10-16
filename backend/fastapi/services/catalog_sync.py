"""
Catalog Synchronization & Flattening Engine for Dippie Cinema (CATALOG-01-F01).

Implements ingestion and multi-level flattening for payloads conforming to
dippie.catalog.v1 (series, seasons, episodes, segments, scenes, characters,
media assets, and text tracks).

Transforms hierarchical catalog trees into unified searchable items:
- Series items
- Episode items
- Segment items
- Scene items
"""

import os
import json
import logging
import hashlib
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Union

logger = logging.getLogger("moviercm.catalog_sync")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO)

DEFAULT_CATALOG_PATHS = [
    Path(__file__).resolve().parent.parent.parent.parent / "data" / "catalog" / "committed_catalog_snapshot.json",
    Path(__file__).resolve().parent.parent.parent.parent / "data" / "catalog" / "imported_catalog.json",
]

DEMO_CATALOG_PATH = Path(__file__).resolve().parent.parent.parent.parent / "docs" / "contracts" / "animation-catalog-v1" / "catalog.example.json"


class CatalogSyncError(Exception):
    """Raised when catalog parsing or synchronization fails."""
    pass


def extract_alias_strings(raw_aliases: Optional[List[Any]]) -> List[str]:
    """Extract plain text alias strings from alias list (handles dict or str items)."""
    if not raw_aliases or not isinstance(raw_aliases, list):
        return []
    res: List[str] = []
    for item in raw_aliases:
        if isinstance(item, str) and item.strip():
            res.append(item.strip())
        elif isinstance(item, dict):
            text = item.get("text")
            if text and isinstance(text, str) and text.strip():
                res.append(text.strip())
    return list(dict.fromkeys(res))


def extract_plot_fact_strings(raw_facts: Optional[List[Any]]) -> List[str]:
    """Extract plain text strings from plot_facts list (handles dict or str items)."""
    if not raw_facts or not isinstance(raw_facts, list):
        return []
    fact_texts: List[str] = []
    for item in raw_facts:
        if isinstance(item, str) and item.strip():
            fact_texts.append(item.strip())
        elif isinstance(item, dict):
            text = item.get("text") or item.get("fact")
            if text and isinstance(text, str) and text.strip():
                fact_texts.append(text.strip())
    return fact_texts


def extract_attributes_map(raw_attributes: Optional[List[Any]]) -> Dict[str, Any]:
    """
    Extract normalized scale_id -> value mapping from an attributes list.
    Handles attribute dictionaries with 'scale_id' and 'value'.
    """
    attr_map: Dict[str, Any] = {}
    if not raw_attributes or not isinstance(raw_attributes, list):
        return attr_map

    for attr in raw_attributes:
        if isinstance(attr, dict) and "scale_id" in attr:
            sid = attr["scale_id"]
            val = attr.get("value")
            if val is not None:
                try:
                    attr_map[sid] = float(val)
                except (ValueError, TypeError):
                    attr_map[sid] = val
            else:
                attr_map[sid] = None
    return attr_map


def parse_year_from_date(date_str: Optional[str]) -> Optional[int]:
    """Extract 4-digit year from ISO date strings (e.g. '2026-03-01')."""
    if not date_str or not isinstance(date_str, str):
        return None
    try:
        parts = date_str.split("-")
        if len(parts) >= 1 and len(parts[0]) == 4:
            return int(parts[0])
    except Exception:
        pass
    return None


class CatalogSyncManager:
    """
    Manages loading, flattening, and caching of dippie.catalog.v1 payloads.
    Provides indexed searchable representation for hybrid search and AI chat.
    """

    def __init__(self):
        self._raw_catalog: Optional[Dict[str, Any]] = None
        self._flattened_items: List[Dict[str, Any]] = []
        self._items_by_id: Dict[str, Dict[str, Any]] = {}
        self._item_counts: Dict[str, int] = {}
        self._content_hash: Optional[str] = None
        self._is_loaded: bool = False

    @property
    def is_loaded(self) -> bool:
        return self._is_loaded

    @property
    def content_hash(self) -> Optional[str]:
        return self._content_hash

    @property
    def item_counts(self) -> Dict[str, int]:
        return dict(self._item_counts)

    def get_flattened_catalog(self) -> List[Dict[str, Any]]:
        """Return all flattened searchable items (series, episodes, segments, scenes)."""
        return list(self._flattened_items)

    def get_item_by_id(self, item_id: str) -> Dict[str, Any]:
        return self._items_by_id.get(item_id, {})

    @staticmethod
    def compute_hash(payload: Dict[str, Any]) -> str:
        """Compute stable SHA-256 hash of catalog payload."""
        serialized = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def load_from_payload(
        self,
        payload: Dict[str, Any],
        include_draft: bool = False,
        include_private: bool = False,
    ) -> Dict[str, int]:
        """
        Parse and flatten a dippie.catalog.v1 payload into searchable units.
        Enforces record status and access_policy rules (C9).
        """
        if not isinstance(payload, dict):
            raise CatalogSyncError("Payload must be a dictionary.")

        schema_ver = payload.get("schema_version")
        if schema_ver != "dippie.catalog.v1":
            logger.warning(
                f"[CatalogSyncManager] Payload schema_version is '{schema_ver}', "
                f"expected 'dippie.catalog.v1'. Parsing may be partial."
            )

        # 1. Build lookup tables
        genre_map: Dict[str, List[str]] = {}
        for g in payload.get("genres", []):
            if isinstance(g, dict) and "id" in g:
                gid = g["id"]
                labels = [gid]
                for lbl in g.get("labels", []):
                    if isinstance(lbl, dict) and "text" in lbl:
                        labels.append(lbl["text"])
                for alias in extract_alias_strings(g.get("aliases")):
                    labels.append(alias)
                genre_map[gid] = list(dict.fromkeys(labels))

        char_map: Dict[str, Dict[str, Any]] = {}
        for c in payload.get("characters", []):
            if isinstance(c, dict) and "id" in c:
                cid = c["id"]
                c_name = c.get("name", cid)
                c_aliases = extract_alias_strings(c.get("aliases"))
                char_map[cid] = {
                    "name": c_name,
                    "aliases": c_aliases,
                    "searchable": [c_name] + c_aliases,
                    "traits": c.get("traits", []),
                }

        # Media assets mapping: map episode_id -> primary_media_asset_id
        ep_to_asset: Dict[str, str] = {}
        asset_policy_map: Dict[str, str] = {}
        for asset in payload.get("media_assets", []):
            if isinstance(asset, dict) and "id" in asset:
                aid = asset["id"]
                policy = asset.get("access_policy", "public")
                asset_policy_map[aid] = policy
                for cov in asset.get("coverage", []):
                    if isinstance(cov, dict):
                        cov_ep = cov.get("episode_id")
                        if cov_ep and cov_ep not in ep_to_asset:
                            ep_to_asset[cov_ep] = aid

        # Text tracks cues mapping: asset_id -> list of cues
        asset_cues: Dict[str, List[Dict[str, Any]]] = {}
        for track in payload.get("text_tracks", []):
            if isinstance(track, dict):
                mid = track.get("media_asset_id")
                if mid:
                    cues = track.get("cues", [])
                    if mid not in asset_cues:
                        asset_cues[mid] = []
                    asset_cues[mid].extend(cues)

        # 2. Build parent hierarchical references
        series_dict: Dict[str, Dict[str, Any]] = {}
        for s in payload.get("series", []):
            if isinstance(s, dict) and "id" in s:
                series_dict[s["id"]] = s

        episodes_dict: Dict[str, Dict[str, Any]] = {}
        for ep in payload.get("episodes", []):
            if isinstance(ep, dict) and "id" in ep:
                episodes_dict[ep["id"]] = ep

        # 3. Flatten each entity level into searchable items
        flattened: List[Dict[str, Any]] = []
        eligible_series_ids: Set[str] = set()

        # --- A. Series Items ---
        series_count = 0
        for s in payload.get("series", []):
            if not isinstance(s, dict) or "id" not in s:
                continue
            rec = s.get("record", {})
            if not include_draft and rec.get("status") in ("draft", "archived"):
                continue

            sid = s["id"]
            eligible_series_ids.add(sid)
            title = s.get("title", "")
            aliases = extract_alias_strings(s.get("aliases"))
            synopsis = s.get("synopsis", "")
            g_ids = s.get("genre_ids", [])
            resolved_genres = []
            for gid in g_ids:
                resolved_genres.extend(genre_map.get(gid, [gid]))
            resolved_genres = list(dict.fromkeys(resolved_genres))

            keywords = s.get("keywords", [])
            themes = s.get("themes", [])
            char_ids = s.get("character_ids", [])
            char_names = []
            for cid in char_ids:
                if cid in char_map:
                    char_names.extend(char_map[cid]["searchable"])
                else:
                    char_names.append(cid)
            char_names = list(dict.fromkeys(char_names))

            rel_year = s.get("release_year_start") or parse_year_from_date(s.get("release_date"))
            attr_map = extract_attributes_map(s.get("attributes"))

            series_item: Dict[str, Any] = {
                "id": sid,
                "title": title,
                "aliases": aliases,
                "synopsis": synopsis,
                "genres": resolved_genres,
                "keywords": keywords,
                "themes": themes,
                "characters": char_names,
                "release_year": rel_year,
                "item_type": "series",
                # Compatible fields
                "year": rel_year,
                "runtime": "Series",
                "description": synopsis or f"Animation series: {title}",
                "comparative_attributes": attr_map,
                "attributes": s.get("attributes", []),
            }
            flattened.append(series_item)
            series_count += 1

        # --- B. Episode Items ---
        episode_count = 0
        eligible_episode_ids: Set[str] = set()
        for ep in payload.get("episodes", []):
            if not isinstance(ep, dict) or "id" not in ep:
                continue
            parent_series_id = ep.get("series_id", "")
            if not include_draft and parent_series_id and parent_series_id not in eligible_series_ids:
                continue
            rec = ep.get("record", {})
            if not include_draft and rec.get("status") in ("draft", "archived"):
                continue

            epid = ep["id"]
            eligible_episode_ids.add(epid)
            parent_series = series_dict.get(parent_series_id, {})
            season_id = ep.get("season_id", "")
            title = ep.get("title", "")
            aliases = extract_alias_strings(ep.get("aliases"))
            ep_num = ep.get("number")
            air_date = ep.get("release_date")
            duration_ms = ep.get("duration_ms")
            synopsis = ep.get("synopsis", "")
            plot_facts = extract_plot_fact_strings(ep.get("plot_facts"))

            # Genres
            ep_gids = ep.get("genre_ids") or parent_series.get("genre_ids", [])
            resolved_genres = []
            for gid in ep_gids:
                resolved_genres.extend(genre_map.get(gid, [gid]))
            resolved_genres = list(dict.fromkeys(resolved_genres))

            # Characters
            char_ids = ep.get("character_ids", [])
            char_names = []
            for cid in char_ids:
                if cid in char_map:
                    char_names.extend(char_map[cid]["searchable"])
                else:
                    char_names.append(cid)
            char_names = list(dict.fromkeys(char_names))

            keywords = ep.get("keywords", [])
            themes = ep.get("themes", [])
            primary_asset_id = ep_to_asset.get(epid) or ep.get("primary_media_asset_id")

            year = parse_year_from_date(air_date) or parent_series.get("release_year_start")
            attr_map = extract_attributes_map(ep.get("attributes"))

            dur_min = (duration_ms // 60000) if (duration_ms and duration_ms > 0) else None
            runtime_str = f"{dur_min}m" if dur_min else "Episode"

            episode_item: Dict[str, Any] = {
                "id": epid,
                "series_id": parent_series_id,
                "series_title": parent_series.get("title", ""),
                "season_id": season_id,
                "title": title,
                "aliases": aliases,
                "episode_number": ep_num,
                "air_date": air_date,
                "duration_ms": duration_ms,
                "synopsis": synopsis,
                "plot_facts": plot_facts,
                "characters": char_names,
                "keywords": keywords,
                "themes": themes,
                "primary_media_asset_id": primary_asset_id,
                "genres": resolved_genres,
                "release_year": year,
                "item_type": "episode",
                # Compatible fields
                "year": year,
                "runtime": runtime_str,
                "description": synopsis or f"Episode {ep_num}: {title}",
                "comparative_attributes": attr_map,
                "attributes": ep.get("attributes", []),
            }
            flattened.append(episode_item)
            episode_count += 1

        # --- C. Segment Items ---
        segment_count = 0
        eligible_segment_ids: Set[str] = set()
        for seg in payload.get("segments", []):
            if not isinstance(seg, dict) or "id" not in seg:
                continue
            parent_ep_id = seg.get("episode_id", "")
            if not include_draft and parent_ep_id and parent_ep_id not in eligible_episode_ids:
                continue
            rec = seg.get("record", {})
            if not include_draft and rec.get("status") in ("draft", "archived"):
                continue

            seg_id = seg["id"]
            eligible_segment_ids.add(seg_id)
            ep_id = seg.get("episode_id", "")
            parent_ep = episodes_dict.get(ep_id, {})
            parent_series_id = parent_ep.get("series_id", "")
            parent_series = series_dict.get(parent_series_id, {})

            title = seg.get("title", "")
            aliases = extract_alias_strings(seg.get("aliases"))
            synopsis = seg.get("synopsis", "")
            char_ids = seg.get("character_ids", [])
            char_names = []
            for cid in char_ids:
                if cid in char_map:
                    char_names.extend(char_map[cid]["searchable"])
                else:
                    char_names.append(cid)
            char_names = list(dict.fromkeys(char_names))

            plot_facts = extract_plot_fact_strings(seg.get("plot_facts"))
            keywords = seg.get("keywords", [])
            themes = seg.get("themes", [])

            start_ms = seg.get("episode_start_ms")
            if start_ms is None:
                start_ms = seg.get("start_ms")
            end_ms = seg.get("episode_end_ms")
            if end_ms is None:
                end_ms = seg.get("end_ms")

            # Inherit genres and year from parent episode/series
            ep_gids = parent_ep.get("genre_ids") or parent_series.get("genre_ids", [])
            resolved_genres = []
            for gid in ep_gids:
                resolved_genres.extend(genre_map.get(gid, [gid]))
            resolved_genres = list(dict.fromkeys(resolved_genres))

            year = parse_year_from_date(parent_ep.get("release_date")) or parent_series.get("release_year_start")
            attr_map = extract_attributes_map(seg.get("attributes"))

            if start_ms is not None and end_ms is not None:
                dur_sec = max(0, (end_ms - start_ms) // 1000)
                runtime_str = f"{dur_sec}s" if dur_sec > 0 else "Segment"
            else:
                dur_sec = None
                runtime_str = "Segment"

            segment_item: Dict[str, Any] = {
                "id": seg_id,
                "episode_id": ep_id,
                "episode_title": parent_ep.get("title", ""),
                "series_id": parent_series_id,
                "series_title": parent_series.get("title", ""),
                "title": title,
                "aliases": aliases,
                "synopsis": synopsis,
                "characters": char_names,
                "plot_facts": plot_facts,
                "keywords": keywords,
                "themes": themes,
                "start_ms": start_ms,
                "end_ms": end_ms,
                "genres": resolved_genres,
                "release_year": year,
                "item_type": "segment",
                # Compatible fields
                "year": year,
                "runtime": runtime_str,
                "description": synopsis or f"Segment: {title}",
                "comparative_attributes": attr_map,
                "attributes": seg.get("attributes", []),
            }
            flattened.append(segment_item)
            segment_count += 1

        # --- D. Scene Items ---
        scene_count = 0
        for sc in payload.get("scenes", []):
            if not isinstance(sc, dict) or "id" not in sc:
                continue
            ep_id = sc.get("episode_id", "")
            if not include_draft and ep_id and ep_id not in eligible_episode_ids:
                continue
            seg_id = sc.get("segment_id")
            if not include_draft and seg_id and seg_id not in eligible_segment_ids:
                continue
            rec = sc.get("record", {})
            if not include_draft and rec.get("status") in ("draft", "archived"):
                continue

            sc_id = sc["id"]
            media_asset_id = sc.get("media_asset_id", "")

            # Access policy check
            if not include_private and asset_policy_map.get(media_asset_id) in ("private", "authenticated"):
                continue

            start_ms = sc.get("start_ms")
            end_ms = sc.get("end_ms")

            visual_summary = sc.get("visual_description") or sc.get("summary") or sc.get("visual_summary", "")

            # Extract dialogue summary from cues falling into [start_ms, end_ms]
            cues = asset_cues.get(media_asset_id, [])
            dialogue_lines = []
            if start_ms is not None and end_ms is not None:
                for cue in cues:
                    c_start = cue.get("start_ms")
                    c_end = cue.get("end_ms")
                    if c_start is not None and c_end is not None:
                        if (c_start >= start_ms and c_start <= end_ms) or (c_end >= start_ms and c_end <= end_ms):
                            line = cue.get("text")
                            if line and isinstance(line, str) and line.strip():
                                dialogue_lines.append(line.strip())
            dialogue_summary = sc.get("dialogue_summary") or (" ".join(dialogue_lines) if dialogue_lines else "")

            char_ids = sc.get("character_ids", [])
            char_names = []
            for cid in char_ids:
                if cid in char_map:
                    char_names.extend(char_map[cid]["searchable"])
                else:
                    char_names.append(cid)
            char_names = list(dict.fromkeys(char_names))

            keywords = sc.get("keywords", [])
            themes = sc.get("themes", [])
            sound_events = sc.get("sound_events", [])
            title = sc.get("title") or f"Scene {sc_id}"

            parent_ep = episodes_dict.get(ep_id, {})
            parent_series_id = parent_ep.get("series_id", "")
            parent_series = series_dict.get(parent_series_id, {})

            ep_gids = parent_ep.get("genre_ids") or parent_series.get("genre_ids", [])
            resolved_genres = []
            for gid in ep_gids:
                resolved_genres.extend(genre_map.get(gid, [gid]))
            resolved_genres = list(dict.fromkeys(resolved_genres))

            year = parse_year_from_date(parent_ep.get("release_date")) or parent_series.get("release_year_start")
            attr_map = extract_attributes_map(sc.get("attributes"))

            if start_ms is not None and end_ms is not None:
                dur_sec = max(0, (end_ms - start_ms) // 1000)
                runtime_str = f"{dur_sec}s" if dur_sec > 0 else "Scene"
            else:
                dur_sec = None
                runtime_str = "Scene"

            desc = visual_summary or sc.get("summary", "")
            if dialogue_summary:
                desc = f"{desc} | Thoại: \"{dialogue_summary}\"".strip()

            scene_item: Dict[str, Any] = {
                "id": sc_id,
                "episode_id": ep_id,
                "episode_title": parent_ep.get("title", ""),
                "segment_id": sc.get("segment_id"),
                "series_id": parent_series_id,
                "series_title": parent_series.get("title", ""),
                "media_asset_id": media_asset_id,
                "start_ms": start_ms,
                "end_ms": end_ms,
                "title": title,
                "visual_summary": visual_summary,
                "dialogue_summary": dialogue_summary,
                "characters": char_names,
                "keywords": keywords,
                "themes": themes,
                "sound_events": sound_events,
                "genres": resolved_genres,
                "release_year": year,
                "item_type": "scene",
                # Compatible fields
                "year": year,
                "runtime": runtime_str,
                "description": desc or f"Scene: {title}",
                "comparative_attributes": attr_map,
                "attributes": sc.get("attributes", []),
            }
            flattened.append(scene_item)
            scene_count += 1

        # Store internal state
        self._raw_catalog = payload
        self._flattened_items = flattened
        self._items_by_id = {item["id"]: item for item in flattened}
        self._item_counts = {
            "series": series_count,
            "episodes": episode_count,
            "segments": segment_count,
            "scenes": scene_count,
            "total": len(flattened),
        }
        self._content_hash = self.compute_hash(payload)
        self._is_loaded = True

        logger.info(
            f"[CatalogSyncManager] Parsed catalog payload: {series_count} series, "
            f"{episode_count} episodes, {segment_count} segments, {scene_count} scenes "
            f"({len(flattened)} total searchable items)."
        )
        return dict(self._item_counts)

    def load_from_file(self, file_path: Union[str, Path]) -> Dict[str, int]:
        """Load and parse catalog from a file path."""
        p = Path(file_path).resolve()
        if not p.exists():
            raise FileNotFoundError(f"Catalog file not found: {p}")
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        return self.load_from_payload(data)

    def load_default_catalog(self) -> bool:
        """Attempt to load from default committed catalog paths.
        Demo mode is strictly opt-in via CATALOG_DEMO_MODE=true env var."""
        for path in DEFAULT_CATALOG_PATHS:
            if path.exists():
                try:
                    logger.info(f"[CatalogSyncManager] Loading committed catalog snapshot from: {path}")
                    self.load_from_file(path)
                    return True
                except Exception as e:
                    logger.warning(f"[CatalogSyncManager] Failed loading snapshot {path}: {e}")

        # Only load demo fixture if explicit demo mode is set
        if os.environ.get("CATALOG_DEMO_MODE", "").lower() in ("true", "1", "yes"):
            if DEMO_CATALOG_PATH.exists():
                try:
                    logger.info(f"[CatalogSyncManager] CATALOG_DEMO_MODE active: Loading demo fixture from {DEMO_CATALOG_PATH}")
                    self.load_from_file(DEMO_CATALOG_PATH)
                    return True
                except Exception as e:
                    logger.warning(f"[CatalogSyncManager] Failed loading demo fixture: {e}")
        else:
            logger.info("[CatalogSyncManager] No committed catalog snapshot found and demo mode is disabled. Index starts empty.")
        return False


# Global singleton instance
catalog_sync_manager = CatalogSyncManager()
