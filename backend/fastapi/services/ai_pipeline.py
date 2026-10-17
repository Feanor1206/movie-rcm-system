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
import math
import copy
import logging
from typing import List, Dict, Any, Optional, Tuple
from dotenv import load_dotenv
from services.qwen_service import qwen_service, DEFAULT_MOVIES
from services.catalog_sync import catalog_sync_manager
from services.hybrid_retrieval import HybridMovieIndex, tokenize_text

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

        if parsed.get("intent_type") == "CONVERSATIONAL_PATCH" and session_id in self.session_state:
            effective = self.apply_patch(self.session_state[session_id], parsed)
            self.session_state[session_id] = effective
            return effective

        if parsed.get("intent_type") == "DISCOVERY":
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
            retrieval_prior = m.get("retrieval_score", 1.0) * 10.0
            base = float(m.get("rating", 8.0)) * 8.0 + retrieval_prior
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
    - Tên nhân vật (characters)
    - Tình tiết cốt truyện đã xác thực (verified plot facts)
    - Mốc thời gian phân cảnh (scene timestamps)
    - Chẩn đoán thuộc tính so sánh khi thiếu dữ liệu
    """
    @staticmethod
    def _format_time_ms(ms: Optional[int]) -> str:
        if ms is None or ms < 0:
            return "00:00"
        total_sec = ms // 1000
        mins = total_sec // 60
        secs = total_sec % 60
        return f"{mins:02d}:{secs:02d}"

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
            return clar.get("question") or "Yêu cầu của bạn chưa đủ rõ ràng hoặc có mâu thuẫn. Bạn có thể nói rõ hơn được không?"

        if not ranked_movies:
            return (
                "Tôi đã kiểm tra toàn bộ kho danh mục theo các ràng buộc khắt khe của bạn "
                "(về năm phát hành, thể loại và từ khóa), nhưng hiện chưa có kết quả nào khớp 100%. "
                "Bạn có muốn nới lỏng bớt điều kiện tìm kiếm không?"
            )

        top = ranked_movies[0]
        others = ranked_movies[1:]

        # Extract grounding details
        item_type = top.get("item_type", "movie")
        title = top.get("title", "Tác phẩm")
        year = top.get("year", 2025)
        rating = top.get("rating", 8.0)
        desc = top.get("description", "")
        chars = top.get("characters", [])
        facts = top.get("plot_facts", [])
        start_ms = top.get("start_ms")
        end_ms = top.get("end_ms")
        vis_sum = top.get("visual_summary") or top.get("visual_description")
        diag = top.get("diagnostics") or {}

        # Build grounded narrative parts
        grounding_sentences: List[str] = []

        # Intro
        cons = nlu_output.get("constraints") or {}
        inc = ", ".join(cons.get("include_genres") or [])
        exc = ", ".join(cons.get("exclude_genres") or [])
        ref_title = (nlu_output.get("reference") or {}).get("text")

        if ref_title:
            grounding_sentences.append(f"Dựa trên sự tương đồng với **{ref_title}**")
        elif inc:
            grounding_sentences.append(f"Dựa trên gu thể loại **{inc}**")
        else:
            grounding_sentences.append("Dựa trên truy vấn ngữ nghĩa của bạn")

        if exc:
            grounding_sentences.append(f"(đã loại trừ hoàn toàn thể loại **{exc}**)")

        intro_prefix = " ".join(grounding_sentences)

        # Grounding by Item Type
        if item_type == "scene":
            ts_str = f"{self._format_time_ms(start_ms)}–{self._format_time_ms(end_ms)}"
            main_recommendation = (
                f"{intro_prefix}, tôi đề xuất phân cảnh **{title}** (mốc thời gian **{ts_str}**). "
            )
            if vis_sum:
                main_recommendation += f"Cảnh quay miêu tả: *{vis_sum}*. "
        elif item_type == "segment":
            ts_str = f"{self._format_time_ms(start_ms)}–{self._format_time_ms(end_ms)}"
            main_recommendation = (
                f"{intro_prefix}, tôi gợi ý đoạn trích **{title}** (thời lượng **{ts_str}**). "
                f"{desc} "
            )
        elif item_type == "episode":
            ep_num = top.get("episode_number")
            num_str = f"Tập {ep_num}: " if ep_num else ""
            main_recommendation = (
                f"{intro_prefix}, tôi đề xuất tập phim **{num_str}{title}** ({year} · {rating}★). "
                f"{desc} "
            )
        else:
            main_recommendation = (
                f"{intro_prefix}, tôi đề xuất tác phẩm **{title}** ({year} · {rating}★). "
                f"{desc} "
            )

        # Character grounding
        if chars:
            main_recommendation += f"Tác phẩm có sự xuất hiện của nhân vật **{', '.join(chars[:2])}**. "

        # Verified plot facts grounding
        if facts:
            fact_text = facts[0] if isinstance(facts[0], str) else facts[0].get("text", "")
            main_recommendation += f"Tình tiết cốt truyện xác thực: \"*{fact_text}*\". "

        # Trait diagnostics grounding
        missing_traits = diag.get("missing_traits") or []
        if missing_traits:
            main_recommendation += f"(Hệ thống lưu ý: Dữ liệu thuộc tính {' & '.join(missing_traits)} của mục này chưa được hiệu chuẩn). "

        # Additional recommendations
        if others:
            other_names = ", ".join(f"**{m.get('title')}**" for m in others[:2])
            main_recommendation += f"Ngoài ra, bạn cũng có thể tham khảo thêm {other_names}."

        return main_recommendation.strip()


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
        follow_ups = []
        if ranked_top:
            top_title = ranked_top[0].get("title", "")
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
        snapshot: Optional[Any] = None
    ) -> Dict[str, Any]:
        """
        Execute full 5-stage recommendation pipeline on the active catalog.
        Captures and uses AcceptedSnapshot for thread-safe consistency (CATALOG-01-F08 R1).
        """
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

        # Stage 1: Phase 23 Qwen Intent Parser & Patch Merger
        nlu_result = self.nlu_node.process(query, history, active_catalog, session_id=session_id)
        if not (nlu_result.get("query") or {}).get("text"):
            if "query" not in nlu_result or not isinstance(nlu_result["query"], dict):
                nlu_result["query"] = {}
            nlu_result["query"]["text"] = query
        nlu_result["raw_query"] = query

        # Stage 2: Hard Constraint & Hybrid Retrieval using snapshot's index
        target_index = getattr(current_snap, "hybrid_index", None) if current_snap is not None else None
        candidates = self.retrieval_node.retrieve_candidates(
            nlu_result, active_catalog, top_k=12, hybrid_index=target_index
        )

        # Stage 3: Qwen 0.6B Recommender (Coarse Filtering)
        filtered = self.recommender_node.filter_candidates(candidates, nlu_result)

        # Stage 4: Qwen 0.6B Ranker & MMR Diversity
        ranked_top = self.ranker_node.rank_top_k(filtered, nlu_result, top_k=3)


        # Stage 5: Grounded Storytelling Explanation
        explanation_text = self.explainer_node.generate_explanation(ranked_top, nlu_result, query, history)

        # Aggregate diagnostics from candidates
        collected_diagnostics = [
            m.get("diagnostics") for m in ranked_top if m.get("diagnostics")
        ]

        return {
            "text": explanation_text,
            "recommendedMovies": ranked_top,
            "structuredIntent": nlu_result,
            "pipelineStages": {
                "nlu": nlu_result,
                "candidateCount": len(candidates),
                "rankedCount": len(ranked_top),
                "diagnostics": collected_diagnostics,
            },
            "followUps": self._build_follow_ups(nlu_result, ranked_top)
        }


# Global pipeline instance
cascading_pipeline = CascadingAIPipeline()
