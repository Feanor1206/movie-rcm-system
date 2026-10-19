"""
True Hybrid Retrieval Engine for Dippie Cinema (REC-01).

Combines:
1. True BM25 Lexical Keyword Search (Robertson-Spärck Jones formula with length normalization).
2. Dense Semantic Vector Search (intfloat/multilingual-e5-small, 384 dimensions, normalized cosine similarity).
3. Field-weighted metadata indexing (title, aliases, verified plot facts, characters, themes, synopsis).
4. Precomputed index caching with content hash, encoder metadata, and fallback handling.
"""

import os
import re
import math
import json
import hashlib
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Union

logger = logging.getLogger("moviercm.hybrid_retrieval")
if not logger.handlers:
    logging.basicConfig(level=logging.INFO)

INDEX_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data" / "indices"
DEFAULT_INDEX_PATH = INDEX_DIR / "movie_index_v1.json"
ENCODER_MODEL_NAME = "intfloat/multilingual-e5-small"
ENCODER_DIMENSION = 384


# =============================================================================
# 1. TEXT TOKENIZER & NORMALIZER
# =============================================================================
def tokenize_text(text: str) -> List[str]:
    """Tokenize lowercase words, preserving alphanumeric tokens and Vietnamese words."""
    if not text:
        return []
    return [w.lower() for w in re.findall(r"\b\w+\b", text, flags=re.UNICODE) if len(w) > 1]


ITEM_TYPE_SYNONYMS = {
    "series": {"series", "bộ", "bo", "bộ phim", "phim bộ", "show", "show truyền hình"},
    "season": {"season", "mùa", "mua", "phần", "phan"},
    "episode": {"episode", "tập", "tap", "tập phim"},
    "segment": {"segment", "truyện ngắn", "truyen ngan", "đoạn", "doan", "phần nhỏ"},
    "scene": {"scene", "scenes", "cảnh", "canh", "phân cảnh", "phan canh", "trích đoạn", "trich doan", "cảnh quay"}
}

def normalize_item_type(val: Optional[str]) -> Optional[str]:
    if not val:
        return None
    v = str(val).lower().strip()
    for canonical, syns in ITEM_TYPE_SYNONYMS.items():
        if v in syns or any(s in v for s in syns):
            return canonical
    return v


# =============================================================================
# 2. TRUE BM25 SCORER
# =============================================================================
class BM25Index:
    """
    Standard BM25 implementation (k1=1.5, b=0.75).
    Score(D, Q) = sum_{q in Q} IDF(q) * (f(q, D) * (k1 + 1)) / (f(q, D) + k1 * (1 - b + b * (|D| / avgdl)))
    """
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.corpus_size: int = 0
        self.avg_doc_len: float = 0.0
        self.doc_lengths: Dict[str, int] = {}
        self.doc_freqs: Dict[str, int] = {}  # term -> number of docs containing term
        self.doc_term_freqs: Dict[str, Dict[str, int]] = {}  # doc_id -> {term -> count}
        self.idf: Dict[str, float] = {}

    def fit(self, documents: Dict[str, List[str]]):
        """Build BM25 statistics from {doc_id: token_list}"""
        self.doc_freqs.clear()
        self.doc_lengths.clear()
        self.doc_term_freqs.clear()
        self.idf.clear()
        self.corpus_size = len(documents)
        if self.corpus_size == 0:
            self.avg_doc_len = 0.0
            return

        total_length = 0

        for doc_id, tokens in documents.items():
            length = len(tokens)
            self.doc_lengths[doc_id] = length
            total_length += length

            tf: Dict[str, int] = {}
            for t in tokens:
                tf[t] = tf.get(t, 0) + 1
            self.doc_term_freqs[doc_id] = tf

            for t in set(tokens):
                self.doc_freqs[t] = self.doc_freqs.get(t, 0) + 1

        self.avg_doc_len = total_length / self.corpus_size if self.corpus_size > 0 else 0.0

        # Calculate standard Robertson-Spärck Jones IDF
        self.idf.clear()
        for term, df in self.doc_freqs.items():
            # Standard Lucene/BM25 IDF: ln((N - df + 0.5) / (df + 0.5) + 1.0)
            self.idf[term] = math.log((self.corpus_size - df + 0.5) / (df + 0.5) + 1.0)

    def score(self, query_tokens: List[str], doc_id: str) -> float:
        """Calculate BM25 score for a specific document against query tokens."""
        if doc_id not in self.doc_term_freqs or self.avg_doc_len == 0.0:
            return 0.0

        doc_len = self.doc_lengths.get(doc_id, 0)
        tf_map = self.doc_term_freqs.get(doc_id, {})
        score = 0.0

        for q in query_tokens:
            if q not in tf_map or q not in self.idf:
                continue
            freq = tf_map[q]
            idf_val = self.idf[q]
            denom = freq + self.k1 * (1.0 - self.b + self.b * (doc_len / self.avg_doc_len))
            score += idf_val * (freq * (self.k1 + 1.0)) / denom

        return score


# =============================================================================
# 3. DENSE ENCODER (multilingual-e5-small)
# =============================================================================
class DenseEncoder:
    """Wrapper for multilingual-e5-small dense representation model."""
    def __init__(self, model_name: str = ENCODER_MODEL_NAME):
        self.model_name = model_name
        self.tokenizer = None
        self.model = None
        self.is_loaded = False

    def load(self):
        if self.is_loaded:
            return
        try:
            from transformers import AutoTokenizer, AutoModel
            import torch
            logger.info(f"[DenseEncoder] Loading {self.model_name}...")
            try:
                self.tokenizer = AutoTokenizer.from_pretrained(self.model_name, local_files_only=True)
                self.model = AutoModel.from_pretrained(self.model_name, local_files_only=True)
            except Exception:
                self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
                self.model = AutoModel.from_pretrained(self.model_name)
            self.model.eval()
            self.is_loaded = True
        except Exception as e:
            logger.warning(f"[DenseEncoder] Could not load dense model ({e}). Operating in lexical BM25 fallback mode.")
            self.is_loaded = False

    def encode_queries(self, queries: List[str]) -> List[List[float]]:
        """Encode query text with 'query: ' prefix and L2 normalization."""
        if not self.is_loaded:
            self.load()
        if not self.is_loaded:
            return [[0.0] * ENCODER_DIMENSION for _ in queries]
        import torch
        prefixed = [f"query: {q}" for q in queries]
        inputs = self.tokenizer(prefixed, padding=True, truncation=True, max_length=512, return_tensors="pt")
        with torch.no_grad():
            outputs = self.model(**inputs)
            # Mean pooling
            mask = inputs["attention_mask"].unsqueeze(-1).expand(outputs.last_hidden_state.size()).float()
            sum_embeddings = torch.sum(outputs.last_hidden_state * mask, 1)
            sum_mask = torch.clamp(mask.sum(1), min=1e-9)
            mean_pooled = sum_embeddings / sum_mask
            # L2 normalize
            normalized = torch.nn.functional.normalize(mean_pooled, p=2, dim=1)
        return normalized.cpu().tolist()

    def encode_documents(self, documents: List[str]) -> List[List[float]]:
        """Encode document text with 'passage: ' prefix and L2 normalization."""
        if not self.is_loaded:
            self.load()
        if not self.is_loaded:
            return [[0.0] * ENCODER_DIMENSION for _ in documents]
        import torch
        prefixed = [f"passage: {d}" for d in documents]
        inputs = self.tokenizer(prefixed, padding=True, truncation=True, max_length=512, return_tensors="pt")
        with torch.no_grad():
            outputs = self.model(**inputs)
            mask = inputs["attention_mask"].unsqueeze(-1).expand(outputs.last_hidden_state.size()).float()
            sum_embeddings = torch.sum(outputs.last_hidden_state * mask, 1)
            sum_mask = torch.clamp(mask.sum(1), min=1e-9)
            mean_pooled = sum_embeddings / sum_mask
            normalized = torch.nn.functional.normalize(mean_pooled, p=2, dim=1)
        return normalized.cpu().tolist()


# =============================================================================
# 4. HYBRID RETRIEVAL INDEX & ENGINE
# =============================================================================
class HybridMovieIndex:
    """
    Manages indexing and hybrid search over the movie and multi-level catalog.
    """
    def __init__(self, index_path: Optional[Path] = None):
        self.index_path = index_path or DEFAULT_INDEX_PATH
        self.bm25 = BM25Index()
        self.encoder = DenseEncoder()
        self.documents: Dict[str, Dict[str, Any]] = {}
        self.embeddings: Dict[str, List[float]] = {}
        self.metadata_index: Dict[str, Any] = {}
        self.is_ready = False

    @staticmethod
    def compute_content_hash(catalog: List[Dict[str, Any]]) -> str:
        """Compute SHA-256 of sorted catalog content for freshness check."""
        serialized = json.dumps(sorted(catalog, key=lambda x: str(x.get("id"))), sort_keys=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    @staticmethod
    def build_searchable_document_text(movie: Dict[str, Any]) -> str:
        """Construct weighted document text from metadata fields."""
        parts = []
        # Title repeated 3x for strong term boost
        title = movie.get("title", "")
        if title:
            parts.extend([title, title, title])

        # Aliases repeated 2x
        aliases = movie.get("aliases", [])
        if isinstance(aliases, list):
            for a in aliases:
                if isinstance(a, str) and a.strip():
                    parts.extend([a.strip(), a.strip()])

        # Characters: names & aliases repeated 2x for high character query recall
        chars = movie.get("characters", [])
        if isinstance(chars, list):
            for c in chars:
                if isinstance(c, str) and c.strip():
                    parts.extend([c.strip(), c.strip()])

        # Plot facts (strings or objects with 'text')
        facts = movie.get("plot_facts", [])
        if isinstance(facts, list):
            for f in facts:
                if isinstance(f, str) and f.strip():
                    parts.append(f.strip())
                elif isinstance(f, dict) and "text" in f:
                    parts.append(str(f["text"]).strip())

        # Keywords and themes
        for key in ("keywords", "themes"):
            val_list = movie.get(key, [])
            if isinstance(val_list, list):
                for val in val_list:
                    if isinstance(val, str) and val.strip():
                        parts.append(val.strip())

        # Scene visual & dialogue summaries
        vis_sum = movie.get("visual_summary") or movie.get("visual_description")
        if vis_sum and isinstance(vis_sum, str):
            parts.extend([vis_sum.strip(), vis_sum.strip()])

        dial_sum = movie.get("dialogue_summary")
        if dial_sum and isinstance(dial_sum, str):
            parts.append(dial_sum.strip())

        sound_evs = movie.get("sound_events", [])
        if isinstance(sound_evs, list):
            for se in sound_evs:
                if isinstance(se, str) and se.strip():
                    parts.append(se.strip())

        # Backward compatibility for legacy verified_facts dict
        v_facts = movie.get("verified_facts", {})
        if isinstance(v_facts, dict):
            for k in ("plot_facts", "characters", "themes", "keywords"):
                val = v_facts.get(k)
                if isinstance(val, list):
                    parts.extend([str(v) for v in val if v])

        # Genres
        genres = movie.get("genres", [])
        if isinstance(genres, list):
            for g in genres:
                if isinstance(g, str) and g.strip():
                    parts.append(g.strip())

        # Synopsis or description
        synopsis = movie.get("description") or movie.get("synopsis") or ""
        if synopsis and isinstance(synopsis, str):
            parts.append(synopsis.strip())

        return " ".join(parts)

    def build_from_catalog(self, catalog: List[Dict[str, Any]], save_to_disk: bool = True):
        """Construct BM25 and Dense index from a catalog list."""
        logger.info(f"[HybridMovieIndex] Building index for {len(catalog)} items...")
        self.documents.clear()
        self.embeddings.clear()
        doc_texts: Dict[str, str] = {}
        tokenized_corpus: Dict[str, List[str]] = {}

        if not catalog:
            self.bm25.fit({})
            content_hash = self.compute_content_hash([])
            self.metadata_index = {
                "index_version": "1.0.0",
                "encoder_id": ENCODER_MODEL_NAME,
                "encoder_dimension": ENCODER_DIMENSION,
                "content_hash": content_hash,
                "movie_count": 0,
                "doc_ids": []
            }
            self.is_ready = True
            if save_to_disk:
                self.save_index()
            return

        for m in catalog:
            mid = m["id"]
            text = self.build_searchable_document_text(m)
            doc_texts[mid] = text
            tokenized_corpus[mid] = tokenize_text(text)
            self.documents[mid] = dict(m)

        # 1. Fit BM25
        self.bm25.fit(tokenized_corpus)

        # 2. Encode Dense Vectors
        ids = list(doc_texts.keys())
        texts = [doc_texts[mid] for mid in ids]
        try:
            dense_vecs = self.encoder.encode_documents(texts)
            for mid, vec in zip(ids, dense_vecs):
                self.embeddings[mid] = vec
        except Exception as e:
            logger.warning(f"[HybridMovieIndex] Dense encoding batch failed: {e}. BM25 ready.")
            self.embeddings.clear()

        content_hash = self.compute_content_hash(catalog)
        self.metadata_index = {
            "index_version": "1.0.0",
            "encoder_id": ENCODER_MODEL_NAME,
            "encoder_dimension": ENCODER_DIMENSION,
            "content_hash": content_hash,
            "movie_count": len(catalog),
            "doc_ids": ids
        }

        self.is_ready = True

        if save_to_disk:
            self.save_index()

    def save_index(self):
        """Persist index metadata, BM25 tokens, and dense embeddings to disk."""
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        dump_data = {
            "metadata": self.metadata_index,
            "documents": self.documents,
            "embeddings": self.embeddings,
            "doc_lengths": self.bm25.doc_lengths,
            "avg_doc_len": self.bm25.avg_doc_len,
            "doc_freqs": self.bm25.doc_freqs,
            "doc_term_freqs": self.bm25.doc_term_freqs,
            "idf": self.bm25.idf
        }
        with open(self.index_path, "w", encoding="utf-8") as f:
            json.dump(dump_data, f, ensure_ascii=False)
        logger.info(f"[HybridMovieIndex] Saved precomputed index to {self.index_path}")

    def load_index(self) -> bool:
        """Load precomputed index from disk if available."""
        if not self.index_path.exists():
            logger.warning(f"[HybridMovieIndex] Index file {self.index_path} not found.")
            return False

        try:
            with open(self.index_path, "r", encoding="utf-8") as f:
                dump_data = json.load(f)

            self.metadata_index = dump_data.get("metadata", {})
            self.documents = dump_data.get("documents", {})
            self.embeddings = dump_data.get("embeddings", {})

            self.bm25.doc_lengths = dump_data.get("doc_lengths", {})
            self.bm25.avg_doc_len = float(dump_data.get("avg_doc_len", 0.0))
            self.bm25.doc_freqs = dump_data.get("doc_freqs", {})
            self.bm25.doc_term_freqs = dump_data.get("doc_term_freqs", {})
            self.bm25.idf = dump_data.get("idf", {})
            self.bm25.corpus_size = len(self.documents)

            self.is_ready = True
            logger.info(f"[HybridMovieIndex] Loaded index ({len(self.documents)} docs) from {self.index_path}")
            return True
        except Exception as e:
            logger.error(f"[HybridMovieIndex] Failed to load index from {self.index_path}: {e}")
            return False

    def is_stale(self, catalog: List[Dict[str, Any]]) -> bool:
        """Check if catalog content has changed compared to loaded index."""
        current_hash = self.compute_content_hash(catalog)
        return self.metadata_index.get("content_hash") != current_hash

    def search_hybrid(
        self,
        query_text: str,
        nlu_intent: Dict[str, Any],
        catalog: Optional[List[Dict[str, Any]]] = None,
        dense_weight: float = 0.6,
        bm25_weight: float = 0.4,
        item_type_filter: Optional[Union[str, List[str]]] = None
    ) -> List[Dict[str, Any]]:
        """
        Execute True Hybrid Retrieval (BM25 + Dense) with multi-level catalog filtering and weighting.
        """
        # Resolve corpus
        search_catalog = list(catalog) if catalog is not None else list(self.documents.values())

        if not self.is_ready or (catalog is not None and self.is_stale(catalog)):
            logger.info("[HybridMovieIndex] Rebuilding index due to missing or stale cache...")
            self.build_from_catalog(search_catalog, save_to_disk=True)

        q_tokens = tokenize_text(query_text)
        query_dense = None
        if query_text.strip():
            try:
                query_dense = self.encoder.encode_queries([query_text])[0]
            except Exception as e:
                logger.warning(f"[HybridMovieIndex] Dense encoding failed: {e}. Falling back to BM25 only.")

        # Hard constraints from NLU
        cons = nlu_intent.get("constraints") or {}
        inc_genres = set(cons.get("include_genres") or [])
        exc_genres = set(cons.get("exclude_genres") or [])
        year_min = cons.get("year_min")
        year_max = cons.get("year_max")

        # Item type filter (series, episode, segment, scene)
        target_types: set = set()

        # 1. Highest priority: Infer specific item types directly from user query text
        if query_text:
            q_lower_check = query_text.lower()
            if any(w in q_lower_check for w in ("phân cảnh", "cảnh quay", "trích đoạn", "cảnh nhảy", "cảnh rượt", "cảnh ")):
                target_types.add("scene")
            elif any(w in q_lower_check for w in ("truyện ngắn", "mẩu chuyện", "tiểu phẩm")):
                target_types.add("segment")
            elif any(w in q_lower_check for w in ("tập phim", "tập ")):
                target_types.add("episode")
            elif any(w in q_lower_check for w in ("bộ phim", "bộ hoạt hình", "loạt phim")):
                target_types.add("series")

        # 2. Second priority: Explicit item_type_filter argument or NLU parsed item_type
        if not target_types:
            raw_types = []
            if item_type_filter:
                if isinstance(item_type_filter, str):
                    raw_types.append(item_type_filter)
                elif isinstance(item_type_filter, (list, tuple, set)):
                    raw_types.extend(item_type_filter)
            nlu_item_type = nlu_intent.get("item_type") or cons.get("item_type")
            if nlu_item_type:
                if isinstance(nlu_item_type, str):
                    raw_types.append(nlu_item_type)
                elif isinstance(nlu_item_type, (list, tuple, set)):
                    raw_types.extend(nlu_item_type)

            for raw_t in raw_types:
                canon = normalize_item_type(raw_t)
                if canon:
                    target_types.add(canon)

        # 3. If target_types is generic ("movie", "film"), do NOT filter out animation hierarchy items
        if target_types.issubset({"movie", "film"}):
            target_types.clear()

        ref_film = None
        ref_text = (nlu_intent.get("reference") or {}).get("text")
        if ref_text:
            ref_text_lower = ref_text.lower().strip()
            for m in search_catalog:
                if m.get("title", "").lower() == ref_text_lower or any(ref_text_lower in str(a).lower() for a in m.get("aliases", [])):
                    ref_film = m
                    break

        # Calculate raw scores
        bm25_raw: Dict[str, float] = {}
        dense_raw: Dict[str, float] = {}

        for m in search_catalog:
            mid = m["id"]
            # 1. BM25 score
            bm25_raw[mid] = self.bm25.score(q_tokens, mid)

            # 2. Dense cosine similarity (dot product of L2 normalized vectors)
            if query_dense and mid in self.embeddings and any(self.embeddings[mid]):
                d_vec = self.embeddings[mid]
                sim = sum(q_v * d_v for q_v, d_v in zip(query_dense, d_vec))
                dense_raw[mid] = max(0.0, sim)
            else:
                dense_raw[mid] = 0.0

        # Normalize BM25 scores to [0, 1]
        max_bm25 = max(bm25_raw.values()) if bm25_raw and max(bm25_raw.values()) > 0 else 1.0

        scored_candidates = []
        q_lower = query_text.lower().strip()
        q_token_set = set(q_tokens)

        for m in search_catalog:
            mid = m["id"]
            m_type = normalize_item_type(m.get("item_type", "")) or str(m.get("item_type", "")).lower()

            # Hard Constraint: Item Type Filter
            if target_types and m_type and (m_type not in target_types):
                continue

            # Hard Constraint: Exclude Genres (case-insensitive)
            m_genres = m.get("genres") or []
            m_genres_lower = {str(g).lower() for g in m_genres}
            exc_genres_lower = {str(g).lower() for g in exc_genres}
            if exc_genres_lower and (m_genres_lower & exc_genres_lower):
                continue

            # Hard Constraint: Year Range
            m_year = m.get("year") if m.get("year") is not None else m.get("release_year")
            if m_year is not None and isinstance(m_year, int) and m_year > 0:
                if year_min is not None and m_year < year_min:
                    continue
                if year_max is not None and m_year > year_max:
                    continue

            # Do not recommend the reference movie itself
            if ref_film and mid == ref_film["id"]:
                continue

            norm_bm25 = bm25_raw[mid] / max_bm25 if max_bm25 > 0 else 0.0
            dense_sim = dense_raw[mid]

            # Weighted combination
            effective_dense_weight = dense_weight if (query_dense and mid in self.embeddings and any(self.embeddings[mid])) else 0.0
            effective_bm25_weight = 1.0 if effective_dense_weight == 0.0 else bm25_weight
            hybrid_score = (effective_dense_weight * dense_sim) + (effective_bm25_weight * norm_bm25)

            # Match Boost 1: Exact title or alias match
            title_lower = str(m.get("title", "")).lower()
            aliases_lower = [str(a).lower() for a in m.get("aliases", []) if a]
            if title_lower and title_lower in q_lower:
                hybrid_score += 0.45
            elif any(a in q_lower for a in aliases_lower):
                hybrid_score += 0.40

            # Match Boost 2: Character names and aliases
            char_list = [str(c).lower() for c in m.get("characters", []) if c]
            if any(c in q_lower for c in char_list):
                hybrid_score += 0.35

            # Match Boost 3: Plot facts overlap
            facts_list = m.get("plot_facts", [])
            facts_tokens = set()
            for f in facts_list:
                f_text = f.get("text", "") if isinstance(f, dict) else str(f)
                facts_tokens.update(tokenize_text(f_text))
            if q_token_set and facts_tokens and (q_token_set & facts_tokens):
                hybrid_score += 0.25 * (len(q_token_set & facts_tokens) / len(q_token_set))

            # Match Boost 4: Scene visual description overlap
            vis_sum = str(m.get("visual_summary") or m.get("visual_description") or "")
            if vis_sum:
                vis_tokens = set(tokenize_text(vis_sum))
                if q_token_set and vis_tokens and (q_token_set & vis_tokens):
                    hybrid_score += 0.25 * (len(q_token_set & vis_tokens) / len(q_token_set))

            # Match Boost 5: Genre alignment bonus
            if inc_genres:
                inc_lower = {str(g).lower() for g in inc_genres}
                matched_genres = m_genres_lower & inc_lower
                hybrid_score += len(matched_genres) * 0.15

            scored_candidates.append({
                "movie": m,
                "score": round(hybrid_score, 4),
                "bm25_score": round(norm_bm25, 4),
                "dense_score": round(dense_sim, 4),
                "rating": m.get("rating", 8.0)
            })

        # Graceful fallback: If strict item_type filtering yielded 0 candidates, relax item_type constraint
        if not scored_candidates and target_types:
            for m in search_catalog:
                mid = m["id"]
                m_genres = m.get("genres") or []
                m_genres_lower = {str(g).lower() for g in m_genres}
                exc_genres_lower = {str(g).lower() for g in exc_genres}
                if exc_genres_lower and (m_genres_lower & exc_genres_lower):
                    continue
                m_year = m.get("year") if m.get("year") is not None else m.get("release_year")
                if m_year is not None and isinstance(m_year, int) and m_year > 0:
                    if year_min is not None and m_year < year_min:
                        continue
                    if year_max is not None and m_year > year_max:
                        continue
                if ref_film and mid == ref_film["id"]:
                    continue

                norm_bm25 = bm25_raw[mid] / max_bm25 if max_bm25 > 0 else 0.0
                dense_sim = dense_raw[mid]
                effective_dense_weight = dense_weight if (query_dense and mid in self.embeddings and any(self.embeddings[mid])) else 0.0
                effective_bm25_weight = 1.0 if effective_dense_weight == 0.0 else bm25_weight
                hybrid_score = (effective_dense_weight * dense_sim) + (effective_bm25_weight * norm_bm25)
                title_lower = str(m.get("title", "")).lower()
                aliases_lower = [str(a).lower() for a in m.get("aliases", []) if a]
                if title_lower and title_lower in q_lower:
                    hybrid_score += 0.45
                elif any(a in q_lower for a in aliases_lower):
                    hybrid_score += 0.40
                char_list = [str(c).lower() for c in m.get("characters", []) if c]
                if any(c in q_lower for c in char_list):
                    hybrid_score += 0.35
                scored_candidates.append({
                    "movie": m,
                    "score": round(hybrid_score, 4),
                    "bm25_score": round(norm_bm25, 4),
                    "dense_score": round(dense_sim, 4),
                    "rating": m.get("rating", 8.0)
                })

        # Sort by hybrid score descending
        scored_candidates.sort(key=lambda x: x["score"], reverse=True)
        return scored_candidates

