from collections import Counter, defaultdict
from contextlib import nullcontext
import copy
from dataclasses import dataclass, field
import functools
import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile
from typing import Any
import unicodedata

import numpy as np


NEGATION_CUE = re.compile(
    r"\b(?:(?:(?:chứ|chu)\s+)?(?:không|khong)\s+(?:phải|phai|xem)|(?:bỏ|bo)\s+qua|trừ|"
    r"tru(?=\s+(?:s\d+e\d+\b|(?:mùa|mua|season|phần|phan|tập|tap|ep|episode)\s*#?\s*\d)))\b"
)
_TOKEN_RE = re.compile(r"\b\w+\b")
_RRF_SCORES = tuple(1.0 / (60 + rank) for rank in range(1, 65))
_EMBEDDING_FILE_CACHE: dict[tuple[str, int], np.ndarray] = {}


@functools.lru_cache(maxsize=8192)
def normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", str(text).casefold().replace("đ", "d"))
    return "".join(char for char in decomposed if unicodedata.category(char) != "Mn")


@functools.lru_cache(maxsize=4096)
def _cached_tokenize(text: str) -> tuple[str, ...]:
    return tuple(_TOKEN_RE.findall(unicodedata.normalize("NFC", str(text).casefold())))


def tokenize(text: str) -> list[str]:
    return list(_cached_tokenize(text))


@functools.lru_cache(maxsize=4096)
def _cached_bigrams(tokens: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(f"{left}_{right}" for left, right in zip(tokens, tokens[1:]))


def _bigrams(tokens: list[str] | tuple[str, ...]) -> list[str]:
    return list(_cached_bigrams(tuple(tokens)))


def parse_season_episode_intent(query: str) -> tuple[int | None, int | None]:
    text = normalize(query)
    combined = re.search(r"\bs0*(\d+)e0*(\d+)\b", text)
    if combined:
        return int(combined[1]), int(combined[2])
    season = re.search(r"\b(?:mua|season|phan)\s*#?\s*0*(\d+)\b", text)
    episode = re.search(r"\b(?:tap|ep|episode)\s*#?\s*0*(\d+)\b", text)
    return int(season[1]) if season else None, int(episode[1]) if episode else None


HIGH_WEIGHT_FIELDS = ("title", "series_title", "episode_title", "aliases", "characters")
MEDIUM_WEIGHT_FIELDS = ("keywords", "themes", "plot_facts", "sound_events")


def document_text(item: dict) -> str:
    values = []
    for field in ("title", "series_title", "episode_title", "description", "synopsis",
                  "visual_summary", "dialogue_summary", "aliases", "characters", "plot_facts",
                  "keywords", "themes", "sound_events"):
        value = item.get(field)
        if isinstance(value, str) and value:
            values.append(value)
        elif isinstance(value, list):
            values.extend(text for text in value if isinstance(text, str))
    return "\n".join(dict.fromkeys(values))


def _field_values(item: dict, fields: tuple[str, ...]) -> str:
    values = []
    for field in fields:
        value = item.get(field)
        if isinstance(value, str) and value:
            values.append(value)
        elif isinstance(value, list):
            values.extend(text for text in value if isinstance(text, str))
    return " ".join(values)


def _coverage_mappings(episodes, payload):
    mappings = defaultdict(list)
    for asset in payload.get("media_assets", []):
        if (not isinstance(asset, dict) or asset.get("access_policy", "public") != "public"
                or asset.get("enabled", True) is not True
                or (asset.get("record") or {}).get("status") in ("draft", "archived")):
            continue
        coverage = asset.get("coverage", [])
        if not coverage:
            coverage = [{"episode_id": episode["id"], "source_in_ms": 0,
                         "source_out_ms": asset.get("duration_ms"), "episode_in_ms": 0}
                        for episode in episodes.values() if episode.get("primary_media_asset_id") == asset.get("id")]
        for entry in coverage:
            if entry.get("episode_id") not in episodes:
                continue
            source_in = entry.get("source_in_ms")
            source_out = entry.get("source_out_ms") or asset.get("duration_ms")
            episode_in = entry.get("episode_in_ms")
            if not isinstance(source_in, int) or isinstance(source_in, bool) or source_in < 0:
                continue
            if source_out is not None and (not isinstance(source_out, int) or isinstance(source_out, bool) or source_out <= source_in):
                continue
            if episode_in is not None and (not isinstance(episode_in, int) or isinstance(episode_in, bool) or episode_in < 0):
                continue
            mappings[asset["id"]].append({"episode_id": entry["episode_id"], "source_in_ms": source_in,
                                          "source_out_ms": source_out, "episode_in_ms": episode_in})
    return mappings


def _episode_position(position, mapping):
    return (position - mapping["source_in_ms"] + mapping["episode_in_ms"]
            if mapping["episode_in_ms"] is not None else None)


def _documents(catalog: list[dict], payload: dict | None) -> list[dict]:
    documents = copy.deepcopy(catalog)
    episodes = {item["id"]: item for item in documents if item.get("item_type") == "episode"}
    for item in documents:
        parent = episodes.get(item.get("episode_id"), {})
        for field in ("episode_number", "season_number", "series_id", "series_title", "year", "genres"):
            if item.get(field) is None or field not in item:
                item[field] = copy.deepcopy(parent.get(field))
    if not payload:
        return documents
    mappings = _coverage_mappings(episodes, payload)
    for item in documents:
        if item.get("item_type") != "scene" or not isinstance(item.get("start_ms"), (int, float)):
            continue
        matches = [entry for entry in mappings.get(item.get("media_asset_id"), [])
                   if entry["episode_id"] == item.get("episode_id")
                   and item["start_ms"] >= entry["source_in_ms"]
                   and (entry["source_out_ms"] is None or item["start_ms"] < entry["source_out_ms"])]
        if len(matches) == 1:
            item["_episode_start_ms"] = _episode_position(item["start_ms"], matches[0])
            if isinstance(item.get("end_ms"), (int, float)):
                item["_episode_end_ms"] = _episode_position(item["end_ms"], matches[0])
        elif item.get("media_asset_id"):
            item["_episode_start_ms"] = item["_episode_end_ms"] = None
    for track in payload.get("text_tracks", []):
        if ((track.get("record") or {}).get("status") in ("draft", "archived")
                or track.get("enabled", True) is not True):
            continue
        for mapping in mappings.get(track.get("media_asset_id"), []):
            episode = episodes[mapping["episode_id"]]
            cues = [cue for cue in track.get("cues", [])
                    if isinstance(cue.get("text"), str) and cue["text"].strip()
                    and isinstance(cue.get("start_ms"), int) and not isinstance(cue["start_ms"], bool)
                    and isinstance(cue.get("end_ms"), int) and not isinstance(cue["end_ms"], bool)
                    and 0 <= cue["start_ms"] < cue["end_ms"]
                    and cue["end_ms"] > mapping["source_in_ms"]
                    and (mapping["source_out_ms"] is None or cue["start_ms"] < mapping["source_out_ms"])]
            cues.sort(key=lambda cue: (cue["start_ms"], cue["end_ms"]))
            if not cues:
                continue
            first = int(min(cue["start_ms"] for cue in cues) // 22_500 * 22_500)
            last = int(max(cue["end_ms"] for cue in cues))
            seen = set()
            for start in range(first, last, 22_500):
                selected = [cue for cue in cues if cue["start_ms"] < start + 45_000 and cue["end_ms"] > start]
                if not selected:
                    continue
                text = " ".join(cue["text"].strip() for cue in selected)
                selection = tuple((cue["start_ms"], cue["end_ms"], cue["text"]) for cue in selected)
                if selection in seen:
                    continue
                seen.add(selection)
                source_start = max(min(cue["start_ms"] for cue in selected), mapping["source_in_ms"])
                source_end = max(cue["end_ms"] for cue in selected)
                if mapping["source_out_ms"] is not None:
                    source_end = min(source_end, mapping["source_out_ms"])
                window = copy.deepcopy(episode)
                window.update(id=f"dialogue:{track.get('id', track.get('media_asset_id'))}:{episode['id']}:{start}",
                              episode_id=episode["id"], item_type="dialogue", start_ms=source_start,
                              end_ms=source_end, description=text, dialogue_summary=text,
                              media_asset_id=track["media_asset_id"],
                              _episode_start_ms=_episode_position(source_start, mapping),
                              _episode_end_ms=_episode_position(source_end, mapping))
                documents.append(window)
    return documents


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _atomic_array(path: Path, values: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
            np.save(handle, values, allow_pickle=False)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _normalize_vectors(values: Any, count: int, dimension: int | None = None) -> np.ndarray:
    array = np.asarray(values, dtype=np.float32)
    if array.ndim != 2 or array.shape[0] != count or array.shape[1] < 1:
        raise ValueError("Embedding matrix shape does not match document count")
    if dimension is not None and array.shape[1] != dimension:
        raise ValueError("Embedding dimension does not match this model revision")
    if not np.isfinite(array).all():
        raise ValueError("Embedding vectors must be finite")
    norms = np.linalg.norm(array, axis=1, keepdims=True)
    if (norms == 0).any():
        raise ValueError("Embedding vectors must have nonzero norm")
    return array / norms


@dataclass(frozen=True)
class TextIndex:
    _documents: tuple
    _texts: tuple
    _postings: dict
    _lengths: np.ndarray
    _average_length: float
    embeddings: np.ndarray | None
    encoder: Any
    model_id: str
    missing_embeddings: int
    matrix_path: Path | None
    _doc_genres: tuple = ()
    _idf: dict = field(default_factory=dict)
    _doc_len_penalty: np.ndarray | None = None

    @property
    def documents(self) -> list[dict]:
        return [
            dict(item, genres=list(item["genres"])) if "genres" in item and isinstance(item["genres"], list) else dict(item)
            for item in self._documents
        ]

    @property
    def dense_ready(self) -> bool:
        return self.embeddings is not None and self.encoder is not None

    @property
    def is_ready(self) -> bool:
        return True

    @classmethod
    def build(cls, catalog: list[dict], *, cache_dir: Path, encoder=None, model_id="lexical",
              encode_missing=False, content_hash="", payload=None):
        documents = _documents(catalog, payload)
        texts = tuple(document_text(item) for item in documents)
        vectors = {}
        missing = []
        dimension = None
        directory = Path(cache_dir) / _hash(model_id)
        if model_id != "lexical":
            for text in dict.fromkeys(texts):
                key = _hash(text)
                path = directory / "documents" / f"{key}.npy"
                if not path.exists():
                    missing.append((text, path))
                    continue
                cache_key = (str(path), path.stat().st_mtime_ns)
                cached_vec = _EMBEDDING_FILE_CACHE.get(cache_key)
                if cached_vec is not None:
                    dimension = cached_vec.shape[0]
                    vectors[text] = cached_vec
                    continue
                vector = np.load(path, allow_pickle=False)
                if vector.ndim != 1:
                    raise ValueError("Cached document embedding must be one-dimensional")
                if not np.isclose(np.linalg.norm(vector.astype(np.float32)), 1.0, atol=0.001, rtol=0.001):
                    raise ValueError("Cached document embedding must already be normalized")
                matrix = _normalize_vectors(vector.reshape(1, -1), 1, dimension)
                dimension = matrix.shape[1]
                vectors[text] = matrix[0]
                _EMBEDDING_FILE_CACHE[cache_key] = matrix[0]
            if encode_missing and missing:
                if encoder is None:
                    raise ValueError("An encoder is required to prepare missing embeddings")
                for start in range(0, len(missing), 64):
                    batch = missing[start:start + 64]
                    matrix = _normalize_vectors(encoder.encode_documents([item[0] for item in batch]), len(batch), dimension)
                    dimension = matrix.shape[1]
                    for (text, path), vector in zip(batch, matrix):
                        _atomic_array(path, vector.astype(np.float16))
                        vectors[text] = vector
        missing_count = sum(text not in vectors for text in texts) if model_id != "lexical" else 0
        embeddings, matrix_path = None, None
        if texts and model_id != "lexical" and not missing_count:
            matrix = np.asarray([vectors[text] for text in texts], dtype=np.float16)
            embeddings = np.frombuffer(matrix.tobytes(), dtype=np.float16).reshape(matrix.shape)
            snapshot_key = _hash((content_hash or "") + "\n" + "\n".join(_hash(text) for text in texts))
            matrix_path = directory / "snapshots" / f"{snapshot_key}.npy"
            if not matrix_path.exists():
                _atomic_array(matrix_path, embeddings)
        postings = defaultdict(list)
        lengths = np.zeros(len(texts), dtype=np.float32)
        doc_genres = []
        for index, (item, text) in enumerate(zip(documents, texts)):
            doc_genres.append({normalize(g) for g in (item.get("genres") or [])})
            tokens = _cached_tokenize(text)
            lengths[index] = len(tokens)
            counts = Counter(tokens)
            for token in _cached_tokenize(_field_values(item, HIGH_WEIGHT_FIELDS)):
                counts[token] += 2
            for token in _cached_tokenize(_field_values(item, MEDIUM_WEIGHT_FIELDS)):
                counts[token] += 1
            for bigram in _cached_bigrams(tokens):
                counts[bigram] += 2
            for word, count in tuple(counts.items()):
                folded = "_".join(normalize(part) for part in word.split("_")) if "_" in word else normalize(word)
                if folded != word:
                    counts[folded] += count
            for word, count in counts.items():
                postings[word].append((index, count))
        lengths.flags.writeable = False

        num_texts = len(texts)
        idf = {
            term: math.log(1 + (num_texts - len(posting) + 0.5) / (len(posting) + 0.5))
            for term, posting in postings.items()
        }
        avg_len = float(lengths.mean()) if len(lengths) else 1.0
        doc_len_penalty = (1.5 * (0.25 + 0.75 * lengths / (avg_len or 1.0))).astype(np.float32)

        return cls(tuple(documents), texts, dict(postings), lengths,
                   float(lengths.mean()) if len(lengths) else 0, embeddings, encoder,
                   model_id, missing_count, matrix_path,
                   tuple(doc_genres), idf, doc_len_penalty)

    def _allowed(self, scopes: list[str], constraints: dict) -> tuple[list[int], bool]:
        season, episode = parse_season_episode_intent(scopes[0])
        negative = parse_season_episode_intent(scopes[1]) if len(scopes) > 1 else (None, None)
        season = constraints.get("season_number", season)
        episode = constraints.get("episode_number", episode)
        include = {normalize(genre) for genre in constraints.get("include_genres", [])}
        exclude = {normalize(genre) for genre in constraints.get("exclude_genres", [])}
        allowed = []
        for index, item in enumerate(self._documents):
            if season is not None and item.get("season_number") != season:
                continue
            if episode is not None and item.get("episode_number") != episode:
                continue
            if negative[1] is not None and item.get("episode_number") == negative[1] and (negative[0] is None or item.get("season_number") == negative[0]):
                continue
            if negative[0] is not None and negative[1] is None and item.get("season_number") == negative[0]:
                continue
            genres = self._doc_genres[index] if self._doc_genres and index < len(self._doc_genres) else {normalize(genre) for genre in item.get("genres") or []}
            if include and not genres.intersection(include) or genres.intersection(exclude):
                continue
            year = item.get("year") or item.get("release_year")
            if constraints.get("year_min") is not None and (year is None or year < constraints["year_min"]):
                continue
            if constraints.get("year_max") is not None and (year is None or year > constraints["year_max"]):
                continue
            allowed.append(index)
        return allowed, season is not None or episode is not None

    def search(self, query: str, limit=8, constraints=None, *, reranker=None, gpu_gate=None, calibration=None) -> list[dict]:
        if calibration is not None and getattr(calibration, "score_type", "reranker") != ("reranker" if reranker is not None else "rrf"):
            raise ValueError("Calibration score stage does not match the active ranking model")
        constraints = constraints or {}
        scopes = NEGATION_CUE.split(unicodedata.normalize("NFC", query.casefold()), maxsplit=1)
        allowed, explicit_number = self._allowed(scopes, constraints)
        if not allowed or not query.strip():
            return []
        scores = np.zeros(len(self._texts), dtype=np.float32)
        query_tokens = _cached_tokenize(scopes[0])
        for term in set(query_tokens + _cached_bigrams(query_tokens)):
            posting = self._postings.get(term, [])
            if not posting:
                continue
            weight = 1.35 if "_" in term else 1.0
            term_factor = weight * self._idf.get(term, math.log(1 + (len(self._texts) - len(posting) + 0.5) / (len(posting) + 0.5))) * 2.5
            for index, count in posting:
                denominator = count + (self._doc_len_penalty[index] if self._doc_len_penalty is not None else (1.5 * (0.25 + 0.75 * self._lengths[index] / (self._average_length or 1))))
                scores[index] += term_factor * count / denominator
        lexical = sorted((index for index in allowed if scores[index] > 0), key=lambda index: (-scores[index], index))[:30]
        rankings = [lexical]
        if self.dense_ready:
            query_vector = _normalize_vectors(self.encoder.encode_queries([query]), 1, self.embeddings.shape[1])[0]
            dense_scores = self.embeddings @ query_vector
            rankings.append(sorted((index for index in allowed if dense_scores[index] > 0), key=lambda index: (-dense_scores[index], index))[:30])
        if not any(rankings) and explicit_number:
            rankings = [allowed[:30]]
        fused = defaultdict(float)
        for ranking in rankings:
            for rank, index in enumerate(ranking):
                fused[index] += _RRF_SCORES[rank] if rank < len(_RRF_SCORES) else (1.0 / (61 + rank))
        candidates = sorted(fused, key=lambda index: (-fused[index], index))[:30]
        raw_scores = dict(fused)
        if reranker is not None and candidates:
            with gpu_gate() if gpu_gate is not None else nullcontext():
                ranked_scores = np.asarray(reranker(query, [self._texts[index] for index in candidates]), dtype=np.float32)
            if ranked_scores.shape != (len(candidates),) or not np.isfinite(ranked_scores).all():
                raise ValueError("Reranker must return a finite score for each candidate")
            raw_scores = dict(zip(candidates, ranked_scores.tolist()))
            candidates.sort(key=lambda index: (-raw_scores[index], index))
        by_id = {item["id"]: item for item in self._documents}
        results, used = [], set()
        for index in candidates:
            source = self._documents[index]
            episode_id = source.get("episode_id") or (source["id"] if source.get("item_type") == "episode" else None)
            result_id = episode_id or source["id"]
            if result_id in used:
                continue
            probability = calibration(raw_scores[index]) if calibration is not None else None
            if probability is not None and not 0 <= probability <= 1:
                raise ValueError("Calibrated score must be between zero and one")
            threshold = getattr(calibration, "threshold", 0) if calibration is not None else 0
            if probability is not None and probability < threshold:
                continue
            base_doc = by_id.get(result_id, source)
            result = dict(base_doc)
            if "genres" in result and isinstance(result["genres"], list):
                result["genres"] = list(result["genres"])
            result["year"] = result.get("year") or result.get("release_year") or 0
            evidence_text = source.get("dialogue_summary") or source.get("visual_summary") or source.get("description") or source.get("synopsis") or source.get("title", "")
            position = source.get("_episode_start_ms", source.get("start_ms"))
            result.update(episodeId=episode_id, startMs=position, score=float(raw_scores[index]),
                          start_ms=source.get("start_ms"), end_ms=source.get("end_ms"),
                          calibratedScore=probability, matchPercentage=round(probability * 100) if probability is not None else None,
                          evidence=[{"documentId": source["id"], "text": evidence_text[:1200],
                                     "startMs": position, "endMs": source.get("_episode_end_ms", source.get("end_ms")),
                                     "sourceStartMs": source.get("start_ms"), "sourceEndMs": source.get("end_ms"),
                                     "mediaAssetId": source.get("media_asset_id"),
                                     "timeline": "episode" if episode_id and position is not None else "file",
                                     "itemType": source.get("item_type", "movie")}],
                          diagnostics={"retrieval": "hybrid_rrf" if self.dense_ready else "bm25",
                                       "denseReady": self.dense_ready, "missingEmbeddings": self.missing_embeddings,
                                       "calibrated": probability is not None})
            results.append(result)
            used.add(result_id)
            if len(results) >= max(1, min(100, limit)):
                break
        return results


def prepare_embeddings(catalog, *, cache_dir, encoder, model_id, payload=None, content_hash=""):
    return TextIndex.build(catalog, cache_dir=cache_dir, encoder=encoder, model_id=model_id,
                           encode_missing=True, payload=payload, content_hash=content_hash)
