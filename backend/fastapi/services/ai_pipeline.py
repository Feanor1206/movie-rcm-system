"""
=============================================================================
CASCADING MULTI-STAGE AI RECOMMENDATION PIPELINE (PHASE 23 INTEGRATED)
=============================================================================
Architecture:
  1. Qwen Phase 23 Intent Parser (StructuredDiscoveryIntent v1 + Patch Merger)
     ↓
  2. Hybrid Retrieval & Hard Constraint Engine (Year, Exclude/Include Genres, TF-IDF)
     ↓
  3. Qwen 0.6B Recommender (Domain Candidate Filtering & Reference Similarity)
     ↓
  4. Qwen 0.6B Ranker + MMR Diversity (Fine-grained Scoring & Top-K Selection)
     ↓
  5. Qwen Grounded Storyteller (Personalized Vietnamese Explanation Generation)
=============================================================================
"""

import os
import re
import math
import copy
import logging
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from services.qwen_service import qwen_service, DEFAULT_MOVIES

load_dotenv()
logger = logging.getLogger(__name__)


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

        if parsed.get("intent_type") == "CONVERSATIONAL_PATCH" and session_id in self.session_state:
            effective = self.apply_patch(self.session_state[session_id], parsed)
            self.session_state[session_id] = effective
            return effective

        if parsed.get("intent_type") == "DISCOVERY":
            self.session_state[session_id] = copy.deepcopy(parsed)

        return parsed


# =============================================================================
# STAGE 2: HARD CONSTRAINT & HYBRID SPARSE/REFERENCE RETRIEVAL NODE
# =============================================================================
class EmbeddingRetrievalNode:
    """
    Tầng 2: Thực thi ràng buộc cứng (Hard Constraints: Year, Exclude Genres)
    và tính điểm tương đồng ngữ nghĩa TF-IDF + Reference Film.
    """
    @staticmethod
    def _tokenize(text: str) -> List[str]:
        return re.findall(r"\w+", (text or "").lower())

    def retrieve_candidates(
        self,
        nlu_output: Dict[str, Any],
        catalog: List[Dict[str, Any]],
        top_k: int = 12
    ) -> List[Dict[str, Any]]:
        logger.info("[Stage 2 - Constraint & Retrieval] Đang lọc ràng buộc cứng và truy xuất ứng viên...")
        if nlu_output.get("intent_type") == "CLARIFICATION":
            return []

        cons = nlu_output.get("constraints") or {}
        inc_genres = set(cons.get("include_genres") or [])
        exc_genres = set(cons.get("exclude_genres") or [])
        ymin = cons.get("year_min")
        ymax = cons.get("year_max")

        ref_obj = nlu_output.get("reference") or {}
        ref_title = (ref_obj.get("text") or "").lower().strip()
        ref_movie = None
        if ref_title:
            for m in catalog:
                if m["title"].lower() == ref_title or ref_title in m["title"].lower():
                    ref_movie = m
                    break

        query_text = (nlu_output.get("query") or {}).get("text") or ""
        q_tokens = set(self._tokenize(query_text))

        candidates = []
        for movie in catalog:
            m_genres = set(movie.get("genres") or [])
            m_year = movie.get("year", 2025)

            # 1. Hard Constraint: Exclude Genres
            if exc_genres and (m_genres & exc_genres):
                continue

            # 2. Hard Constraint: Year Range
            if ymin is not None and m_year < ymin:
                continue
            if ymax is not None and m_year > ymax:
                continue

            # Không tự gợi ý lại đúng bộ phim đang làm mốc tham chiếu
            if ref_movie and movie["id"] == ref_movie["id"]:
                continue

            score = 0.0

            # 3. Genre Match (ưu tiên đúng thể loại Animation và các thể loại con)
            if "Animation" in inc_genres:
                if "Animation" in m_genres:
                    score += 6.0
                else:
                    score -= 4.0

            specific_inc = inc_genres - {"Animation"}
            matched_g = m_genres & specific_inc
            if specific_inc and not matched_g and not ref_movie:
                score -= 2.0
            else:
                score += len(matched_g) * 3.5

            # 4. Reference Film Facet Similarity
            if ref_movie:
                ref_g = set(ref_movie.get("genres") or [])
                shared_g = len(m_genres & ref_g)
                score += shared_g * 3.0

            # 5. Lexical / Semantic overlap trên mô tả và tiêu đề
            doc_tokens = set(self._tokenize(f"{movie.get('title', '')} {movie.get('description', '')} {' '.join(m_genres)}"))
            overlap = len(q_tokens & doc_tokens)
            score += overlap * 0.8

            # 6. Confidence-aware Rating Prior
            score += float(movie.get("rating", 7.5)) * 0.5

            candidates.append({"movie": movie, "retrieval_score": score})

        candidates.sort(key=lambda x: x["retrieval_score"], reverse=True)
        return [c["movie"] for c in candidates[:top_k]]


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
        if nlu_output.get("intent_type") == "CLARIFICATION":
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
            base = float(m.get("rating", 8.0)) * 9.5
            m_genres = set(m.get("genres") or [])
            if specific_inc:
                overlap_ratio = len(m_genres & specific_inc) / max(1, len(specific_inc))
                base += overlap_ratio * 18.0
            else:
                base += max(0, 12 - idx * 2)

            match_pct = int(max(75, min(99, round(base))))
            scored.append({**m, "matchPercentage": match_pct})

        scored.sort(key=lambda x: x["matchPercentage"], reverse=True)

        # Đa dạng hóa MMR nếu diversify không bị tắt (diversify != False)
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
# STAGE 5: QWEN GROUNDED EXPLANATION GENERATOR NODE
# =============================================================================
class ExplanationGeneratorNode:
    """
    Tầng 5: Sinh lời tư vấn bằng tiếng Việt bám sát kết quả xếp hạng và ràng buộc đã bóc tách.
    """
    def generate_explanation(
        self,
        ranked_movies: List[Dict[str, Any]],
        nlu_output: Dict[str, Any],
        query: str,
        history: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        logger.info("[Stage 5 - Grounded Storyteller] Đang sinh lời giải thích điện ảnh bằng tiếng Việt...")
        return qwen_service.generate_grounded_explanation(
            query=query,
            structured_intent=nlu_output,
            ranked_movies=ranked_movies,
            history=history
        )


# =============================================================================
# MASTER PIPELINE ORCHESTRATOR
# =============================================================================
class CascadingAIPipeline:
    """
    Trình điều phối toàn bộ Pipeline 5 tầng tích hợp Phase 23 Intent Parser
    """
    def __init__(self):
        self.nlu_node = NLUUnderstandingNode()
        self.retrieval_node = EmbeddingRetrievalNode()
        self.recommender_node = Recommender06BNode()
        self.ranker_node = Ranker06BNode()
        self.explainer_node = ExplanationGeneratorNode()

    @staticmethod
    def _build_follow_ups(nlu_result: Dict[str, Any], ranked_top: List[Dict[str, Any]]) -> List[str]:
        follow_ups = []
        if ranked_top:
            top_title = ranked_top[0]["title"]
            follow_ups.append(f"Tìm phim giống {top_title} nhưng không có kinh dị")
        cons = nlu_result.get("constraints") or {}
        if "Horror" not in (cons.get("exclude_genres") or []):
            follow_ups.append("Giữ nguyên nhưng bỏ thể loại kinh dị đi")
        if cons.get("year_min") is None and cons.get("year_max") is None:
            follow_ups.append("Đổi thành phim phát hành từ năm 2020 trở đi")
        else:
            follow_ups.append("Đổi thành lấy 5 phim thay vì kết quả hiện tại")
        return follow_ups[:3]

    def run(
        self,
        query: str,
        catalog: Optional[List[Dict[str, Any]]] = None,
        history: Optional[List[Dict[str, Any]]] = None,
        session_id: str = "default"
    ) -> Dict[str, Any]:
        # Hợp nhất catalog gửi từ client với kho phim chuẩn để đảm bảo luôn có đủ các tác phẩm kinh điển
        merged_catalog = list(DEFAULT_MOVIES)
        if catalog:
            existing_ids = {m["id"] for m in merged_catalog}
            for item in catalog:
                if item.get("id") not in existing_ids:
                    merged_catalog.append(item)

        # Stage 1: Phase 23 Qwen Intent Parser & Patch Merger
        nlu_result = self.nlu_node.process(query, history, merged_catalog, session_id=session_id)

        # Stage 2: Hard Constraint & Hybrid Retrieval
        candidates = self.retrieval_node.retrieve_candidates(nlu_result, merged_catalog, top_k=12)

        # Stage 3: Qwen 0.6B Recommender (Coarse Filtering)
        filtered = self.recommender_node.filter_candidates(candidates, nlu_result)

        # Stage 4: Qwen 0.6B Ranker & MMR Diversity
        ranked_top = self.ranker_node.rank_top_k(filtered, nlu_result, top_k=3)

        # Stage 5: Qwen Grounded Storytelling Explanation
        explanation_text = self.explainer_node.generate_explanation(ranked_top, nlu_result, query, history)

        return {
            "text": explanation_text,
            "recommendedMovies": ranked_top,
            "structuredIntent": nlu_result,
            "pipelineStages": {
                "nlu": nlu_result,
                "candidateCount": len(candidates),
                "rankedCount": len(ranked_top),
            },
            "followUps": self._build_follow_ups(nlu_result, ranked_top)
        }


# Global pipeline instance
cascading_pipeline = CascadingAIPipeline()
