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
    """Tokenize lowercase words, preserving alphanumeric tokens, single digits, and Vietnamese words."""
    if not text:
        return []
    return [w.lower() for w in re.findall(r"\b\w+\b", text, flags=re.UNICODE) if len(w) > 1 or w.isdigit()]


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


GENRE_AND_DESCRIPTIVE_WORDS = {
    "gia đình", "gia dinh", "hài hước", "hai huoc", "hài", "hai", "vui nhộn", "vui nhon",
    "tình cảm", "tinh cam", "phiêu lưu", "phieu luu", "học đường", "hoc duong",
    "tuổi thơ", "tuoi tho", "bạn bè", "ban be", "đời thường", "doi thuong",
    "cuộc sống", "cuoc song", "kinh dị", "kinh di", "hành động", "hanh dong",
    "hoạt hình", "hoat hinh", "hoạt họa", "anime", "manga", "hoạt", "hình",
    "hay", "mới", "cũ", "ngắn", "dài", "chiếu rạp", "đặc biệt", "ngoại truyện",
    "trẻ em", "thiếu nhi", "tuổi mới lớn", "vui vẻ", "ý nghĩa", "cảm động",
    "nhẹ nhàng", "bựa", "lầy lội", "dễ thương", "học sinh", "cho", "về", "nhất",
    "gợi ý", "goi y", "gợi", "ý", "tìm", "tim", "xem", "phim", "bộ", "loạt", "các", "những"
}


def is_descriptive_not_franchise(phrase: str) -> bool:
    """
    Kiểm tra xem cụm từ có phải là mô tả thể loại/tính chất/chủ đề chung (không phải tên riêng franchise).
    Ví dụ: 'gia đình hài hước', 'vui nhộn cho gia đình' -> True
           'Doraemon', 'Shin', 'Conan' -> False
    """
    if not phrase:
        return True
    p = phrase.lower().strip()
    for gw in sorted(GENRE_AND_DESCRIPTIVE_WORDS, key=len, reverse=True):
        p = re.sub(r"\b" + re.escape(gw) + r"\b", " ", p)
    remaining = re.findall(r"\b\w+\b", p)
    return len(remaining) == 0


def split_query_scopes(query_text: str) -> Tuple[str, str]:
    """
    Tách truy vấn thành phạm vi khẳng định (positive search target) và phạm vi phủ định/loại trừ.
    Ví dụ: 'Jadoo chơi bóng, không phải tập 999' -> ('Jadoo chơi bóng,', 'tập 999')
    """
    if not query_text:
        return "", ""
    negation_pattern = r"\b(?:không phải|chứ không phải|tránh|không xem|trừ|bỏ qua|không muốn|không cần|đừng|không lấy|không có|không chứa)\b"
    parts = re.split(negation_pattern, query_text, maxsplit=1, flags=re.IGNORECASE)
    pos_scope = parts[0].strip()
    neg_scope = parts[1].strip() if len(parts) > 1 else ""
    return pos_scope, neg_scope


def parse_season_episode_intent(query_text: str) -> Tuple[Optional[int], Optional[int]]:
    """
    Trích xuất số mùa (season) và số tập (episode) bằng ranh giới từ chính xác.
    Bảo đảm:
      - 'tập 1' không bao giờ khớp 'tập 10' hay 'tập 11'
      - 'năm 2021' hay số trong tiêu đề không bị nhận nhầm thành tập
    """
    if not query_text:
        return None, None
    q_norm = query_text.lower()
    
    # Check SxxExx pattern first (e.g., S01E01, S3E1)
    se_match = re.search(r"\bs0*(\d+)e0*(\d+)\b", q_norm)
    if se_match:
        return int(se_match.group(1)), int(se_match.group(2))
    
    sea_num = None
    ep_num = None
    
    sea_match = re.search(r"\b(?:mùa|mua|season|phần|phan)\s*#?\s*0*(\d+)\b", q_norm)
    if sea_match:
        sea_num = int(sea_match.group(1))
        
    ep_match = re.search(r"\b(?:tập|tap|ep|episode)\s*#?\s*0*(\d+)\b", q_norm)
    if ep_match:
        ep_num = int(ep_match.group(1))
        
    return sea_num, ep_num


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

        # Series & Season context for hierarchical items (episodes, segments)
        series_title = movie.get("series_title")
        if series_title and isinstance(series_title, str):
            parts.extend([series_title, series_title])

        season_title = movie.get("season_title")
        if season_title and isinstance(season_title, str):
            parts.extend([season_title, season_title])

        season_num = movie.get("season_number")
        if season_num is not None:
            parts.extend([f"Mùa {season_num}", f"Season {season_num}", f"Phần {season_num}"])

        ep_num = movie.get("episode_number")
        if ep_num is not None:
            parts.extend([f"Tập {ep_num}", f"Tập {ep_num:02d}", f"Episode {ep_num}"])
            if season_num is not None:
                parts.extend([
                    f"Mùa {season_num} Tập {ep_num}",
                    f"Season {season_num} Episode {ep_num}",
                    f"S{season_num:02d}E{ep_num:02d}"
                ])

        parent_ep_title = movie.get("parent_episode_title") or movie.get("episode_title")
        if parent_ep_title and isinstance(parent_ep_title, str):
            parts.extend([parent_ep_title, parent_ep_title])

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

        # Determine positive search scope to avoid scoring negation tokens
        raw_query = str(nlu_intent.get("raw_query") or "").strip() if nlu_intent else ""
        effective_query = raw_query if raw_query else query_text
        pos_scope, neg_scope = split_query_scopes(effective_query)
        pos_q_text, _ = split_query_scopes(query_text)

        search_target_text = pos_q_text.strip() if pos_q_text.strip() else (pos_scope.strip() if pos_scope.strip() else query_text.strip())
        q_tokens = tokenize_text(search_target_text)
        query_dense = None
        if search_target_text:
            try:
                query_dense = self.encoder.encode_queries([search_target_text])[0]
            except Exception as e:
                logger.warning(f"[HybridMovieIndex] Dense encoding failed: {e}. Falling back to BM25 only.")

        # Hard constraints from NLU
        cons = nlu_intent.get("constraints") or {}
        inc_genres = set(cons.get("include_genres") or [])
        exc_genres = set(cons.get("exclude_genres") or [])
        year_min = cons.get("year_min")
        year_max = cons.get("year_max")

        # Fallback year inference from query text if NLU constraints missing
        if year_min is None and year_max is None and query_text:
            y_m = re.search(r"\b(19\d{2}|20\d{2})\b", query_text)
            if y_m:
                y_val = int(y_m.group(1))
                if any(w in query_text.lower() for w in ("trước", "before")):
                    year_max = y_val - 1
                elif any(w in query_text.lower() for w in ("sau", "after")):
                    year_min = y_val + 1
                else:
                    year_min = y_val
                    year_max = y_val

        # Item type filter (series, episode, segment, scene)
        target_types: set = set()
        q_lower = query_text.lower().strip()

        # 1. Highest priority: Infer specific item types directly from user query text
        if query_text:
            if any(w in q_lower for w in ("phân cảnh", "cảnh quay", "trích đoạn", "cảnh nhảy", "cảnh rượt", "cảnh ")):
                target_types.add("scene")
            elif any(w in q_lower for w in ("truyện ngắn", "mẩu chuyện", "tiểu phẩm")):
                target_types.add("segment")
            elif any(w in q_lower for w in ("tập phim", "tập ")):
                target_types.add("episode")
            elif any(w in q_lower for w in ("bộ phim", "bộ hoạt hình", "loạt phim")):
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
        is_similarity_search = any(
            pat in q_lower for pat in ["giống", "tương tự", "như phim", "similar", "like movie", "recommend like"]
        )
        if ref_text and is_similarity_search:
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

        # Available seasons and episodes in search catalog
        available_seasons = {m.get("season_number") for m in search_catalog if m.get("season_number") is not None}
        available_episodes = {m.get("episode_number") for m in search_catalog if m.get("episode_number") is not None}
        available_season_episodes = {
            (m.get("season_number"), m.get("episode_number"))
            for m in search_catalog if m.get("season_number") is not None and m.get("episode_number") is not None
        }

        scored_candidates = []
        raw_query = str(nlu_intent.get("raw_query") or "").strip() if nlu_intent else ""
        effective_query = raw_query if raw_query else query_text
        pos_scope, neg_scope = split_query_scopes(effective_query)
        pos_lower = pos_scope.lower().strip()
        pos_clean = re.sub(r"[^\w\s]", "", pos_lower).strip()

        pos_q_text, _ = split_query_scopes(query_text)
        pos_q_lower = pos_q_text.lower().strip()
        pos_q_clean = re.sub(r"[^\w\s]", "", pos_q_lower).strip()

        # Parse target season/episode strictly from positive affirmation scope
        query_sea, query_ep = parse_season_episode_intent(pos_scope)
        if query_sea is None and query_ep is None and raw_query and pos_q_text != pos_scope:
            query_sea, query_ep = parse_season_episode_intent(pos_q_text)
        # Parse excluded season/episode from negation scope
        excluded_sea, excluded_ep = parse_season_episode_intent(neg_scope) if neg_scope else (None, None)

        # Detect if user explicitly requested a specific franchise/series that is NOT in catalog
        # Pattern: "phim hoạt hình X", "bộ phim hoạt hình X", "phim X", "loạt phim X"
        if not is_similarity_search and pos_scope:
            franchise_match = re.search(
                r"(?:phim\s+hoạt\s+hình|bộ\s+phim\s+hoạt\s+hình|loạt\s+phim|bộ\s+hoạt\s+hình)\s+([A-ZÀ-Ỹa-zà-ỹ0-9_\-\s]{2,30}?)(?:\s+(?:tập|mùa|phần|bản|movie|chiếu\s+rạp|dài|ngắn|đặc\s+biệt|ngoại\s+truyện|về|có|không|phát\s+hành|năm)\b|$)",
                pos_scope,
                re.IGNORECASE
            )
            if franchise_match:
                req_franchise = franchise_match.group(1).strip()
                req_franchise_clean = re.sub(r"[^\w\s]", "", req_franchise.lower()).strip()
                catalog_series_names = set()
                for m in search_catalog:
                    if m.get("item_type") == "series" or "series" in str(m.get("item_type", "")).lower():
                        catalog_series_names.add(re.sub(r"[^\w\s]", "", str(m.get("title", "")).lower()).strip())
                        for a in m.get("aliases", []):
                            catalog_series_names.add(re.sub(r"[^\w\s]", "", str(a).lower()).strip())
                universe_keywords = {"jadoo", "jadu", "xin chao jadoo", "hello jadoo", "choi jadoo"}
                is_catalog_franchise = any(
                    req_franchise_clean == name or req_franchise_clean in name or name in req_franchise_clean
                    for name in (catalog_series_names | universe_keywords)
                    if name
                )
                if not is_catalog_franchise and len(req_franchise_clean) >= 3 and not is_descriptive_not_franchise(req_franchise):
                    logger.info(f"[HybridRetrieval] Foreign franchise detected in positive query: '{req_franchise}'. Abstaining.")
                    return []

        # Validate existence ONLY for positive requested target
        if query_sea is not None and query_sea not in available_seasons:
            return []
        if query_sea is not None and query_ep is not None and (query_sea, query_ep) not in available_season_episodes:
            return []
        if query_sea is None and query_ep is not None and query_ep not in available_episodes:
            return []

        # Detect conflict between requested episode number and explicit title match
        detected_conflict = None
        if query_ep is not None:
            for m in search_catalog:
                m_t = str(m.get("title", "")).strip().lower()
                m_ep = m.get("episode_number")
                if m_t and len(m_t) >= 4 and (m_t in pos_lower or m_t in pos_q_lower):
                    if m_ep is not None and m_ep != query_ep:
                        detected_conflict = {
                            "type": "EPISODE_TITLE_CONFLICT",
                            "requested_episode": query_ep,
                            "conflicting_episode": m_ep,
                            "conflicting_title": m.get("title")
                        }
                        break

        q_lower = f"{raw_query} {query_text}".lower().strip() if raw_query else query_text.lower().strip()
        q_token_set = set(tokenize_text(q_lower))
        pos_token_set = set(tokenize_text(pos_scope.lower())) if pos_scope else q_token_set

        for m in search_catalog:
            mid = m["id"]
            m_type = normalize_item_type(m.get("item_type", "")) or str(m.get("item_type", "")).lower()
            ep_num = m.get("episode_number")
            sea_num = m.get("season_number")

            # Exclusion constraints from negation scope
            if excluded_ep is not None and ep_num == excluded_ep:
                continue
            if excluded_sea is not None and sea_num == excluded_sea:
                continue

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
            title_lower = str(m.get("title", "")).lower().strip()
            title_clean = re.sub(r"[^\w\s]", "", title_lower).strip()
            title_tokens = set(tokenize_text(title_clean))
            ref_clean = re.sub(r"[^\w\s]", "", str(ref_text or "").lower()).strip()

            is_exact_title = False
            if title_clean and len(title_clean) >= 4:
                if title_clean == ref_clean:
                    is_exact_title = True
                elif title_clean == pos_clean or title_clean in pos_clean:
                    is_exact_title = True
                elif title_clean == pos_q_clean or title_clean in pos_q_clean:
                    is_exact_title = True
                elif title_lower in pos_lower or title_lower in pos_q_lower:
                    is_exact_title = True

            if is_exact_title:
                if len(title_tokens) <= 2 and len(q_token_set) >= 5 and "jadoo" not in q_lower:
                    hybrid_score += 0.20
                elif m_type == "series":
                    hybrid_score += 1.50
                else:
                    hybrid_score += 1.30
            elif title_tokens and len(title_tokens) >= 3 and title_tokens.issubset(pos_token_set):
                hybrid_score += 1.15
            else:
                # Word-boundary alias matching on positive affirmation scope only
                matched_alias = False
                for a in m.get("aliases", []):
                    a_str = str(a).strip().lower()
                    a_clean = re.sub(r"[^\w\s]", "", a_str).strip()
                    if not a_clean:
                        continue
                    if re.search(r"\d", a_str):
                        a_pat = r"\b" + re.escape(a_str) + r"\b"
                        if re.search(a_pat, pos_lower) or re.search(a_pat, pos_q_lower):
                            matched_alias = True
                            break
                    else:
                        if a_str in pos_lower or a_str in pos_q_lower or (len(a_clean) >= 6 and (a_clean in pos_clean or a_clean in pos_q_clean)):
                            matched_alias = True
                            break
                if matched_alias:
                    hybrid_score += 0.75
                elif title_tokens and len(title_tokens) >= 2 and (len(title_tokens & q_token_set) / len(title_tokens)) >= 0.75:
                    hybrid_score += 0.60

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

            # Match Boost 6: Season + Episode Number exact match
            ep_num = m.get("episode_number")
            sea_num = m.get("season_number")
            if ep_num is not None:
                if query_ep is not None and query_sea is not None:
                    if ep_num == query_ep and sea_num == query_sea:
                        hybrid_score += 2.00
                    elif ep_num == query_ep and sea_num != query_sea:
                        hybrid_score -= 2.00
                    else:
                        hybrid_score -= 2.50
                elif query_ep is not None:
                    if ep_num == query_ep:
                        hybrid_score += 1.60
                    else:
                        hybrid_score -= 2.00

            # Match Boost 7: Segment exact title match
            if m_type == "segment":
                seg_t = str(m.get("title", "")).lower()
                if seg_t and seg_t in q_lower:
                    hybrid_score += 0.90

            item_diag = {}
            if detected_conflict:
                item_diag["conflict"] = detected_conflict

            scored_candidates.append({
                "movie": m,
                "score": round(hybrid_score, 4),
                "bm25_score": round(norm_bm25, 4),
                "dense_score": round(dense_sim, 4),
                "rating": m.get("rating"),
                "diagnostics": item_diag
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
                    "rating": m.get("rating"),
                    "diagnostics": {"conflict": detected_conflict} if detected_conflict else {}
                })

        # Sort by hybrid score descending
        scored_candidates.sort(key=lambda x: x["score"], reverse=True)

        # Confidence guard for unanswerable / out-of-catalog queries (Issue A2)
        if scored_candidates:
            top_item = scored_candidates[0]
            top_score = top_item["score"]
            top_bm25 = top_item["bm25_score"]
            top_dense = top_item["dense_score"]
            raw_top_bm25 = bm25_raw.get(top_item["movie"]["id"], 0.0)

            # Check if top item earned a strong exact boost (exact title, exact season/episode, or segment title)
            has_strong_boost = (top_score - (0.6 * top_dense + 0.4 * top_bm25)) >= 0.40

            # 1. Analyze query context: detect positive search target vs negation/exclusion
            raw_text = str(nlu_intent.get("raw_query") or query_text)
            negation_pattern = r"\b(?:không phải|chứ không phải|tránh|không xem|trừ|bỏ qua|không muốn)\b"
            neg_parts = re.split(negation_pattern, raw_text, flags=re.IGNORECASE)
            pos_text = neg_parts[0] if neg_parts else raw_text

            # 2. Check if query is targeting Jadoo universe in its positive clause
            JADOO_UNIVERSE = {
                "jadoo", "jadu", "minji", "mimi", "seung-gi", "seunggi", "ho-dol", "hodol",
                "nan-hee", "nanhee", "doldol", "yun-seok", "eun-hee", "seong-hoon", "min-woo",
                "romy", "e-cha"
            }
            pos_words = set(tokenize_text(pos_text.lower()))
            is_jadoo_targeted = bool(pos_words & JADOO_UNIVERSE) or (query_ep is not None)

            # 3. Compute informative content tokens
            generic_stop = {
                "phim", "hoạt", "hình", "tập", "bộ", "mùa", "cho", "tôi", "xem", "tìm",
                "gợi", "ý", "hay", "nhất", "những", "của", "và", "với", "năm", "không", "có", "nào"
            }
            content_tokens = [t for t in tokenize_text(pos_text) if t not in generic_stop and len(t) >= 2]

            doc_text = self.build_searchable_document_text(top_item["movie"]).lower()
            matched_content = [t for t in content_tokens if t in doc_text]
            overlap_ratio = len(matched_content) / len(content_tokens) if content_tokens else 1.0

            is_genre_or_descriptive = is_descriptive_not_franchise(pos_text) or bool(inc_genres)

            # Decision rules:
            ref_status = (nlu_intent.get("reference") or {}).get("status")
            if ref_status == "UNRESOLVED_REFERENCE" and not is_jadoo_targeted and not has_strong_boost:
                return []

            if not has_strong_boost:
                if is_genre_or_descriptive:
                    # Generic genre/theme discovery (e.g. 'phim hoạt hình gia đình hài hước')
                    if top_score < 0.15 and overlap_ratio < 0.15 and top_dense < 0.40:
                        return []
                elif not is_jadoo_targeted:
                    # Query does NOT target Jadoo and has no exact title/segment boost
                    if overlap_ratio < 0.45 or raw_top_bm25 < 12.0:
                        return []
                else:
                    # Query mentions Jadoo, but if user asked for a completely fabricated premise
                    non_jadoo_content = [t for t in content_tokens if t not in JADOO_UNIVERSE]
                    if len(non_jadoo_content) >= 2:
                        matched_non_jadoo = [t for t in non_jadoo_content if t in doc_text]
                        non_jadoo_overlap = len(matched_non_jadoo) / len(non_jadoo_content)
                        if non_jadoo_overlap < 0.20 and raw_top_bm25 < 5.0:
                            return []

        return scored_candidates

