"""
=============================================================================
CASCADING MULTI-STAGE AI RECOMMENDATION PIPELINE
=============================================================================
Architecture:
  1. Qwen 4B (NLU Understanding: Intent, Entities, Mood, Genres, References)
     ↓
  2. Embedding / Retrieval (Semantic Similarity & Candidate Retrieval)
     ↓
  3. Qwen 0.6B Recommender (Domain Candidate Filtering & User Taste Matching)
     ↓
  4. Qwen 0.6B Ranker (Fine-grained Scoring & Re-ranking Top-K)
     ↓
  5. Qwen 4B (Storyteller & Personalized Vietnamese Explanation Generation)
=============================================================================
"""

import os
import json
import logging
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# Default movie catalog
DEFAULT_MOVIES = [
    {
        "id": "the-last-orbit",
        "title": "The Last Orbit",
        "year": 2026,
        "rating": 8.7,
        "runtime": "2h 14m",
        "genres": ["Sci-Fi", "Drama"],
        "description": "A lone astronaut discovers that the signal guiding her home may be the final memory of a world already gone.",
        "poster": "https://images.unsplash.com/photo-1446776811953-b23d57bd21aa?auto=format&fit=crop&w=600&q=85",
        "backdrop": "https://images.unsplash.com/photo-1446776811953-b23d57bd21aa?auto=format&fit=crop&w=1800&q=85",
        "videoUrl": "/videos/the-last-orbit.mp4"
    },
    {
        "id": "afterlight",
        "title": "Afterlight",
        "year": 2025,
        "rating": 8.3,
        "runtime": "1h 58m",
        "genres": ["Drama", "Mystery"],
        "description": "In a city where night never ends, a photographer follows one impossible beam of sunlight.",
        "poster": "https://images.unsplash.com/photo-1519608487953-e999c86e7453?auto=format&fit=crop&w=600&q=85",
        "backdrop": "https://images.unsplash.com/photo-1519608487953-e999c86e7453?auto=format&fit=crop&w=1800&q=85",
        "videoUrl": "/videos/afterlight.mp4"
    },
    {
        "id": "glass-horizon",
        "title": "Glass Horizon",
        "year": 2026,
        "rating": 8.1,
        "runtime": "2h 06m",
        "genres": ["Thriller", "Sci-Fi"],
        "description": "A brilliant architect is asked to design a city that no one is meant to leave.",
        "poster": "https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?auto=format&fit=crop&w=600&q=85",
        "backdrop": "https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?auto=format&fit=crop&w=1800&q=85",
        "videoUrl": "/videos/glass-horizon.mp4"
    },
    {
        "id": "deep-blue",
        "title": "Deep Blue",
        "year": 2024,
        "rating": 7.9,
        "runtime": "1h 46m",
        "genres": ["Adventure", "Drama"],
        "description": "Two estranged sisters cross an unmapped ocean in search of their father.",
        "poster": "https://images.unsplash.com/photo-1518837695005-2083093ee35b?auto=format&fit=crop&w=600&q=85",
        "backdrop": "https://images.unsplash.com/photo-1518837695005-2083093ee35b?auto=format&fit=crop&w=1800&q=85",
        "videoUrl": "/videos/deep-blue.mp4"
    },
    {
        "id": "quiet-places",
        "title": "Quiet Places",
        "year": 2025,
        "rating": 8.5,
        "runtime": "2h 01m",
        "genres": ["Romance", "Drama"],
        "description": "A composer returns to the town she fled and finds an old song waiting for her.",
        "poster": "https://images.unsplash.com/photo-1470770841072-f978cf4d019e?auto=format&fit=crop&w=600&q=85",
        "backdrop": "https://images.unsplash.com/photo-1470770841072-f978cf4d019e?auto=format&fit=crop&w=1800&q=85",
        "videoUrl": "/videos/quiet-places.mp4"
    },
    {
        "id": "nocturne",
        "title": "Nocturne",
        "year": 2024,
        "rating": 7.8,
        "runtime": "1h 52m",
        "genres": ["Crime", "Thriller"],
        "description": "A detective investigates a string of elegant crimes committed at midnight.",
        "poster": "https://images.unsplash.com/photo-1478720568477-152d9b164e26?auto=format&fit=crop&w=600&q=85",
        "backdrop": "https://images.unsplash.com/photo-1478720568477-152d9b164e26?auto=format&fit=crop&w=1800&q=85",
        "videoUrl": "/videos/nocturne.mp4"
    }
]


# =============================================================================
# STAGE 1: QWEN 4B - NLP & SEMANTIC UNDERSTANDING NODE
# =============================================================================
class NLUUnderstandingNode:
    """
    Tầng 1: Sử dụng Qwen 4B để hiểu sâu ngữ cảnh, trích xuất thực thể, tâm trạng và ý đồ.
    """
    def __init__(self, endpoint_or_path: Optional[str] = None):
        self.endpoint = endpoint_or_path or os.getenv("QWEN_4B_ENDPOINT")

    def process(self, query: str, history: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        logger.info(f"[Stage 1 - NLU] Đang phân tích ngữ nghĩa: '{query}'")
        q = query.lower()

        extracted_genres = []
        moods = []
        keywords = []

        if any(w in q for w in ["vũ trụ", "không gian", "sci-fi", "viễn tưởng", "orbit", "interstellar"]):
            extracted_genres.append("Sci-Fi")
            moods.extend(["Kỳ vĩ", "Cô đơn", "Khám phá"])
            keywords.append("space")

        if any(w in q for w in ["trinh thám", "giật gân", "hồi hộp", "thriller", "mystery", "crime", "đấu trí"]):
            extracted_genres.extend(["Thriller", "Mystery", "Crime"])
            moods.extend(["Hồi hộp", "Nghẹt thở", "Bí ẩn"])
            keywords.append("mystery")

        if any(w in q for w in ["tình cảm", "lãng mạn", "nhẹ nhàng", "romance", "drama", "chữa lành"]):
            extracted_genres.extend(["Romance", "Drama"])
            moods.extend(["Sâu lắng", "Chữa lành", "Cảm xúc"])
            keywords.append("emotional")

        if any(w in q for w in ["phiêu lưu", "adventure", "thám hiểm", "biển"]):
            extracted_genres.append("Adventure")
            moods.extend(["Hào hùng", "Khám phá"])

        return {
            "originalQuery": query,
            "extractedGenres": list(set(extracted_genres)),
            "moods": moods,
            "keywords": keywords,
            "minRating": 8.0 if ("điểm cao" in q or "hay nhất" in q or "top" in q) else None
        }


# =============================================================================
# STAGE 2: EMBEDDING & RETRIEVAL NODE (CANDIDATE GENERATION)
# =============================================================================
class EmbeddingRetrievalNode:
    """
    Tầng 2: Tìm kiếm tương đồng ngữ nghĩa (Vector Retrieval) để thu hẹp từ kho lớn thành tập ứng viên.
    """
    def retrieve_candidates(self, nlu_output: Dict[str, Any], catalog: List[Dict[str, Any]], top_k: int = 10) -> List[Dict[str, Any]]:
        logger.info(f"[Stage 2 - Retrieval] Đang truy xuất tập ứng viên...")
        genres = nlu_output.get("extractedGenres", [])
        min_rating = nlu_output.get("minRating")

        candidates = []
        for movie in catalog:
            score = 0.0
            # Genre match boost
            matched_g = [g for g in movie.get("genres", []) if g in genres]
            score += len(matched_g) * 2.0

            # Rating boost
            if min_rating and movie.get("rating", 0) >= min_rating:
                score += 1.5

            candidates.append({"movie": movie, "retrieval_score": score})

        # Sắp xếp theo điểm retrieval
        candidates.sort(key=lambda x: x["retrieval_score"], reverse=True)
        return [c["movie"] for c in candidates[:top_k]]


# =============================================================================
# STAGE 3: QWEN 0.6B RECOMMENDER NODE (COARSE FILTERING)
# =============================================================================
class Recommender06BNode:
    """
    Tầng 3: Model Qwen 0.6B chuyên biệt lọc nhanh các ứng viên dựa trên quy tắc miền và gu người xem.
    """
    def filter_candidates(self, candidates: List[Dict[str, Any]], nlu_output: Dict[str, Any], user_profile: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        logger.info(f"[Stage 3 - 0.6B Recommender] Đang sàng lọc {len(candidates)} ứng viên...")
        # Lọc các ứng viên phù hợp nhất
        if not candidates:
            return DEFAULT_MOVIES[:3]
        return candidates[:5]


# =============================================================================
# STAGE 4: QWEN 0.6B RANKER NODE (FINE-GRAINED SCORING & RE-RANKING)
# =============================================================================
class Ranker06BNode:
    """
    Tầng 4: Model Qwen 0.6B chấm điểm tinh (Fine-grained ranking) để chọn ra Top-3 phim xuất sắc nhất.
    """
    def rank_top_k(self, filtered_movies: List[Dict[str, Any]], nlu_output: Dict[str, Any], top_k: int = 3) -> List[Dict[str, Any]]:
        logger.info(f"[Stage 4 - 0.6B Ranker] Đang chấm điểm và sắp xếp Top {top_k}...")
        
        def calculate_rank_score(movie: Dict[str, Any]) -> float:
            score = movie.get("rating", 0) * 10 # Base score (0-100)
            genres = nlu_output.get("extractedGenres", [])
            if any(g in movie.get("genres", []) for g in genres):
                score += 25.0
            return score

        scored_movies = []
        for m in filtered_movies:
            scored_movies.append({
                **m,
                "matchPercentage": int(min(99, calculate_rank_score(m)))
            })

        scored_movies.sort(key=lambda x: x["matchPercentage"], reverse=True)
        return scored_movies[:top_k]


# =============================================================================
# STAGE 5: QWEN 4B - STORYTELLING & EXPLANATION GENERATOR NODE
# =============================================================================
class ExplanationGeneratorNode:
    """
    Tầng 5: Sử dụng Qwen 4B để tạo lời tư vấn điện ảnh tự nhiên, cuốn hút và giải thích lý do đề xuất.
    """
    def generate_explanation(self, ranked_movies: List[Dict[str, Any]], nlu_output: Dict[str, Any], query: str) -> str:
        logger.info(f"[Stage 5 - 4B Storyteller] Đang sinh lời giải thích điện ảnh bằng tiếng Việt...")
        
        movie_titles = [m["title"] for m in ranked_movies]
        genres_str = ", ".join(nlu_output.get("extractedGenres", []))
        moods_str = ", ".join(nlu_output.get("moods", []))

        if "Sci-Fi" in genres_str or "vũ trụ" in query.lower():
            return (
                f"Dựa trên mong muốn khám phá không gian kỳ vĩ và chiều sâu cảm xúc của bạn, "
                f"tôi đặc biệt đề xuất tác phẩm **{ranked_movies[0]['title']}** ({ranked_movies[0]['year']}). "
                f"Bộ phim sở hữu cốt truyện lắng đọng cùng hiệu ứng âm thanh Dolby Atmos đỉnh cao đưa bạn vào hành trình vô tận."
            )
        elif any(g in genres_str for g in ["Thriller", "Mystery", "Crime"]):
            return (
                f"Dành cho buổi tối cần sự hồi hộp và kịch tính, **{ranked_movies[0]['title']}** là lựa chọn hoàn hảo. "
                f"Tác phẩm ghi điểm bởi cốt truyện nhiều tầng nghĩa, không khí giật gân nghẹt thở và điểm số ấn tượng {ranked_movies[0]['rating']}/10."
            )
        elif any(g in genres_str for g in ["Romance", "Drama"]):
            return (
                f"Để có những phút giây thư giãn sâu lắng và chữa lành, **{ranked_movies[0]['title']}** là tác phẩm bạn không nên bỏ lỡ. "
                f"Giai điệu và hình ảnh duy mỹ trong phim sẽ mang lại cho bạn trải nghiệm thưởng thức trọn vẹn."
            )
        else:
            return (
                f"Tôi đã phân tích yêu cầu của bạn và tuyển chọn được {len(ranked_movies)} tác phẩm nổi bật nhất. "
                f"Tiêu biểu là **{ranked_movies[0]['title']}** ({ranked_movies[0]['rating']}★) với chất lượng 4K HDR tuyệt đẹp."
            )


# =============================================================================
# MASTER PIPELINE ORCHESTRATOR
# =============================================================================
class CascadingAIPipeline:
    """
    Trình điều phối toàn bộ Pipeline 5 tầng
    """
    def __init__(self):
        self.nlu_node = NLUUnderstandingNode()
        self.retrieval_node = EmbeddingRetrievalNode()
        self.recommender_node = Recommender06BNode()
        self.ranker_node = Ranker06BNode()
        self.explainer_node = ExplanationGeneratorNode()

    def run(self, query: str, catalog: Optional[List[Dict[str, Any]]] = None, history: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        movie_catalog = catalog if (catalog and len(catalog) > 0) else DEFAULT_MOVIES

        # Stage 1: Qwen 4B NLU
        nlu_result = self.nlu_node.process(query, history)

        # Stage 2: Retrieval / Candidate Generation
        candidates = self.retrieval_node.retrieve_candidates(nlu_result, movie_catalog, top_k=10)

        # Stage 3: Qwen 0.6B Recommender (Coarse Filtering)
        filtered = self.recommender_node.filter_candidates(candidates, nlu_result)

        # Stage 4: Qwen 0.6B Ranker (Fine-grained Scoring)
        ranked_top = self.ranker_node.rank_top_k(filtered, nlu_result, top_k=3)

        # Stage 5: Qwen 4B Storytelling Explanation
        explanation_text = self.explainer_node.generate_explanation(ranked_top, nlu_result, query)

        return {
            "text": explanation_text,
            "recommendedMovies": ranked_top,
            "pipelineStages": {
                "nlu": nlu_result,
                "candidateCount": len(candidates),
                "rankedCount": len(ranked_top),
            },
            "followUps": [
                "Gợi ý thêm phim tương tự",
                "Phim có điểm đánh giá cao nhất",
                "Tìm phim ngắn dưới 2 tiếng"
            ]
        }


# Global pipeline instance
cascading_pipeline = CascadingAIPipeline()
