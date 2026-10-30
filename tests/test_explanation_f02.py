"""
Regression and Quality Tests for Role B: ExplanationGeneratorNode (AI-OPT-01-F02).
Covers all response types and assertions required by F02 specifications:
1. Exact series lookup: factual, no similarity wording, no unrelated items appended.
2. Exact episode lookup: formatted cleanly with season/episode, no similarity wording, no unrelated items appended.
3. Plot search: explains matching detail, allows additional suggestions.
4. Segment/scene with timestamp: formatted [Mốc thời gian: mm:ss – mm:ss].
5. Segment/scene without timestamp: does NOT display '00:00 - 00:00'.
6. Genuine similarity search: uses 'Dựa trên sự tương đồng với...' only when requested.
7. Out-of-catalog foreign franchise abstention: clear explanation that only Jadoo is available.
8. Nonexistent season/episode: clear explanation that season/episode is unavailable.
9. Missing violence data: does NOT claim 'đã loại trừ hoàn toàn'.
10. Episode/title conflict: clearly acknowledges both and does not claim to have found the right single episode.
11. Clean display: strips .mp4 and deduplicates characters.
12. Missing rating/year: does NOT invent '8.0★' or '2025'.
"""

import sys
import pytest
from pathlib import Path

# Add backend/fastapi to sys.path
backend_fastapi_dir = Path(__file__).resolve().parent.parent / "backend" / "fastapi"
if str(backend_fastapi_dir) not in sys.path:
    sys.path.insert(0, str(backend_fastapi_dir))

from services.ai_pipeline import ExplanationGeneratorNode


@pytest.fixture
def explainer():
    return ExplanationGeneratorNode()


def test_01_exact_series_lookup(explainer):
    """'Tìm phim hoạt hình Xin Chào Jadoo' -> factual series intro, no similarity phrase, no extra items."""
    ranked = [{
        "id": "ser_jadoo",
        "title": "Xin Chào Jadoo",
        "item_type": "series",
        "description": "Bộ phim hoạt hình hài hước về cuộc sống của cô bé Jadoo và gia đình.",
        "characters": ["Choi Jadoo", "Jadoo", "Kim Min-ji"]
    }]
    nlu = {"query": {"text": "Tìm phim hoạt hình Xin Chào Jadoo"}, "reference": {"text": "Xin Chào Jadoo"}}
    res = explainer.generate_explanation(ranked, nlu, query="Tìm phim hoạt hình Xin Chào Jadoo")
    
    assert "Xin Chào Jadoo" in res
    assert "Dựa trên sự tương đồng" not in res
    assert "Ngoài ra" not in res
    # Characters deduplicated (no 'Choi Jadoo, Jadoo')
    assert "Choi Jadoo, Jadoo" not in res


def test_02_exact_episode_lookup(explainer):
    """'Xin Chào Jadoo Mùa 1 Tập 1' -> 'Đây là Xin Chào Jadoo Mùa 1, Tập 1...', no extra recommendations."""
    ranked = [
        {
            "id": "ep_jadoo_s01_0001",
            "title": "Anh sẽ mua cho em tất cả những gì em muốn ăn.",
            "item_type": "episode",
            "season_number": 1,
            "episode_number": 1,
            "year": 2011,
            "rating": None,
            "description": "Jadoo và gia đình trong bữa ăn đầu tiên."
        },
        {
            "id": "ep_jadoo_s01_0002",
            "title": "Muốn ăn nhưng lại sợ tăng cân",
            "item_type": "episode",
            "season_number": 1,
            "episode_number": 2
        }
    ]
    nlu = {"query": {"text": "Xin Chào Jadoo Mùa 1 Tập 1"}}
    res = explainer.generate_explanation(ranked, nlu, query="Xin Chào Jadoo Mùa 1 Tập 1")
    
    assert "Mùa 1" in res
    assert "Tập 1" in res
    assert "Anh sẽ mua cho em" in res
    assert "Dựa trên sự tương đồng" not in res
    # Unrelated episode must NOT be appended for exact episode lookup!
    assert "Muốn ăn nhưng lại sợ tăng cân" not in res
    assert "Ngoài ra" not in res
    # Missing rating must not invent 8.0★
    assert "8.0★" not in res
    assert "8.0" not in res


def test_03_plot_search(explainer):
    """'Tập nào Jadoo muốn ăn nhưng sợ tăng cân?' -> Explains matching plot, allows suggestions."""
    ranked = [
        {
            "id": "ep_jadoo_s01_0002",
            "title": "Muốn ăn nhưng lại sợ tăng cân",
            "item_type": "episode",
            "season_number": 1,
            "episode_number": 2,
            "plot_facts": ["Jadoo lo lắng về cân nặng nhưng không thể ngừng ăn ngon."],
            "description": ""
        },
        {
            "id": "ep_jadoo_s04_0024",
            "title": "Chúng tôi muốn có một bữa ăn ngon",
            "item_type": "episode",
            "season_number": 4,
            "episode_number": 24
        }
    ]
    nlu = {"query": {"text": "Tập nào Jadoo muốn ăn nhưng sợ tăng cân?"}}
    res = explainer.generate_explanation(ranked, nlu, query="Tập nào Jadoo muốn ăn nhưng sợ tăng cân?")
    
    assert "Muốn ăn nhưng lại sợ tăng cân" in res
    assert "Tình tiết trong tập" in res
    assert "Jadoo lo lắng về cân nặng" in res
    assert "Chúng tôi muốn có một bữa ăn ngon" in res


def test_04_segment_with_timestamp(explainer):
    """Segment with known start_ms and end_ms prints formatted time."""
    ranked = [{
        "id": "seg_01",
        "title": "Cứu cá vàng",
        "item_type": "segment",
        "parent_episode_title": "Tập 8: Thủy cung",
        "start_ms": 125000,
        "end_ms": 360000,
        "description": "Tiểu phẩm Jadoo cứu chú cá vàng."
    }]
    nlu = {"query": {"text": "Truyện ngắn Cứu cá vàng"}}
    res = explainer.generate_explanation(ranked, nlu, query="Truyện ngắn Cứu cá vàng")
    
    assert "Cứu cá vàng" in res
    assert "02:05" in res
    assert "06:00" in res
    assert "00:00" not in res


def test_05_segment_without_timestamp_no_00_00(explainer):
    """Segment with start_ms=None must NOT output '00:00'."""
    ranked = [{
        "id": "seg_02",
        "title": "Bức thư tình Ngày Valentine Trắng",
        "item_type": "segment",
        "parent_episode_title": "Gương kia, ai đẹp nhất thế gian？",
        "start_ms": None,
        "end_ms": None,
        "description": "Tiểu phẩm ngày lễ tình nhân."
    }]
    nlu = {"query": {"text": "Mẩu chuyện Bức thư tình bí ẩn"}}
    res = explainer.generate_explanation(ranked, nlu, query="Mẩu chuyện Bức thư tình bí ẩn")
    
    assert "Bức thư tình Ngày Valentine Trắng" in res
    assert "00:00" not in res


def test_06_genuine_similarity_search(explainer):
    """Only query with 'tương tự/giống' uses similarity wording."""
    ranked = [{
        "id": "ep_01",
        "title": "Chiếc xe mơ ước của ba",
        "item_type": "episode",
        "description": "Câu chuyện hài hước về chiếc ô tô."
    }]
    nlu = {
        "query": {"text": "Tìm phim tương tự Shin Cậu Bé Bút Chì"},
        "reference": {"text": "Shin Cậu Bé Bút Chì", "status": "CLEAR_REFERENCE_TEXT"}
    }
    res = explainer.generate_explanation(ranked, nlu, query="Tìm phim tương tự Shin Cậu Bé Bút Chì")
    
    assert "Dựa trên sự tương đồng" in res
    assert "Shin Cậu Bé Bút Chì" in res


def test_07_out_of_catalog_abstention_foreign_franchise(explainer):
    """An unmatched request does not claim the catalog has only one franchise."""
    nlu = {"query": {"text": "Gợi ý phim Doraemon tập dài"}}
    res = explainer.generate_explanation([], nlu, query="Gợi ý phim Doraemon tập dài")
    
    assert "chưa tìm thấy" in res
    assert "chỉ có dữ liệu" not in res
    assert "Tôi đã kiểm tra toàn bộ kho" not in res


def test_08_out_of_bounds_season_abstention(explainer):
    """Out of range season states season is unavailable."""
    nlu = {"query": {"text": "Jadoo Mùa 15 Tập 1"}}
    res = explainer.generate_explanation([], nlu, query="Jadoo Mùa 15 Tập 1")
    
    assert "chưa có mùa hoặc tập này" in res
    assert "Tôi đã kiểm tra toàn bộ kho" not in res


def test_09_missing_violence_condition_no_overclaiming(explainer):
    """Query asking for 'không có bạo lực' does NOT claim 'đã loại trừ hoàn toàn'."""
    ranked = [{
        "id": "ep_jadoo_s06_0013",
        "title": "Giữa chúng ta không có tình yêu",
        "item_type": "episode",
        "season_number": 6,
        "episode_number": 13,
        "year": 2021
    }]
    nlu = {
        "query": {"text": "Phim hoạt hình Jadoo phát hành năm 2021 không có bạo lực"},
        "constraints": {"exclude_genres": ["Violence"]}
    }
    res = explainer.generate_explanation(
        ranked,
        nlu,
        query="Phim hoạt hình Jadoo phát hành năm 2021 không có bạo lực"
    )
    
    assert "đã loại trừ hoàn toàn" not in res
    assert "chưa ghi nhận cảnh báo bạo lực" in res


def test_10_conflict_handling_explanation(explainer):
    """Conflict between requested episode and title acknowledges both."""
    ranked = [{
        "id": "ep_02",
        "title": "Muốn ăn nhưng lại sợ tăng cân",
        "item_type": "episode",
        "episode_number": 2,
        "diagnostics": {
            "conflict": {
                "type": "EPISODE_TITLE_CONFLICT",
                "requested_episode": 2,
                "conflicting_episode": 1,
                "conflicting_title": "Jadoo chơi bóng"
            }
        }
    }]
    nlu = {"query": {"text": "Jadoo tập 2 Jadoo chơi bóng"}}
    res = explainer.generate_explanation(ranked, nlu, query="Jadoo tập 2 Jadoo chơi bóng")
    
    assert "Tập 2" in res
    assert "Jadoo chơi bóng" in res
    assert "Tập 1" in res


def test_11_clean_title_removes_file_extensions(explainer):
    """Cleans .mp4, _720p, (NEW ) from title."""
    assert explainer._clean_title("Tap_01_Jadoo_Choi_Bong.mp4") == "Tap_01_Jadoo_Choi_Bong"
    assert explainer._clean_title("(NEW ) Bạn có biết đây là đâu không？") == "Bạn có biết đây là đâu không？"
    assert explainer._clean_title("Xin Chào Jadoo Xin Chào Jadoo") == "Xin Chào Jadoo"


def test_12_character_alias_deduplication(explainer):
    """Characters list deduplicates aliases."""
    raw = ["Choi Jadoo", "Jadoo", "최자두", "Jadoo Choi", "Kim Min-ji"]
    cleaned = explainer._clean_characters(raw)
    assert len(cleaned) == 2
    assert "Choi Jadoo" in cleaned
    assert "Kim Min-ji" in cleaned
    assert "Jadoo" not in cleaned[1:]
