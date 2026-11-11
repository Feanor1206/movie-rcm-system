import json
from pathlib import Path

import numpy as np


def compute_phash(image_bytes: bytes) -> int:
    import cv2

    buffer = np.frombuffer(image_bytes, dtype=np.uint8)
    image = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("Could not decode image bytes")
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    small = cv2.resize(gray, (32, 32), interpolation=cv2.INTER_AREA).astype(np.float32)
    low = cv2.dct(small)[:8, :8].reshape(-1)[1:]
    median = float(np.median(low))
    value = 0
    for coefficient in low:
        value = (value << 1) | int(coefficient > median)
    return value


class FrameSearchIndex:
    def __init__(self, entries: list[dict], max_distance: int = 20):
        self.entries = entries
        self.max_distance = max_distance

    @classmethod
    def from_path(cls, path: str | Path, *, max_distance: int = 20):
        target = Path(path).resolve(strict=True)
        manifests = [target] if target.is_file() else sorted(target.glob("*/keyframes.json"))
        entries = []
        for manifest in manifests:
            data = json.loads(manifest.read_text(encoding="utf-8"))
            rows = data.get("frames") or data.get("samples") or []
            episode_id = data.get("episode_id")
            media_asset_id = data.get("media_asset_id")
            for row in rows:
                phash_hex = row.get("phash")
                source_ms = row.get("source_ms")
                ep_id = row.get("episode_id") or episode_id
                if not isinstance(phash_hex, str) or not isinstance(source_ms, int) or not ep_id:
                    continue
                entries.append({
                    "episode_id": ep_id,
                    "media_asset_id": row.get("media_asset_id") or media_asset_id,
                    "source_ms": source_ms,
                    "phash": int(phash_hex, 16),
                    "path": row.get("path"),
                })
        if not entries:
            raise ValueError("No valid keyframe hashes found in frame index path")
        return cls(entries, max_distance=max_distance)

    def search(self, image_bytes: bytes, limit: int = 5) -> list[dict]:
        query_hash = compute_phash(image_bytes)
        scored = []
        for entry in self.entries:
            distance = (query_hash ^ entry["phash"]).bit_count()
            if distance <= self.max_distance:
                similarity = round(1.0 - (distance / 64.0), 4)
                scored.append((distance, -similarity, entry["source_ms"], entry, similarity))
        scored.sort(key=lambda item: (item[0], item[2]))
        results, seen = [], set()
        for distance, _, source_ms, entry, similarity in scored:
            episode_id = entry["episode_id"]
            if episode_id in seen:
                continue
            seen.add(episode_id)
            results.append({
                "id": episode_id,
                "episodeId": episode_id,
                "startMs": source_ms,
                "start_ms": source_ms,
                "score": similarity,
                "matchPercentage": round(similarity * 100),
                "hammingDistance": distance,
                "mediaAssetId": entry.get("media_asset_id"),
                "evidence": [{
                    "documentId": f"frame:{episode_id}:{source_ms}",
                    "startMs": source_ms,
                    "sourceStartMs": source_ms,
                    "mediaAssetId": entry.get("media_asset_id"),
                    "itemType": "frame",
                }],
            })
            if len(results) >= max(1, min(50, limit)):
                break
        return results
