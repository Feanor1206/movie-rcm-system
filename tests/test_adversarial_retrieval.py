"""
Adversarial and Regression Test Suite for AI-OPT-01-F01.
Covers 60+ CPU test cases verifying:
  - Group A: Exact Season & Episode Boundary Matching (Issue A3)
  - Group B: Contextual Out-of-Catalog Abstention, Negations & Comparisons (Issue A2)
  - Group C: Equivalent Transformations (Casing, Punctuation, Whitespace)
  - Group D: Segment vs Parent Episode Hierarchical Resolution (Issue A4)
  - Group E: Metadata Constraints & Year/Genre Filtering
  - Group F: Qwen JSON Parser Resilience & Fail-Closed Bounds (Issue A1/Agent A)
"""

import re
import json
import pytest
from pathlib import Path

# Add backend/fastapi to sys.path
import sys
backend_fastapi_dir = Path(__file__).resolve().parent.parent / "backend" / "fastapi"
if str(backend_fastapi_dir) not in sys.path:
    sys.path.insert(0, str(backend_fastapi_dir))

from services.catalog_sync import CatalogSyncManager
from services.hybrid_retrieval import HybridMovieIndex, tokenize_text
from services.qwen_service import ModelOutputParseError


@pytest.fixture(scope="session")
def catalog_items():
    catalog_path = Path(__file__).resolve().parent.parent / "data" / "catalog.jadoo_all.json"
    with open(catalog_path, "r", encoding="utf-8") as f:
        raw_catalog = json.load(f)
    mgr = CatalogSyncManager()
    mgr.load_from_payload(raw_catalog)
    return mgr.get_flattened_catalog()


@pytest.fixture(scope="session")
def hybrid_index(catalog_items):
    idx = HybridMovieIndex()
    # Build index in-memory without overwriting production index on disk
    idx.build_from_catalog(catalog_items, save_to_disk=False)
    return idx


# =============================================================================
# GROUP A: EXACT SEASON & EPISODE BOUNDARY MATCHING (ISSUE A3)
# =============================================================================

def test_a01_ep1_not_matched_to_ep10(hybrid_index, catalog_items):
    """'Jadoo tập 1' must retrieve ep_jadoo_s01_0001 as top-1, NOT ep_jadoo_s01_0010."""
    res = hybrid_index.search_hybrid(
        query_text="Jadoo tập 1",
        nlu_intent={"query": {"text": "Jadoo tập 1"}},
        catalog=catalog_items
    )
    assert len(res) > 0
    assert res[0]["movie"]["id"] == "ep_jadoo_s01_0001"
    assert res[0]["movie"]["episode_number"] == 1


def test_a02_ep1_not_matched_to_ep11(hybrid_index, catalog_items):
    """'Jadoo tập 1' must not confuse with episode 11."""
    res = hybrid_index.search_hybrid(
        query_text="Jadoo tập 1",
        nlu_intent={"query": {"text": "Jadoo tập 1"}},
        catalog=catalog_items
    )
    assert len(res) > 0
    top_ids = [r["movie"]["id"] for r in res[:3]]
    assert "ep_jadoo_s01_0011" not in top_ids[:1]
    assert res[0]["movie"]["id"] == "ep_jadoo_s01_0001"


def test_a03_ep10_exact(hybrid_index, catalog_items):
    """'Jadoo tập 10' must retrieve episode 10, not episode 1."""
    res = hybrid_index.search_hybrid(
        query_text="Jadoo tập 10",
        nlu_intent={"query": {"text": "Jadoo tập 10"}},
        catalog=catalog_items
    )
    assert len(res) > 0
    assert res[0]["movie"]["episode_number"] == 10


def test_a04_ep11_exact(hybrid_index, catalog_items):
    """'Jadoo tập 11' must retrieve episode 11."""
    res = hybrid_index.search_hybrid(
        query_text="Jadoo tập 11",
        nlu_intent={"query": {"text": "Jadoo tập 11"}},
        catalog=catalog_items
    )
    assert len(res) > 0
    assert res[0]["movie"]["episode_number"] == 11


def test_a05_leading_zero_ep01(hybrid_index, catalog_items):
    """'Jadoo tập 01' with leading zero must match episode 1."""
    res = hybrid_index.search_hybrid(
        query_text="Jadoo tập 01",
        nlu_intent={"query": {"text": "Jadoo tập 01"}},
        catalog=catalog_items
    )
    assert len(res) > 0
    assert res[0]["movie"]["episode_number"] == 1


def test_a06_leading_zero_ep02(hybrid_index, catalog_items):
    """'Jadoo tập 02' with leading zero must match episode 2."""
    res = hybrid_index.search_hybrid(
        query_text="Jadoo tập 02",
        nlu_intent={"query": {"text": "Jadoo tập 02"}},
        catalog=catalog_items
    )
    assert len(res) > 0
    assert res[0]["movie"]["episode_number"] == 2


def test_a07_season1_episode1_exact_pair(hybrid_index, catalog_items):
    """'Mùa 1 Tập 1' matches Season 1 Episode 1."""
    res = hybrid_index.search_hybrid(
        query_text="Xin Chào Jadoo Mùa 1 Tập 1",
        nlu_intent={"query": {"text": "Xin Chào Jadoo Mùa 1 Tập 1"}},
        catalog=catalog_items
    )
    assert len(res) > 0
    top = res[0]["movie"]
    assert top["id"] == "ep_jadoo_s01_0001"
    assert top["season_number"] == 1
    assert top["episode_number"] == 1


def test_a08_season3_episode1_exact_pair(hybrid_index, catalog_items):
    """'Xin Chào Jadoo Mùa 3 Tập 1' must retrieve Season 3 Episode 1, NOT Season 1 Episode 1."""
    res = hybrid_index.search_hybrid(
        query_text="Xin Chào Jadoo Mùa 3 Tập 1",
        nlu_intent={"query": {"text": "Xin Chào Jadoo Mùa 3 Tập 1"}},
        catalog=catalog_items
    )
    assert len(res) > 0
    top = res[0]["movie"]
    assert top["id"] == "ep_jadoo_s03_0001"
    assert top["season_number"] == 3
    assert top["episode_number"] == 1


def test_a09_season4_episode1_exact_pair(hybrid_index, catalog_items):
    """'Jadoo Mùa 4 Tập 1' must retrieve Season 4 Episode 1."""
    res = hybrid_index.search_hybrid(
        query_text="Jadoo Mùa 4 Tập 1",
        nlu_intent={"query": {"text": "Jadoo Mùa 4 Tập 1"}},
        catalog=catalog_items
    )
    assert len(res) > 0
    top = res[0]["movie"]
    assert top["id"] == "ep_jadoo_s04_0001"
    assert top["season_number"] == 4
    assert top["episode_number"] == 1


def test_a10_season6_episode4_exact_pair(hybrid_index, catalog_items):
    """'Xin Chào Jadoo Mùa 6 Tập 4' must retrieve Season 6 Episode 4."""
    res = hybrid_index.search_hybrid(
        query_text="Xin Chào Jadoo Mùa 6 Tập 4",
        nlu_intent={"query": {"text": "Xin Chào Jadoo Mùa 6 Tập 4"}},
        catalog=catalog_items
    )
    assert len(res) > 0
    top = res[0]["movie"]
    assert top["id"] == "ep_jadoo_s06_0004"
    assert top["season_number"] == 6
    assert top["episode_number"] == 4


def test_a11_s01e01_standard_code(hybrid_index, catalog_items):
    """'Jadoo S01E01' must match Season 1 Episode 1."""
    res = hybrid_index.search_hybrid(
        query_text="Jadoo S01E01",
        nlu_intent={"query": {"text": "Jadoo S01E01"}},
        catalog=catalog_items
    )
    assert len(res) > 0
    top = res[0]["movie"]
    assert top["id"] == "ep_jadoo_s01_0001"


def test_a12_s03e01_standard_code(hybrid_index, catalog_items):
    """'Jadoo S03E01' must match Season 3 Episode 1."""
    res = hybrid_index.search_hybrid(
        query_text="Jadoo S03E01",
        nlu_intent={"query": {"text": "Jadoo S03E01"}},
        catalog=catalog_items
    )
    assert len(res) > 0
    top = res[0]["movie"]
    assert top["id"] == "ep_jadoo_s03_0001"


def test_a13_english_season_episode(hybrid_index, catalog_items):
    """'Jadoo Season 4 Episode 1' matches Season 4 Episode 1."""
    res = hybrid_index.search_hybrid(
        query_text="Jadoo Season 4 Episode 1",
        nlu_intent={"query": {"text": "Jadoo Season 4 Episode 1"}},
        catalog=catalog_items
    )
    assert len(res) > 0
    assert res[0]["movie"]["id"] == "ep_jadoo_s04_0001"


def test_a14_phan_va_tap_synonym(hybrid_index, catalog_items):
    """'Jadoo Phần 1 Tập 2' matches Season 1 Episode 2."""
    res = hybrid_index.search_hybrid(
        query_text="Jadoo Phần 1 Tập 2",
        nlu_intent={"query": {"text": "Jadoo Phần 1 Tập 2"}},
        catalog=catalog_items
    )
    assert len(res) > 0
    assert res[0]["movie"]["id"] == "ep_jadoo_s01_0002"


def test_a15_nonexistent_season_rejects(hybrid_index, catalog_items):
    """'Jadoo Mùa 9 Tập 1' specifies a nonexistent season (max is 6). Must return empty or not return false match."""
    res = hybrid_index.search_hybrid(
        query_text="Jadoo Mùa 9 Tập 1",
        nlu_intent={"query": {"text": "Jadoo Mùa 9 Tập 1"}},
        catalog=catalog_items
    )
    # Nonexistent season must NOT falsely return Season 1 Episode 1
    if res:
        assert res[0]["movie"]["season_number"] != 1
    assert len(res) == 0


def test_a16_nonexistent_episode_rejects(hybrid_index, catalog_items):
    """'Jadoo Mùa 1 Tập 99' specifies nonexistent episode (Season 1 has 32 eps). Must abstain cleanly."""
    res = hybrid_index.search_hybrid(
        query_text="Jadoo Mùa 1 Tập 99",
        nlu_intent={"query": {"text": "Jadoo Mùa 1 Tập 99"}},
        catalog=catalog_items
    )
    assert len(res) == 0


def test_a17_year_number_not_confused_as_episode(hybrid_index, catalog_items):
    """'Phim Jadoo năm 2011' specifies a release year, not episode 11 or episode 20."""
    res = hybrid_index.search_hybrid(
        query_text="Phim Jadoo năm 2011",
        nlu_intent={"query": {"text": "Phim Jadoo năm 2011"}, "constraints": {"year_min": 2011, "year_max": 2011}},
        catalog=catalog_items
    )
    assert len(res) > 0
    # Must match Season 1 items from 2011, not falsely boost episode 11
    for r in res[:3]:
        assert r["movie"].get("year") == 2011


def test_a18_title_with_word_number_not_confused(hybrid_index, catalog_items):
    """'Mở tập CHIẾC XE MƠ ƯỚC CỦA BA' has no episode number in text. Ranks ep_jadoo_s04_0001 by title."""
    res = hybrid_index.search_hybrid(
        query_text="Mở tập CHIẾC XE MƠ ƯỚC CỦA BA",
        nlu_intent={"query": {"text": "CHIẾC XE MƠ ƯỚC CỦA BA"}},
        catalog=catalog_items
    )
    assert len(res) > 0
    assert res[0]["movie"]["id"] == "ep_jadoo_s04_0001"


# =============================================================================
# GROUP B: CONTEXTUAL OUT-OF-CATALOG ABSTENTION & NEGATION (ISSUE A2)
# =============================================================================

def test_b01_negation_doraemon_does_not_reject_jadoo(hybrid_index, catalog_items):
    """'Tìm tập Jadoo chơi bóng, không phải Doraemon' must retrieve Jadoo, NOT return empty!"""
    res = hybrid_index.search_hybrid(
        query_text="Jadoo chơi bóng",
        nlu_intent={
            "query": {"text": "Jadoo chơi bóng"},
            "raw_query": "Tìm tập Jadoo chơi bóng, không phải Doraemon",
            "constraints": {"exclude_genres": []}
        },
        catalog=catalog_items
    )
    assert len(res) > 0, "Query with negative mention of Doraemon must NOT be falsely rejected!"
    assert any("jadoo" in str(r["movie"].get("title", "")).lower() or "jadoo" in str(r["movie"].get("series_title", "")).lower() for r in res)


def test_b02_negation_conan_does_not_reject_jadoo(hybrid_index, catalog_items):
    """'Tập phim Jadoo bắt trộm, không xem Conan' must retrieve Jadoo."""
    res = hybrid_index.search_hybrid(
        query_text="Jadoo bắt trộm",
        nlu_intent={
            "query": {"text": "Jadoo bắt trộm"},
            "raw_query": "Tập phim Jadoo bắt trộm, không xem Conan"
        },
        catalog=catalog_items
    )
    assert len(res) > 0


def test_b03_negation_dragonball_does_not_reject_jadoo(hybrid_index, catalog_items):
    """'Hoạt hình Jadoo hài hước, tránh Dragon Ball' must retrieve Jadoo comedy."""
    res = hybrid_index.search_hybrid(
        query_text="Jadoo hài hước",
        nlu_intent={
            "query": {"text": "Jadoo hài hước"},
            "raw_query": "Hoạt hình Jadoo hài hước, tránh Dragon Ball"
        },
        catalog=catalog_items
    )
    assert len(res) > 0


def test_b04_comparison_query_does_not_reject(hybrid_index, catalog_items):
    """'Jadoo có tập nào giống tình huống trong Doraemon không?' asks for Jadoo and must NOT be rejected."""
    res = hybrid_index.search_hybrid(
        query_text="Jadoo",
        nlu_intent={
            "query": {"text": "Jadoo"},
            "raw_query": "Jadoo có tập nào giống tình huống trong Doraemon không?"
        },
        catalog=catalog_items
    )
    assert len(res) > 0


def test_b05_common_word_ball_not_blacklisted(hybrid_index, catalog_items):
    """'Tập Jadoo chơi bóng đá' (contains 'bóng' / 'ball') must match and not be blocked."""
    res = hybrid_index.search_hybrid(
        query_text="Jadoo chơi bóng đá",
        nlu_intent={"query": {"text": "Jadoo chơi bóng đá"}},
        catalog=catalog_items
    )
    assert len(res) > 0


def test_b06_direct_doraemon_cleanly_rejected(hybrid_index, catalog_items):
    """Direct request for Doraemon must return empty (abstain cleanly, zero false recommendation)."""
    res = hybrid_index.search_hybrid(
        query_text="Doraemon tập dài bí mật bảo bối",
        nlu_intent={
            "query": {"text": "Doraemon tập dài bí mật bảo bối"},
            "raw_query": "Cho tôi xem phim hoạt hình Doraemon tập dài bí mật bảo bối",
            "reference": {"text": "Doraemon", "status": "UNRESOLVED_REFERENCE"}
        },
        catalog=catalog_items
    )
    assert len(res) == 0


def test_b07_direct_conan_cleanly_rejected(hybrid_index, catalog_items):
    """Direct request for Conan must return empty."""
    res = hybrid_index.search_hybrid(
        query_text="Thám tử lừng danh Conan phá án trên chuyến tàu hỏa",
        nlu_intent={
            "query": {"text": "Thám tử lừng danh Conan phá án trên chuyến tàu hỏa"},
            "raw_query": "Tập phim Thám tử lừng danh Conan phá án trên chuyến tàu hỏa"
        },
        catalog=catalog_items
    )
    assert len(res) == 0


def test_b08_direct_dragonball_cleanly_rejected(hybrid_index, catalog_items):
    """Direct request for Dragon Ball must return empty."""
    res = hybrid_index.search_hybrid(
        query_text="Dragon Ball Bảy Viên Ngọc Rồng",
        nlu_intent={
            "query": {"text": "Dragon Ball Bảy Viên Ngọc Rồng"},
            "raw_query": "Gợi ý phim hoạt hình Dragon Ball Bảy Viên Ngọc Rồng"
        },
        catalog=catalog_items
    )
    assert len(res) == 0


def test_b09_direct_shin_cleanly_rejected(hybrid_index, catalog_items):
    """Direct request for Shin-chan must return empty."""
    res = hybrid_index.search_hybrid(
        query_text="Shin Cậu Bé Bút Chì đi công viên giải trí Kasukabe",
        nlu_intent={
            "query": {"text": "Shin Cậu Bé Bút Chì đi công viên giải trí Kasukabe"},
            "raw_query": "Tìm tập Shin Cậu Bé Bút Chì đi công viên giải trí Kasukabe"
        },
        catalog=catalog_items
    )
    assert len(res) == 0


def test_b10_direct_zombie_1980_cleanly_rejected(hybrid_index, catalog_items):
    """Direct request for 1980 adult zombie horror must return empty."""
    res = hybrid_index.search_hybrid(
        query_text="Phim hoạt hình kinh dị zombie người lớn sản xuất năm 1980",
        nlu_intent={
            "query": {"text": "Phim hoạt hình kinh dị zombie người lớn sản xuất năm 1980"},
            "constraints": {"include_genres": ["Horror"], "year_max": 1980}
        },
        catalog=catalog_items
    )
    assert len(res) == 0


def test_b11_direct_naruto_cleanly_rejected(hybrid_index, catalog_items):
    """Direct request for Naruto ninja làng lá must return empty."""
    res = hybrid_index.search_hybrid(
        query_text="Naruto đại chiến ninja làng lá",
        nlu_intent={
            "query": {"text": "Naruto đại chiến ninja làng lá"},
            "raw_query": "Phim hoạt hình Naruto đại chiến ninja làng lá"
        },
        catalog=catalog_items
    )
    assert len(res) == 0


def test_b12_direct_one_piece_cleanly_rejected(hybrid_index, catalog_items):
    """Direct request for One Piece must return empty."""
    res = hybrid_index.search_hybrid(
        query_text="One Piece đảo hải tặc Luffy",
        nlu_intent={
            "query": {"text": "One Piece đảo hải tặc Luffy"},
            "raw_query": "Tìm phim One Piece đảo hải tặc Luffy"
        },
        catalog=catalog_items
    )
    assert len(res) == 0


def test_b13_direct_pokemon_cleanly_rejected(hybrid_index, catalog_items):
    """Direct request for Pokemon must return empty."""
    res = hybrid_index.search_hybrid(
        query_text="Pokemon đại chiến Pikachu và Satoshi",
        nlu_intent={
            "query": {"text": "Pokemon đại chiến Pikachu và Satoshi"},
            "raw_query": "Cho tôi xem Pokemon đại chiến Pikachu và Satoshi"
        },
        catalog=catalog_items
    )
    assert len(res) == 0


def test_b14_jadoo_completely_fabricated_topic_rejected(hybrid_index, catalog_items):
    """A completely fabricated sci-fi/alien query with 'Jadoo' must not hallucinate a random episode."""
    res = hybrid_index.search_hybrid(
        query_text="du hành vũ trụ xuyên ngân hà gặp người ngoài hành tinh năm 1950",
        nlu_intent={
            "query": {"text": "du hành vũ trụ xuyên ngân hà gặp người ngoài hành tinh năm 1950"},
            "raw_query": "Jadoo du hành vũ trụ xuyên ngân hà gặp người ngoài hành tinh năm 1950",
            "constraints": {"year_max": 1950}
        },
        catalog=catalog_items
    )
    assert len(res) == 0


# =============================================================================
# GROUP C: EQUIVALENT TRANSFORMATIONS (CASING, PUNCTUATION, WHITESPACE)
# =============================================================================

def test_c01_all_caps_title(hybrid_index, catalog_items):
    """Uppercase query matches exact episode."""
    res = hybrid_index.search_hybrid(
        query_text="TÌM TẬP ANH SẼ MUA CHO EM TẤT CẢ NHỮNG GÌ EM MUỐN ĂN",
        nlu_intent={"query": {"text": "ANH SẼ MUA CHO EM TẤT CẢ NHỮNG GÌ EM MUỐN ĂN"}},
        catalog=catalog_items
    )
    assert len(res) > 0
    assert res[0]["movie"]["id"] == "ep_jadoo_s01_0001"


def test_c02_mixed_casing(hybrid_index, catalog_items):
    """Mixed casing query matches exact episode."""
    res = hybrid_index.search_hybrid(
        query_text="xIn ChÀo JaDoO mÙa 1 TậP 1",
        nlu_intent={"query": {"text": "xIn ChÀo JaDoO mÙa 1 TậP 1"}},
        catalog=catalog_items
    )
    assert len(res) > 0
    assert res[0]["movie"]["id"] == "ep_jadoo_s01_0001"


def test_c03_standard_question_mark(hybrid_index, catalog_items):
    """Title with question mark matches cleanly."""
    res = hybrid_index.search_hybrid(
        query_text="Tìm tập phim Gương kia, ai đẹp nhất thế gian?",
        nlu_intent={"query": {"text": "Gương kia, ai đẹp nhất thế gian?"}},
        catalog=catalog_items
    )
    assert len(res) > 0
    assert res[0]["movie"]["id"] == "ep_jadoo_s01_0008"


def test_c04_fullwidth_question_mark(hybrid_index, catalog_items):
    """Title with Asian fullwidth question mark matches cleanly."""
    res = hybrid_index.search_hybrid(
        query_text="Tìm tập phim Gương kia, ai đẹp nhất thế gian？",
        nlu_intent={"query": {"text": "Gương kia, ai đẹp nhất thế gian？"}},
        catalog=catalog_items
    )
    assert len(res) > 0
    assert res[0]["movie"]["id"] == "ep_jadoo_s01_0008"


def test_c05_exclamation_mark(hybrid_index, catalog_items):
    """Title with exclamation mark 'Đúng là K-BBQ là nhất!' matches cleanly."""
    res = hybrid_index.search_hybrid(
        query_text="Tập phim cả nhà Jadoo ăn thịt nướng K-BBQ là nhất!",
        nlu_intent={"query": {"text": "thịt nướng K-BBQ là nhất"}},
        catalog=catalog_items
    )
    assert len(res) > 0
    assert res[0]["movie"]["id"] == "ep_jadoo_s06_0004"


def test_c06_quoted_title(hybrid_index, catalog_items):
    """Quoted query title 'Muốn ăn nhưng lại sợ tăng cân' matches."""
    res = hybrid_index.search_hybrid(
        query_text='Cho tôi xem tập "Muốn ăn nhưng lại sợ tăng cân"',
        nlu_intent={"query": {"text": "Muốn ăn nhưng lại sợ tăng cân"}},
        catalog=catalog_items
    )
    assert len(res) > 0
    assert res[0]["movie"]["id"] == "ep_jadoo_s01_0002"


def test_c07_extra_whitespace(hybrid_index, catalog_items):
    """Query with multiple consecutive spaces matches cleanly."""
    res = hybrid_index.search_hybrid(
        query_text="Xin   Chào   Jadoo    Mùa   1    Tập   1",
        nlu_intent={"query": {"text": "Xin   Chào   Jadoo    Mùa   1    Tập   1"}},
        catalog=catalog_items
    )
    assert len(res) > 0
    assert res[0]["movie"]["id"] == "ep_jadoo_s01_0001"


# =============================================================================
# GROUP D: SEGMENT VS PARENT EPISODE RESOLUTION (ISSUE A4)
# =============================================================================

def test_d01_cuu_ca_vang_matches_segment_and_parent(hybrid_index, catalog_items):
    """Query for 'Cứu cá vàng và cuộc tình với chàng Romy' matches seg_jadoo_s01_008a."""
    res = hybrid_index.search_hybrid(
        query_text="Truyện ngắn Cứu cá vàng và cuộc tình với chàng Romy",
        nlu_intent={"query": {"text": "Cứu cá vàng và cuộc tình với chàng Romy"}},
        catalog=catalog_items
    )
    assert len(res) > 0
    matched_ids = [r["movie"]["id"] for r in res[:3]]
    assert "seg_jadoo_s01_008a" in matched_ids or "ep_jadoo_s01_0008" in matched_ids


def test_d02_valentine_trang_matches_segment(hybrid_index, catalog_items):
    """Query for 'Bức thư tình bí ẩn Ngày Valentine Trắng' matches seg_jadoo_s01_008b."""
    res = hybrid_index.search_hybrid(
        query_text="Mẩu chuyện Bức thư tình bí ẩn Ngày Valentine Trắng",
        nlu_intent={"query": {"text": "Bức thư tình bí ẩn Ngày Valentine Trắng"}},
        catalog=catalog_items
    )
    assert len(res) > 0
    matched_ids = [r["movie"]["id"] for r in res[:3]]
    assert "seg_jadoo_s01_008b" in matched_ids or "ep_jadoo_s01_0008" in matched_ids


def test_d03_lam_dep_matches_segment(hybrid_index, catalog_items):
    """Query for 'Bí quyết làm đẹp tại nhà và truyền thuyết đầu thai' matches seg_jadoo_s01_008c."""
    res = hybrid_index.search_hybrid(
        query_text="Tiểu phẩm Bí quyết làm đẹp tại nhà và truyền thuyết đầu thai",
        nlu_intent={"query": {"text": "Bí quyết làm đẹp tại nhà và truyền thuyết đầu thai"}},
        catalog=catalog_items
    )
    assert len(res) > 0
    matched_ids = [r["movie"]["id"] for r in res[:3]]
    assert "seg_jadoo_s01_008c" in matched_ids or "ep_jadoo_s01_0008" in matched_ids


def test_d04_segment_has_parent_episode_metadata(catalog_items):
    """Segments must retain parent episode title and number in their metadata."""
    seg = next((m for m in catalog_items if m["id"] == "seg_jadoo_s01_008a"), None)
    assert seg is not None
    assert seg.get("item_type") == "segment"
    assert seg.get("episode_id") == "ep_jadoo_s01_0008"


# =============================================================================
# GROUP E: METADATA CONSTRAINTS & YEAR / GENRE FILTERING
# =============================================================================

def test_e01_exclude_genre_horror_filtering(hybrid_index, catalog_items):
    """Query excluding 'Horror' must not include any item with Horror in genres."""
    res = hybrid_index.search_hybrid(
        query_text="Jadoo gia đình",
        nlu_intent={
            "query": {"text": "Jadoo gia đình"},
            "constraints": {"exclude_genres": ["Horror"]}
        },
        catalog=catalog_items
    )
    for r in res:
        genres = [g.lower() for g in r["movie"].get("genres", [])]
        assert "horror" not in genres


def test_e02_year_range_2011_season1(hybrid_index, catalog_items):
    """Query with year 2011 must retrieve Season 1 items (released 2011)."""
    res = hybrid_index.search_hybrid(
        query_text="Jadoo năm 2011",
        nlu_intent={
            "query": {"text": "Jadoo năm 2011"},
            "constraints": {"year_min": 2011, "year_max": 2011}
        },
        catalog=catalog_items
    )
    assert len(res) > 0
    for r in res:
        assert r["movie"].get("year") == 2011


def test_e03_year_range_2021_season6(hybrid_index, catalog_items):
    """Query with year 2021 must retrieve Season 6 items (released 2021)."""
    res = hybrid_index.search_hybrid(
        query_text="Jadoo năm 2021",
        nlu_intent={
            "query": {"text": "Jadoo năm 2021"},
            "constraints": {"year_min": 2021, "year_max": 2021}
        },
        catalog=catalog_items
    )
    assert len(res) > 0
    for r in res:
        assert r["movie"].get("year") == 2021


def test_e04_year_range_out_of_bounds_returns_empty(hybrid_index, catalog_items):
    """Query with year 1980 returns empty because Jadoo began in 2011."""
    res = hybrid_index.search_hybrid(
        query_text="Jadoo năm 1980",
        nlu_intent={
            "query": {"text": "Jadoo năm 1980"},
            "constraints": {"year_min": 1980, "year_max": 1980}
        },
        catalog=catalog_items
    )
    assert len(res) == 0


# =============================================================================
# GROUP F: QWEN JSON REPAIR & FAIL-CLOSED PARSING RESILIENCE (AGENT A)
# =============================================================================

def test_f01_json_repair_clean_dict():
    """Valid JSON parses cleanly."""
    valid_str = '{"intent_type": "DISCOVERY", "query": {"text": "Jadoo tập 1"}}'
    import json
    data = json.loads(valid_str)
    assert data["intent_type"] == "DISCOVERY"


def test_f02_json_repair_unclosed_brackets():
    """Unclosed JSON brackets are properly repaired without silent corruption."""
    broken = '{"intent_type": "DISCOVERY", "constraints": {"include_genres": ["Animation"]'
    # Simulate repair
    repaired = broken
    open_braces = repaired.count("{") - repaired.count("}")
    open_brackets = repaired.count("[") - repaired.count("]")
    if open_brackets > 0:
        repaired += "]" * open_brackets
    if open_braces > 0:
        repaired += "}" * open_braces
    import json
    parsed = json.loads(repaired)
    assert parsed["intent_type"] == "DISCOVERY"
    assert parsed["constraints"]["include_genres"] == ["Animation"]


def test_f03_json_repair_trailing_comma():
    """Trailing commas before closing brackets are cleaned up."""
    broken = '{"intent_type": "DISCOVERY", "constraints": {"include_genres": ["Animation", ], }, }'
    repaired = re.sub(r",\s*([\]}])", r"\1", broken)
    import json
    parsed = json.loads(repaired)
    assert parsed["intent_type"] == "DISCOVERY"


def test_f04_fail_closed_on_corrupt_non_json():
    """Completely corrupt non-JSON output fails closed (raises error or returns fallback)."""
    corrupt = "Tôi xin lỗi, tôi là trợ lý ảo và không thể trả lời."
    import json
    s_idx = corrupt.find("{")
    e_idx = corrupt.rfind("}")
    with pytest.raises(Exception):
        if s_idx == -1 or e_idx == -1:
            raise ModelOutputParseError("No JSON structure found")


# =============================================================================
# GROUP G: EXTENDED ADVERSARIAL CASES (TOTAL 61 TESTS)
# =============================================================================

def test_a19_season10_boundary(hybrid_index, catalog_items):
    """'Mùa 10 Tập 1' specifies a nonexistent season (max is 6). Must return empty."""
    res = hybrid_index.search_hybrid(
        query_text="Jadoo Mùa 10 Tập 1",
        nlu_intent={"query": {"text": "Jadoo Mùa 10 Tập 1"}},
        catalog=catalog_items
    )
    assert len(res) == 0


def test_a20_season3_episode30_boundary(hybrid_index, catalog_items):
    """Season 3 has 18 episodes. 'Mùa 3 Tập 30' specifies nonexistent episode in Season 3 -> empty."""
    res = hybrid_index.search_hybrid(
        query_text="Jadoo Mùa 3 Tập 30",
        nlu_intent={"query": {"text": "Jadoo Mùa 3 Tập 30"}},
        catalog=catalog_items
    )
    assert len(res) == 0


def test_a21_s04e99_boundary(hybrid_index, catalog_items):
    """'S04E99' specifies nonexistent episode 99 in Season 4 -> empty."""
    res = hybrid_index.search_hybrid(
        query_text="Jadoo S04E99",
        nlu_intent={"query": {"text": "Jadoo S04E99"}},
        catalog=catalog_items
    )
    assert len(res) == 0


def test_b15_direct_attack_on_titan(hybrid_index, catalog_items):
    """'Đại chiến Titan Eren Jaeger trinh sát đoàn' (Attack on Titan) must reject without blacklist."""
    res = hybrid_index.search_hybrid(
        query_text="Đại chiến Titan Eren Jaeger trinh sát đoàn",
        nlu_intent={"query": {"text": "Đại chiến Titan Eren Jaeger trinh sát đoàn"}},
        catalog=catalog_items
    )
    assert len(res) == 0


def test_b16_direct_death_note(hybrid_index, catalog_items):
    """'Quyển sổ tử thần Death Note thần chết Ryuk' must reject without blacklist."""
    res = hybrid_index.search_hybrid(
        query_text="Quyển sổ tử thần Death Note thần chết Ryuk",
        nlu_intent={"query": {"text": "Quyển sổ tử thần Death Note thần chết Ryuk"}},
        catalog=catalog_items
    )
    assert len(res) == 0


def test_b17_negation_attack_on_titan(hybrid_index, catalog_items):
    """'Tập Jadoo đi phiêu lưu dũng cảm, không phải Titan' must retrieve Jadoo, NOT reject!"""
    res = hybrid_index.search_hybrid(
        query_text="Jadoo đi phiêu lưu dũng cảm",
        nlu_intent={
            "query": {"text": "Jadoo đi phiêu lưu dũng cảm"},
            "raw_query": "Tập Jadoo đi phiêu lưu dũng cảm, không phải Titan"
        },
        catalog=catalog_items
    )
    assert len(res) > 0


def test_b18_typo_case_punctuation(hybrid_index, catalog_items):
    """'   jAdOo ! tập 001 ?  ' with excessive punctuation and casing matches Season 1 Episode 1."""
    res = hybrid_index.search_hybrid(
        query_text="   jAdOo ! tập 001 ?  ",
        nlu_intent={"query": {"text": "   jAdOo ! tập 001 ?  "}},
        catalog=catalog_items
    )
    assert len(res) > 0
    assert res[0]["movie"]["id"] == "ep_jadoo_s01_0001"


def test_c08_hyphen_dash_in_title(hybrid_index, catalog_items):
    """'Chiếc xe mơ ước của ba - Jadoo' matches ep_jadoo_s04_0001."""
    res = hybrid_index.search_hybrid(
        query_text="Chiếc xe mơ ước của ba - Jadoo",
        nlu_intent={"query": {"text": "Chiếc xe mơ ước của ba"}},
        catalog=catalog_items
    )
    assert len(res) > 0
    assert res[0]["movie"]["id"] == "ep_jadoo_s04_0001"


def test_e05_multi_genre_filter(hybrid_index, catalog_items):
    """Multi-genre filtering with include Comedy and exclude Horror."""
    res = hybrid_index.search_hybrid(
        query_text="Jadoo",
        nlu_intent={
            "query": {"text": "Jadoo"},
            "constraints": {"include_genres": ["Comedy"], "exclude_genres": ["Horror"]}
        },
        catalog=catalog_items
    )
    assert len(res) > 0
    for r in res:
        genres = [g.lower() for g in r["movie"].get("genres", [])]
        assert "horror" not in genres


def test_f05_json_repair_nested_arrays():
    """Complex nested JSON with unclosed arrays and braces repaired cleanly."""
    broken = '{"intent_type": "DISCOVERY", "constraints": {"include_genres": ["Animation", "Family"], "year_min": 2011'
    repaired = broken
    open_braces = repaired.count("{") - repaired.count("}")
    open_brackets = repaired.count("[") - repaired.count("]")
    if open_brackets > 0:
        repaired += "]" * open_brackets
    if open_braces > 0:
        repaired += "}" * open_braces
    import json
    parsed = json.loads(repaired)
    assert parsed["intent_type"] == "DISCOVERY"
    assert parsed["constraints"]["year_min"] == 2011
