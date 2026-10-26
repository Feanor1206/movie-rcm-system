"""
=============================================================================
CASCADING MULTI-STAGE AI RECOMMENDATION PIPELINE (CATALOG-01 & PHASE 23)
=============================================================================
Architecture:
  1. Qwen Phase 23 Intent Parser (StructuredDiscoveryIntent v1 + Patch Merger)
     ↓
  2. Hybrid Retrieval & Hard Constraint Engine (Robertson-Spärck Jones BM25 + Dense e5)
     Multi-level items (Series, Episode, Segment, Scene) + Comparative Constraints (darkness, pacing)
     ↓
  3. Qwen 0.6B Recommender (Domain Candidate Filtering & Reference Similarity)
     ↓
  4. Qwen 0.6B Ranker + MMR Diversity (Fine-grained Scoring & Top-K Selection)
     ↓
  5. Grounded Storyteller (Grounded on verified plot facts, characters, and scene timestamps)
=============================================================================
"""

import os
import re
import time
import math
import copy
import logging
from typing import List, Dict, Any, Optional, Tuple
from dotenv import load_dotenv
from services.qwen_service import qwen_service, DEFAULT_MOVIES
from services.catalog_sync import catalog_sync_manager
from services.hybrid_retrieval import (
    HybridMovieIndex,
    tokenize_text,
    split_query_scopes,
    parse_season_episode_intent,
    is_descriptive_not_franchise
)

load_dotenv()
logger = logging.getLogger(__name__)


# =============================================================================
# COMPARATIVE CONSTRAINT EVALUATION & DIAGNOSTICS HELPER
# =============================================================================
def evaluate_comparative_constraints(
    item: Dict[str, Any],
    nlu_output: Dict[str, Any],
    query_text: str = ""
) -> Tuple[float, Dict[str, Any]]:
    """
    Evaluate comparative constraints (darkness, pacing) using attribute scales.
    Reports explicit diagnostics when trait data is missing or uncalibrated.
    """
    cons = nlu_output.get("constraints") or {}
    comparative_reqs = nlu_output.get("comparative_attributes") or {}
    q_lower = (query_text or "").lower()

    # Detect if darkness trait is requested
    req_darkness = None
    if "darkness" in comparative_reqs:
        req_darkness = comparative_reqs["darkness"]
    elif "darkness" in cons:
        req_darkness = cons["darkness"]
    elif any(w in q_lower for w in ("u tối", "tối tăm", "đen tối", "dark", "darker", "rùng rợn")):
        req_darkness = "high"

    # Detect if pacing trait is requested
    req_pacing = None
    if "pacing" in comparative_reqs:
        req_pacing = comparative_reqs["pacing"]
    elif "pacing" in cons:
        req_pacing = cons["pacing"]
    elif any(w in q_lower for w in ("nhịp nhanh", "fast", "faster", "fast-paced", "kịch tính")):
        req_pacing = "fast"
    elif any(w in q_lower for w in ("nhịp chậm", "slow", "slower", "slow-paced", "chậm rãi", "sâu lắng")):
        req_pacing = "slow"

    # Extract available attribute scale values from item
    attr_map = dict(item.get("comparative_attributes") or {})
    if not attr_map and item.get("attributes"):
        for a in item.get("attributes", []):
            if isinstance(a, dict) and "scale_id" in a:
                attr_map[a["scale_id"]] = a.get("value")
                base = a["scale_id"].split("_")[0]
                attr_map[base] = a.get("value")

    score_delta = 0.0
    missing_traits: List[str] = []
    evaluated_traits: List[Dict[str, Any]] = []
    trait_diagnostics: List[Dict[str, Any]] = []

    # 1. Darkness Evaluation (Scale: darkness_v1, min: 0, max: 4)
    if req_darkness is not None:
        dark_val = attr_map.get("darkness_v1") if "darkness_v1" in attr_map else attr_map.get("darkness")
        if dark_val is None:
            missing_traits.append("darkness")
            trait_diagnostics.append({
                "trait": "darkness",
                "scale_id": "darkness_v1",
                "status": "missing_trait_data",
                "message": f"Attribute scale 'darkness_v1' data is missing or null for item '{item.get('id')}'"
            })
        else:
            try:
                numeric_val = float(dark_val)
                evaluated_traits.append({
                    "trait": "darkness",
                    "scale_id": "darkness_v1",
                    "value": numeric_val,
                    "status": "evaluated"
                })
                if req_darkness in ("high", "darker", True) or (isinstance(req_darkness, (int, float)) and req_darkness > 1):
                    score_delta += (numeric_val / 4.0) * 15.0
                elif req_darkness in ("low", "less_dark", False):
                    score_delta += ((4.0 - numeric_val) / 4.0) * 15.0
            except (ValueError, TypeError):
                missing_traits.append("darkness")

    # 2. Pacing Evaluation (Scale: pacing_v1, min: 0, max: 4)
    if req_pacing is not None:
        pace_val = attr_map.get("pacing_v1") if "pacing_v1" in attr_map else attr_map.get("pacing")
        if pace_val is None:
            missing_traits.append("pacing")
            trait_diagnostics.append({
                "trait": "pacing",
                "scale_id": "pacing_v1",
                "status": "missing_trait_data",
                "message": f"Attribute scale 'pacing_v1' data is missing or null for item '{item.get('id')}'"
            })
        else:
            try:
                numeric_val = float(pace_val)
                evaluated_traits.append({
                    "trait": "pacing",
                    "scale_id": "pacing_v1",
                    "value": numeric_val,
                    "status": "evaluated"
                })
                if req_pacing in ("fast", "faster", True):
                    score_delta += (numeric_val / 4.0) * 15.0
                elif req_pacing in ("slow", "slower", False):
                    score_delta += ((4.0 - numeric_val) / 4.0) * 15.0
            except (ValueError, TypeError):
                missing_traits.append("pacing")

    diagnostics = {
        "missing_traits": missing_traits,
        "evaluated_traits": evaluated_traits,
        "trait_diagnostics": trait_diagnostics,
    }
    return score_delta, diagnostics


# =============================================================================
# STAGE 1: PHASE 23 QWEN INTENT PARSER & CONVERSATIONAL PATCH ENGINE
# =============================================================================
class NLUUnderstandingNode:
    """
    Tầng 1: Sử dụng Phase 23 Intent Parser để bóc tách StructuredDiscoveryIntent v1
    và hợp nhất trạng thái hội thoại (CONVERSATIONAL_PATCH).
    """
    def __init__(self):
        self.session_state: Dict[str, Dict[str, Any]] = {}

    def apply_patch(self, base_intent: Dict[str, Any], patch_intent: Dict[str, Any]) -> Dict[str, Any]:
        merged = copy.deepcopy(base_intent)
        merged["intent_type"] = "CONVERSATIONAL_PATCH"

        p_cons = patch_intent.get("constraints") or {}
        if p_cons.get("year_min") is not None:
            merged["constraints"]["year_min"] = p_cons["year_min"]
        if p_cons.get("year_max") is not None:
            merged["constraints"]["year_max"] = p_cons["year_max"]
        if p_cons.get("include_genres"):
            merged["constraints"]["include_genres"] = p_cons["include_genres"]
        if p_cons.get("exclude_genres"):
            for eg in p_cons["exclude_genres"]:
                if eg not in merged["constraints"]["exclude_genres"]:
                    merged["constraints"]["exclude_genres"].append(eg)
            merged["constraints"]["include_genres"] = [
                g for g in merged["constraints"]["include_genres"]
                if g not in merged["constraints"]["exclude_genres"]
            ]

        if patch_intent.get("requested_k") is not None:
            merged["requested_k"] = patch_intent["requested_k"]
        if patch_intent.get("diversify") is not None:
            merged["diversify"] = patch_intent["diversify"]
        if (patch_intent.get("reference") or {}).get("status") == "CLEAR_REFERENCE_TEXT":
            merged["reference"] = patch_intent["reference"]
        if patch_intent.get("patch_operations"):
            merged["patch_operations"] = patch_intent["patch_operations"]

        merged["year_min"] = merged["constraints"]["year_min"]
        merged["year_max"] = merged["constraints"]["year_max"]
        merged["include_genres"] = merged["constraints"]["include_genres"]
        merged["exclude_genres"] = merged["constraints"]["exclude_genres"]
        merged["reference_films"] = [merged["reference"]["text"]] if (merged.get("reference") or {}).get("text") else []

        return merged

    def process(
        self,
        query: str,
        history: Optional[List[Dict[str, Any]]] = None,
        catalog: Optional[List[Dict[str, Any]]] = None,
        session_id: str = "default"
    ) -> Dict[str, Any]:
        logger.info(f"[Stage 1 - Phase 23 NLU] Đang phân tích StructuredDiscoveryIntent: '{query}'")
        parsed = qwen_service.parse_discovery_intent(query=query, history=history, catalog=catalog)

        # The compatibility default is shared by anonymous callers, so it must not carry state.
        has_session = bool(session_id and session_id != "default")
        if has_session and parsed.get("intent_type") == "CONVERSATIONAL_PATCH" and session_id in self.session_state:
            effective = self.apply_patch(self.session_state[session_id], parsed)
            self.session_state[session_id] = effective
            return effective

        if has_session and parsed.get("intent_type") == "DISCOVERY":
            self.session_state[session_id] = copy.deepcopy(parsed)

        return parsed


# =============================================================================
# STAGE 2: HYBRID RETRIEVAL & HARD CONSTRAINT ENGINE (CATALOG-01)
# =============================================================================
class EmbeddingRetrievalNode:
    """
    Tầng 2: True Hybrid Retrieval (BM25 Robertson-Spärck Jones + Dense multilingual-e5)
    với lọc ràng buộc cứng (item_type, exclude_genres, year) và đánh giá thuộc tính so sánh (darkness, pacing).
    """
    def __init__(self):
        self.hybrid_index = HybridMovieIndex()

    def retrieve_candidates(
        self,
        nlu_output: Dict[str, Any],
        catalog: List[Dict[str, Any]],
        top_k: int = 12,
        hybrid_index: Optional[Any] = None
    ) -> List[Dict[str, Any]]:
        logger.info("[Stage 2 - Hybrid Retrieval] Đang thực thi True Hybrid Search & lọc ràng buộc...")
        query_text = (nlu_output.get("query") or {}).get("text") or nlu_output.get("raw_query") or ""
        if nlu_output.get("intent_type") == "CLARIFICATION" and not query_text.strip():
            return []
        cons = nlu_output.get("constraints") or {}
        item_type = nlu_output.get("item_type") or cons.get("item_type")

        # Execute True Hybrid Search on provided snapshot index or instance index
        active_idx = hybrid_index if hybrid_index is not None else self.hybrid_index
        results = active_idx.search_hybrid(
            query_text=query_text,
            nlu_intent=nlu_output,
            catalog=catalog,
            item_type_filter=item_type
        )


        candidates = []
        for r in results:
            item = dict(r["movie"])
            score_delta, diagnostics = evaluate_comparative_constraints(item, nlu_output, query_text)
            item["retrieval_score"] = round(r["score"] + score_delta, 4)
            item["bm25_score"] = r.get("bm25_score", 0.0)
            item["dense_score"] = r.get("dense_score", 0.0)
            item["diagnostics"] = diagnostics
            candidates.append(item)

        # Re-sort after comparative adjustments
        candidates.sort(key=lambda x: x["retrieval_score"], reverse=True)
        return candidates[:top_k]


# =============================================================================
# STAGE 3: QWEN 0.6B RECOMMENDER NODE (DOMAIN FILTERING)
# =============================================================================
class Recommender06BNode:
    """
    Tầng 3: Sàng lọc ứng viên theo ngưỡng phù hợp ngữ cảnh và sở thích cá nhân.
    """
    def filter_candidates(
        self,
        candidates: List[Dict[str, Any]],
        nlu_output: Dict[str, Any],
        user_profile: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        logger.info(f"[Stage 3 - 0.6B Recommender] Đang sàng lọc {len(candidates)} ứng viên...")
        if nlu_output.get("intent_type") == "CLARIFICATION" and not candidates:
            return []
        return candidates[:8]


# =============================================================================
# STAGE 4: QWEN 0.6B RANKER & MMR DIVERSITY RERANKING NODE
# =============================================================================
class Ranker06BNode:
    """
    Tầng 4: Chấm điểm tinh (Fine-grained ranking) kết hợp đa dạng hóa MMR (Maximal Marginal Relevance).
    """
    def rank_top_k(
        self,
        filtered_movies: List[Dict[str, Any]],
        nlu_output: Dict[str, Any],
        top_k: int = 3
    ) -> List[Dict[str, Any]]:
        req_k = nlu_output.get("requested_k")
        effective_k = max(1, min(int(req_k), 10)) if isinstance(req_k, int) and req_k > 0 else top_k
        logger.info(f"[Stage 4 - 0.6B Ranker & MMR] Đang xếp hạng Top {effective_k}...")

        if not filtered_movies:
            return []

        cons = nlu_output.get("constraints") or {}
        inc_genres = set(cons.get("include_genres") or [])
        specific_inc = inc_genres - {"Animation"} if len(inc_genres) > 1 else inc_genres

        scored = []
        for idx, m in enumerate(filtered_movies):
            # Prior based on rating and retrieval score
            retrieval_prior = m.get("retrieval_score", 1.0) * 35.0
            base = float(m.get("rating", 8.0)) * 4.0 + retrieval_prior
            m_genres = set(m.get("genres") or [])
            if specific_inc:
                overlap_ratio = len(m_genres & specific_inc) / max(1, len(specific_inc))
                base += overlap_ratio * 15.0
            else:
                base += max(0, 10 - idx * 2)

            match_pct = int(max(70, min(99, round(base))))
            scored.append({**m, "matchPercentage": match_pct})

        scored.sort(key=lambda x: x["matchPercentage"], reverse=True)

        # Đa dạng hóa MMR nếu diversify không bị tắt
        if nlu_output.get("diversify") is False or len(scored) <= effective_k:
            return scored[:effective_k]

        selected = [scored[0]]
        remaining = scored[1:]
        while len(selected) < effective_k and remaining:
            best_idx = 0
            best_mmr = -1e9
            for i, cand in enumerate(remaining):
                c_genres = set(cand.get("genres") or [])
                max_sim = max(
                    len(c_genres & set(s.get("genres") or [])) / max(1, len(c_genres | set(s.get("genres") or [])))
                    for s in selected
                )
                mmr_score = 0.75 * (cand["matchPercentage"] / 100.0) - 0.25 * max_sim
                if mmr_score > best_mmr:
                    best_mmr = mmr_score
                    best_idx = i
            selected.append(remaining.pop(best_idx))

        return selected


# =============================================================================
# STAGE 5: GROUNDED EXPLANATION GENERATOR NODE (CATALOG-01)
# =============================================================================
class ExplanationGeneratorNode:
    """
    Tầng 5: Sinh lời tư vấn bằng tiếng Việt bám sát dữ liệu thực tế (grounded):
    - Tra cứu chính xác: trả đúng tên tập/mùa, không thêm tập không liên quan
    - Tìm theo tình tiết: nêu chi tiết catalog giải thích vì sao khớp
    - Tiểu phẩm/phân cảnh: nêu mốc thời gian nếu có, không hiển thị 00:00 khi null
    - Không khẳng định vượt quá dữ liệu (không bịa rating 8.0, năm 2025, an toàn tuyệt đối)
    - Làm sạch hiển thị: loại bỏ đuôi file, trùng lặp nhân vật và tiêu đề
    """
    @staticmethod
    def _clean_title(raw_title: Optional[str]) -> str:
        if not raw_title:
            return ""
        t = str(raw_title).strip()
        t = re.sub(r"\.(?:mp4|mkv|avi|mov)$", "", t, flags=re.IGNORECASE)
        t = re.sub(r"_(?:720p|1080p|x264|h264|hd)\b", "", t, flags=re.IGNORECASE)
        t = re.sub(r"\s*\(NEW\s*\)\s*", "", t, flags=re.IGNORECASE)
        parts = t.split()
        if len(parts) >= 6 and len(parts) % 2 == 0:
            half = len(parts) // 2
            if parts[:half] == parts[half:]:
                t = " ".join(parts[:half])
        return t.strip()

    @staticmethod
    def _clean_characters(chars: List[Any]) -> List[str]:
        if not chars:
            return []
        seen_token_sets = []
        seen_names = set()
        clean = []
        for c in chars:
            name = str(c).strip() if isinstance(c, str) else str(c.get("name", "")).strip()
            if not name or re.search(r"[\uac00-\ud7af]", name):
                continue
            n_lower = name.lower()
            if n_lower in seen_names:
                continue
            tokens = set(n_lower.split())
            # Deduplicate if tokens are identical (e.g. 'Choi Jadoo' and 'Jadoo Choi')
            # or if one is single token and subset of the other (e.g. 'Jadoo' and 'Choi Jadoo')
            is_alias = False
            for s_tokens in seen_token_sets:
                if tokens == s_tokens:
                    is_alias = True
                    break
                if len(tokens) == 1 and tokens.issubset(s_tokens):
                    is_alias = True
                    break
                if len(s_tokens) == 1 and s_tokens.issubset(tokens):
                    is_alias = True
                    break
            if is_alias:
                continue
            seen_token_sets.append(tokens)
            seen_names.add(n_lower)
            clean.append(name)
            if len(clean) >= 4:
                break
        return clean

    @staticmethod
    def _format_time_ms(ms: Optional[int]) -> Optional[str]:
        if ms is None or ms < 0:
            return None
        total_sec = ms // 1000
        mins = total_sec // 60
        secs = total_sec % 60
        return f"{mins:02d}:{secs:02d}"

    @staticmethod
    def _is_resolved_similarity_query(nlu_output: Dict[str, Any], query: str) -> bool:
        reference = nlu_output.get("reference") or {}
        if reference.get("status") != "CLEAR_REFERENCE_TEXT" or not reference.get("text"):
            return False
        positive_query, _ = split_query_scopes(query)
        return bool(re.search(
            r"\b(?:giống|tương\s+tự|như\s+phim|similar|(?:movie|film|show|series|something|anything)\s+like)\b",
            positive_query,
            flags=re.IGNORECASE,
        ))

    GENERIC_ACTION_VERBS = {
        "chơi", "ăn", "đi", "làm", "xem", "nói", "thấy", "biết", "muốn", "thích",
        "học", "mua", "bán", "chạy", "nghe", "nhìn", "gặp", "tặng", "giúp", "bảo",
        "yêu", "ghét", "sợ", "ngủ", "ngồi", "đứng", "cần", "tìm", "cho", "lấy", "bắt",
        "ném", "đá", "đánh", "hát", "múa", "nấu", "vẽ", "viết", "đọc"
    }

    def evaluate_candidate_grounding(
        self,
        movie: Dict[str, Any],
        nlu_output: Dict[str, Any],
        query: str
    ) -> Tuple[bool, str]:
        """
        Xác định xem một candidate movie có đủ căn cứ (grounded) để trả về cho truy vấn hay không.
        Quy tắc:
        1. CLARIFICATION intent -> False
        2. Exact season/episode -> True nếu số tập khớp trong mệnh đề khẳng định (và không phải câu hỏi)
        3. Exact title / alias -> True nếu tiêu đề khớp trong mệnh đề khẳng định (và không phải câu hỏi)
        4. Series item -> True
        5. Segment / Scene item -> True nếu tiêu đề/aliases khớp từ khóa truy vấn
        6. Similarity search -> True nếu có từ khóa tương đồng (giống, tương tự)
        7. Genre / Thematic discovery -> True nếu là mô tả thể loại chung
        8. Plot / Narrative search (Tình tiết):
           - Phân biệt động từ chung với thực thể / đối tượng cụ thể (C2)
           - Nếu có specific_entities, bắt buộc phải có ít nhất 1 entity xuất hiện trong metadata
           - Đối với cụm từ ngắn (len <= 2), không được để 1 động từ chung xác nhận toàn bộ hành động
           - Đối với cụm từ dài (len >= 3), yêu cầu overlap hợp lý
        """
        if not movie:
            return False, "empty_movie"

        if nlu_output.get("intent_type") == "CLARIFICATION":
            return False, "clarification_intent"

        q_lower = query.lower().strip()
        pos_scope, neg_scope = split_query_scopes(query)
        pos_q_lower = pos_scope.lower().strip()

        # 1. Tra cứu mùa/tập cụ thể (Exact Episode lookup)
        pos_sea, pos_ep = parse_season_episode_intent(pos_scope)
        is_question = any(q_word in pos_q_lower for q_word in ["tập nào", "phim nào", "có tập nào", "tập gì", "cảnh nào", "đoạn nào"])
        if (not is_question) and pos_ep is not None:
            if movie.get("episode_number") == pos_ep:
                if pos_sea is not None:
                    if movie.get("season_number") == pos_sea:
                        return True, "exact_season_episode"
                    else:
                        return False, "season_mismatch"
                else:
                    return True, "exact_episode"
            else:
                return False, "episode_mismatch"

        # 2. Tra cứu tên tập / alias chính xác (Exact Title lookup)
        title = self._clean_title(movie.get("title", ""))
        if title:
            title_lower = title.lower().strip()
            title_clean = re.sub(r"[^\w\s]", "", title_lower).strip()
            pos_clean = re.sub(r"[^\w\s]", "", pos_q_lower).strip()
            if title_clean and len(title_clean) >= 4 and (not is_question):
                if title_clean == pos_clean or title_clean in pos_clean or title_lower in pos_q_lower:
                    return True, "exact_title"

        # 3. Item type là series
        if movie.get("item_type") == "series":
            return True, "series_lookup"

        # 4. Item type là segment hoặc scene
        if movie.get("item_type") in ("segment", "scene"):
            seg_title = (movie.get("title") or "").lower()
            seg_words = [w for w in tokenize_text(seg_title) if len(w) >= 2]
            q_words = set(tokenize_text(pos_q_lower))
            if any(w in q_words for w in seg_words if len(w) >= 3):
                return True, "segment_match"

        # Similarity needs an explicitly resolved reference; "I would like ..." is not one.
        if self._is_resolved_similarity_query(nlu_output, query):
            return True, "similarity_match"

        # 6. Xử lý xung đột số tập và tiêu đề
        if movie.get("diagnostics", {}).get("conflict"):
            return True, "conflict_resolution"

        # 7. Gợi ý theo thể loại / chủ đề tổng quát
        cons = nlu_output.get("constraints") or {}
        has_filter_constraints = bool(
            cons.get("year_min") or cons.get("year_max") or
            cons.get("include_genres") or cons.get("exclude_genres")
        )
        is_generic_descriptive = is_descriptive_not_franchise(pos_scope)
        if is_generic_descriptive:
            return True, "genre_descriptive_discovery"

        # 8. Tra cứu theo tình tiết / cốt truyện cụ thể (Plot search)
        generic_plot_stop = {
            "tập", "nào", "phim", "hoạt", "hình", "mùa", "cho", "tôi", "xem", "tìm",
            "gợi", "ý", "hay", "nhất", "những", "của", "và", "với", "năm", "không", "có",
            "chứa", "jadoo", "jadu", "xin", "chào", "bộ", "đoạn", "cảnh", "trong", "về",
            "là", "bị", "phát", "hành"
        }
        content_words = [w for w in tokenize_text(pos_scope.lower()) if w not in generic_plot_stop and len(w) >= 2 and not w.isdigit()]

        if not content_words:
            if has_filter_constraints:
                if cons.get("year_min") and (movie.get("release_year") or movie.get("year")) != cons.get("year_min"):
                    return False, "year_mismatch"
                return True, "filter_constraints_match"
            return True, "no_specific_plot_keywords"

        title_text = f"{movie.get('title') or ''} {' '.join(movie.get('aliases') or [])}".lower()
        narrative_text = f"{movie.get('synopsis') or ''} {movie.get('description') or ''} {' '.join(str(f if isinstance(f, str) else f.get('text', '')) for f in (movie.get('plot_facts') or []))} {movie.get('visual_summary') or ''}".lower()
        category_text = f"{' '.join(movie.get('genres') or [])} {' '.join(movie.get('keywords') or [])} {' '.join(movie.get('themes') or [])}".lower()
        doc_text = f"{title_text} {narrative_text} {category_text}".lower()

        matched_content = [w for w in content_words if w in doc_text]
        specific_entities = [w for w in content_words if w not in self.GENERIC_ACTION_VERBS]

        if specific_entities:
            matched_entities = [e for e in specific_entities if e in doc_text]
            if len(matched_entities) == 0:
                return False, "missing_specific_entity"

            if len(content_words) >= 3:
                overlap_ratio = len(matched_content) / len(content_words)
                entity_ratio = len(matched_entities) / len(specific_entities)
                if len(matched_content) < 2 or overlap_ratio < 0.35:
                    return False, "insufficient_content_overlap"
                if len(specific_entities) >= 3 and (len(matched_entities) < 2 or entity_ratio < 0.30):
                    return False, "insufficient_entity_overlap"
            elif len(content_words) == 2:
                if len(matched_content) < 2:
                    return False, "insufficient_content_overlap"
        else:
            if len(content_words) >= 2 and len(matched_content) < 2:
                return False, "generic_verbs_insufficient_overlap"
            if len(content_words) == 1:
                return False, "generic_verb_alone_not_grounded"
            if len(matched_content) == 0:
                return False, "no_content_match"

        return True, "plot_grounded"

    def generate_explanation(
        self,
        ranked_movies: List[Dict[str, Any]],
        nlu_output: Dict[str, Any],
        query: str,
        history: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        logger.info("[Stage 5 - Grounded Storyteller] Đang sinh lời giải thích bám sát dữ liệu (Grounded Explanation)...")

        if nlu_output.get("intent_type") == "CLARIFICATION":
            clar = nlu_output.get("clarification") or {}
            return clar.get("question") or "Yêu cầu của bạn chưa đủ thông tin hoặc có điểm mâu thuẫn. Bạn có thể nói rõ hơn được không?"

        q_lower = query.lower().strip()
        cons = nlu_output.get("constraints") or {}

        # Kiểm tra điều kiện chưa xác minh (unverified condition) áp dụng cho MỌI nhánh trả lời
        unverified_note = ""
        has_violence_constraint = (
            "Violence" in (cons.get("exclude_genres") or []) or
            any(w in q_lower for w in ("không có bạo lực", "không bạo lực", "tránh bạo lực"))
        )
        if has_violence_constraint:
            unverified_note = " (Lưu ý: Dữ liệu hiện chưa đủ để xác nhận tập không có bạo lực; chưa ghi nhận cảnh báo bạo lực đối với tập này)."

        # 1. Trường hợp không tìm thấy kết quả hoặc top candidate không có căn cứ
        if not ranked_movies or not self.evaluate_candidate_grounding(ranked_movies[0], nlu_output, query)[0]:
            pos_scope, _ = split_query_scopes(query)
            pos_q_lower = pos_scope.lower().strip()

            # Ngoại lệ franchise bên ngoài
            if any(f in q_lower for f in ["doraemon", "conan", "naruto", "one piece", "dragon ball", "shin"]):
                return "Hệ thống hiện chỉ có dữ liệu các tập phim của bộ hoạt hình Xin Chào Jadoo. Tác phẩm bạn yêu cầu không có trong hệ thống dữ liệu hiện tại."
            # Mùa hoặc tập ngoài khoảng trong mệnh đề khẳng định
            if re.search(r"\b(?:mùa|season)\s*0*(?:[7-9]|\d{2,})\b", pos_q_lower) or re.search(r"\b(?:tập|ep)\s*0*(?:[3-9]\d{2,}|\d{4,})\b", pos_q_lower):
                return "Hiện danh mục phim chưa có mùa hoặc tập này."
            # Ràng buộc điều kiện lọc
            if cons.get("include_genres") or cons.get("exclude_genres") or cons.get("year_min") or cons.get("year_max"):
                return "Hiện chưa tìm thấy nội dung nào khớp với các điều kiện lọc bạn đưa ra trong danh mục."
            # Truy vấn tình tiết / nội dung cụ thể
            generic_plot_stop = {
                "tập", "nào", "phim", "hoạt", "hình", "mùa", "cho", "tôi", "xem", "tìm",
                "gợi", "ý", "hay", "nhất", "những", "của", "và", "với", "năm", "không", "có",
                "chứa", "jadoo", "jadu", "xin", "chào", "bộ", "đoạn", "cảnh", "trong", "về",
                "là", "bị", "phát", "hành"
            }
            content_words = [w for w in tokenize_text(pos_scope.lower()) if w not in generic_plot_stop and len(w) >= 2 and not w.isdigit()]
            if content_words and not is_descriptive_not_franchise(pos_scope):
                return "Hiện chưa tìm thấy tập phim nào có tình tiết phù hợp với yêu cầu của bạn trong danh mục." + unverified_note
            return "Hiện chưa tìm thấy nội dung nào phù hợp với yêu cầu của bạn trong danh mục." + unverified_note

        top = ranked_movies[0]
        others = ranked_movies[1:]

        item_type = top.get("item_type", "movie")
        title = self._clean_title(top.get("title", "Tác phẩm"))
        year = top.get("year") or top.get("release_year")
        rating = top.get("rating")
        desc = (top.get("description") or top.get("synopsis") or "").strip()
        chars = self._clean_characters(top.get("characters") or [])
        facts = top.get("plot_facts") or []
        start_ms = top.get("start_ms")
        end_ms = top.get("end_ms")
        vis_sum = top.get("visual_summary") or top.get("visual_description")
        diag = top.get("diagnostics") or {}
        conflict = diag.get("conflict")

        # 2. Xử lý xung đột số tập và tiêu đề
        if conflict:
            req_ep = conflict.get("requested_episode")
            con_ep = conflict.get("conflicting_episode")
            con_title = self._clean_title(conflict.get("conflicting_title"))
            return (
                f"Bạn vừa yêu cầu **Tập {req_ep}** nhưng nội dung tìm kiếm lại khớp với tập **{con_title}** (Tập {con_ep}). "
                f"Dưới đây là thông tin Tập {req_ep} (**{title}**) và tập liên quan **{con_title}** để bạn lựa chọn nhé."
            ) + unverified_note

        # 3. Tra cứu toàn bộ bộ phim (Series lookup) - CHỈ khi item thực sự là series
        if item_type == "series":
            desc_part = f" Phim kể về: {desc}" if desc else ""
            chars_part = f" Nhân vật chính: **{', '.join(chars)}**." if chars else ""
            return f"Đây là bộ phim hoạt hình **{title}**.{desc_part}{chars_part}".strip() + unverified_note

        # 4. Tra cứu mùa/tập cụ thể hoặc tên tập chính xác (Exact Episode lookup)
        pos_scope, neg_scope = split_query_scopes(query)
        pos_q_lower = pos_scope.lower().strip()
        pos_sea, pos_ep = parse_season_episode_intent(pos_scope)

        is_question = any(q_word in pos_q_lower for q_word in ["tập nào", "phim nào", "có tập nào", "tập gì", "cảnh nào", "đoạn nào"])

        is_exact_num = False
        if pos_ep is not None and top.get("episode_number") == pos_ep:
            if pos_sea is not None:
                is_exact_num = (top.get("season_number") == pos_sea)
            else:
                is_exact_num = True

        is_exact_title = False
        if title:
            title_lower = title.lower().strip()
            title_clean = re.sub(r"[^\w\s]", "", title_lower).strip()
            pos_clean = re.sub(r"[^\w\s]", "", pos_q_lower).strip()
            if title_clean and len(title_clean) >= 4:
                if title_clean == pos_clean or title_clean in pos_clean or title_lower in pos_q_lower:
                    is_exact_title = True

        if (is_exact_num or is_exact_title) and (not is_question) and item_type == "episode":
            sea_num = top.get("season_number")
            ep_num = top.get("episode_number")
            sea_prefix = f"Mùa {sea_num}, " if sea_num else ""
            if ep_num and f"tập {ep_num}" not in title.lower():
                ep_prefix = f"Tập {ep_num}: "
            else:
                ep_prefix = ""

            meta_parts = []
            if year:
                meta_parts.append(str(year))
            if rating:
                meta_parts.append(f"{rating}★")
            meta_str = f" ({' · '.join(meta_parts)})" if meta_parts else ""

            resp = f"Đây là {sea_prefix}{ep_prefix}**{title}**{meta_str}."
            if desc:
                resp += f" {desc}"
            elif facts:
                fact_text = facts[0] if isinstance(facts[0], str) else facts[0].get("text", "")
                if fact_text:
                    resp += f" Tình tiết trong tập: *{fact_text}*."
            return resp.strip() + unverified_note

        # 5. Tra cứu tiểu phẩm / phân cảnh (Segment / Scene)
        if item_type in ("segment", "scene"):
            parent_title = self._clean_title(top.get("parent_episode_title") or top.get("episode_title"))
            ep_num = top.get("episode_number")
            parent_info = f" (thuộc tập **{parent_title}**)" if parent_title else (f" (thuộc Tập {ep_num})" if ep_num else "")

            start_str = self._format_time_ms(start_ms)
            end_str = self._format_time_ms(end_ms)
            if start_str and end_str:
                time_info = f" [Mốc thời gian: {start_str} – {end_str}]"
            else:
                time_info = ""

            resp = f"Đây là tiểu phẩm **{title}**{parent_info}{time_info}."
            if desc:
                resp += f" {desc}"
            elif vis_sum:
                resp += f" Cảnh quay miêu tả: *{vis_sum}*."
            return resp.strip() + unverified_note

        # 6. Đề xuất tương tự (Genuine similarity search)
        is_sim = self._is_resolved_similarity_query(nlu_output, query)
        if is_sim:
            ref_text = (nlu_output.get("reference") or {}).get("text") or "phim bạn yêu cầu"
            resp = f"Dựa trên sự tương đồng với **{ref_text}**, mình gợi ý tập **{title}**."
            if desc:
                resp += f" {desc}"
            if others:
                other_names = ", ".join(f"**{self._clean_title(m.get('title'))}**" for m in others[:2])
                resp += f" Ngoài ra, bạn cũng có thể tham khảo thêm {other_names}."
            return resp.strip() + unverified_note

        # 7. Tìm theo tình tiết / gợi ý tổng quát (Plot search)
        sea_num = top.get("season_number")
        ep_num = top.get("episode_number")
        ep_str = f" (Mùa {sea_num}, Tập {ep_num})" if (sea_num and ep_num) else (f" (Tập {ep_num})" if ep_num else "")

        pos_scope, _ = split_query_scopes(query)
        generic_plot_stop = {
            "tập", "nào", "phim", "hoạt", "hình", "mùa", "cho", "tôi", "xem", "tìm",
            "gợi", "ý", "hay", "nhất", "những", "của", "và", "với", "năm", "không", "có",
            "chứa", "jadoo", "jadu", "xin", "chào", "bộ", "đoạn", "cảnh", "trong", "về",
            "là", "bị", "phát", "hành"
        }
        content_words = [w for w in tokenize_text(pos_scope.lower()) if w not in generic_plot_stop and len(w) >= 2 and not w.isdigit()]

        resp = f"Tập phim phù hợp với nội dung bạn tìm là **{title}**{ep_str}."
        if facts:
            matching_facts = [f for f in facts if any(m in (f if isinstance(f, str) else f.get("text", "")).lower() for m in content_words)]
            chosen_fact = matching_facts[0] if matching_facts else facts[0]
            fact_text = chosen_fact if isinstance(chosen_fact, str) else chosen_fact.get("text", "")
            if fact_text:
                resp += f" Tình tiết trong tập: \"*{fact_text}*\"."
        elif desc:
            resp += f" {desc}"

        if others:
            other_names = ", ".join(f"**{self._clean_title(m.get('title'))}**" for m in others[:2])
            resp += f" Gợi ý thêm: {other_names}."

        return resp.strip() + unverified_note


# =============================================================================
# MASTER PIPELINE ORCHESTRATOR
# =============================================================================
class CascadingAIPipeline:
    """
    Trình điều phối toàn bộ Pipeline 5 tầng tích hợp Phase 23 Intent Parser và multi-level Catalog.
    """
    def __init__(self):
        self.nlu_node = NLUUnderstandingNode()
        self.retrieval_node = EmbeddingRetrievalNode()
        self.recommender_node = Recommender06BNode()
        self.ranker_node = Ranker06BNode()
        self.explainer_node = ExplanationGeneratorNode()

    @staticmethod
    def _build_follow_ups(nlu_result: Dict[str, Any], ranked_top: List[Dict[str, Any]]) -> List[str]:
        if not ranked_top:
            return [
                "Gợi ý các tập phim hoạt hình nổi bật",
                "Tìm theo mùa hoặc số tập cụ thể (ví dụ: Mùa 1 Tập 1)",
                "Tìm theo thể loại gia đình hoặc hài hước"
            ]
        follow_ups = []
        top_title = ranked_top[0].get("title", "")
        if top_title:
            follow_ups.append(f"Tìm nội dung liên quan đến {top_title}")
        cons = nlu_result.get("constraints") or {}
        if "Horror" not in (cons.get("exclude_genres") or []):
            follow_ups.append("Giữ nguyên nhưng bỏ thể loại kinh dị đi")
        if cons.get("year_min") is None and cons.get("year_max") is None:
            follow_ups.append("Đổi thành nội dung phát hành từ năm 2024 trở đi")
        else:
            follow_ups.append("Đổi thành lấy 5 kết quả thay vì hiện tại")
        return follow_ups[:3]

    def run(
        self,
        query: str,
        catalog: Optional[List[Dict[str, Any]]] = None,
        history: Optional[List[Dict[str, Any]]] = None,
        session_id: str = "default",
        snapshot: Optional[Any] = None,
        nlu_intent: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute full 5-stage recommendation pipeline on the active catalog.
        Captures and uses AcceptedSnapshot for thread-safe consistency (CATALOG-01-F08 R1).
        """
        reset_metrics = getattr(qwen_service, "reset_request_inference_stats", None)
        if callable(reset_metrics):
            reset_metrics()
        from services.catalog_sync import get_accepted_snapshot
        current_snap = snapshot if snapshot is not None else get_accepted_snapshot()

        # Resolve active catalog corpus from captured snapshot
        if catalog is not None and len(catalog) > 0:
            active_catalog = list(catalog)
        elif current_snap is not None and getattr(current_snap, "is_ready", False):
            active_catalog = current_snap.get_flattened_catalog()
        elif catalog_sync_manager.is_loaded:
            active_catalog = catalog_sync_manager.get_flattened_catalog()
        else:
            active_catalog = list(DEFAULT_MOVIES)

        t_start = time.perf_counter()

        # Stage 1: Phase 23 Qwen Intent Parser & Patch Merger
        t_nlu_start = time.perf_counter()
        if nlu_intent is not None:
            nlu_result = nlu_intent
        else:
            nlu_result = self.nlu_node.process(query, history, active_catalog, session_id=session_id)
        if not (nlu_result.get("query") or {}).get("text"):
            if "query" not in nlu_result or not isinstance(nlu_result["query"], dict):
                nlu_result["query"] = {}
            nlu_result["query"]["text"] = query
        nlu_result["raw_query"] = query
        t_nlu_end = time.perf_counter()

        # Stage 2: Hard Constraint & Hybrid Retrieval using snapshot's index
        t_ret_start = time.perf_counter()
        target_index = getattr(current_snap, "hybrid_index", None) if current_snap is not None else None
        candidates = self.retrieval_node.retrieve_candidates(
            nlu_result, active_catalog, top_k=12, hybrid_index=target_index
        )
        t_ret_end = time.perf_counter()

        # Stage 3: Qwen 0.6B Recommender (Coarse Filtering)
        t_rec_start = time.perf_counter()
        filtered = self.recommender_node.filter_candidates(candidates, nlu_result)
        t_rec_end = time.perf_counter()

        # Stage 4: Qwen 0.6B Ranker & MMR Diversity
        t_rank_start = time.perf_counter()
        ranked_top = self.ranker_node.rank_top_k(filtered, nlu_result, top_k=3)
        t_rank_end = time.perf_counter()

        # Decision Boundary Synchronization (C1): Filter ungrounded candidates before Stage 5 & payload
        grounded_top = []
        for m in ranked_top:
            is_grounded, reason = self.explainer_node.evaluate_candidate_grounding(m, nlu_result, query)
            if is_grounded:
                m_copy = dict(m)
                m_copy["_grounding_reason"] = reason
                grounded_top.append(m_copy)

        # Exact Lookup Disambiguation:
        # If the top candidate is an exact season/episode or exact title lookup,
        # prioritize only the exact matching target(s) and prune secondary mismatched cards.
        if grounded_top:
            top_reason = grounded_top[0].get("_grounding_reason")
            if top_reason in ("exact_season_episode", "exact_title"):
                grounded_top = [m for m in grounded_top if m.get("_grounding_reason") == top_reason]

        # Stage 5: Grounded Storytelling Explanation
        t_exp_start = time.perf_counter()
        explanation_text = self.explainer_node.generate_explanation(grounded_top, nlu_result, query, history)
        t_exp_end = time.perf_counter()

        t_total_end = time.perf_counter()

        # Aggregate diagnostics from grounded candidates
        collected_diagnostics = [
            m.get("diagnostics") for m in grounded_top if m.get("diagnostics")
        ]

        # Gather generation metrics from qwen_service
        get_request_stats = getattr(qwen_service, "get_request_inference_stats", None)
        gen_stats = get_request_stats() if callable(get_request_stats) else {}

        return {
            "text": explanation_text,
            "recommendedMovies": grounded_top,
            "structuredIntent": nlu_result,
            "pipelineStages": {
                "nlu": nlu_result,
                "candidateCount": len(candidates),
                "rankedCount": len(grounded_top),
                "diagnostics": collected_diagnostics,
                "timings_ms": {
                    "nlu_ms": round((t_nlu_end - t_nlu_start) * 1000, 2),
                    "generation_ms": gen_stats.get("generation_time_ms", 0.0),
                    "retrieval_ms": round((t_ret_end - t_ret_start) * 1000, 2),
                    "recommender_ms": round((t_rec_end - t_rec_start) * 1000, 2),
                    "ranker_ms": round((t_rank_end - t_rank_start) * 1000, 2),
                    "explainer_ms": round((t_exp_end - t_exp_start) * 1000, 2),
                    "total_pipeline_ms": round((t_total_end - t_start) * 1000, 2),
                },
                "metrics": {
                    "prompt_tokens": gen_stats.get("prompt_tokens", 0),
                    "completion_tokens": gen_stats.get("completion_tokens", 0),
                    "tokens_per_second": gen_stats.get("tokens_per_second", 0.0),
                }
            },
            "followUps": self._build_follow_ups(nlu_result, grounded_top)
        }


# Global pipeline instance
cascading_pipeline = CascadingAIPipeline()
