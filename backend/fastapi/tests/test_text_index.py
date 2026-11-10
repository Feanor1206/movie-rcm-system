import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.text_index import TextIndex, prepare_embeddings
from services.search import SearchService


class Encoder:
    def __init__(self):
        self.encoded = []

    def encode_documents(self, texts):
        self.encoded.extend(texts)
        return [[len(text), 1.0, 2.0] for text in texts]

    def encode_queries(self, texts):
        return [[len(text), 1.0, 2.0] for text in texts]


@pytest.fixture
def catalog():
    return [
        {"id": "ep1", "title": "Tập 1", "episode_number": 1, "season_number": 2,
         "item_type": "episode", "description": "Đi học", "genres": ["Animation"], "year": 2020},
        {"id": "ep10", "title": "Tập 10", "episode_number": 10, "season_number": 2,
         "item_type": "episode", "description": "Chơi bóng", "genres": ["Animation"], "year": 2021},
        {"id": "scene1", "title": "Chiếc bình", "episode_id": "ep1", "item_type": "scene",
         "visual_summary": "Jadoo làm vỡ bình hoa", "start_ms": 520_000, "end_ms": 555_000},
    ]


def test_sync_build_never_embeds_and_reports_missing_dense(tmp_path, catalog):
    encoder = Encoder()
    index = TextIndex.build(catalog, cache_dir=tmp_path, encoder=encoder, model_id="model@v1")
    assert encoder.encoded == []
    assert not index.dense_ready
    assert index.missing_embeddings == len(catalog)
    assert index.search("bình hoa")[0]["episodeId"] == "ep1"


def test_embeddings_reused_by_content_and_model_version(tmp_path, catalog):
    encoder = Encoder()
    prepare_embeddings(catalog, cache_dir=tmp_path, encoder=encoder, model_id="model@v1")
    assert len(encoder.encoded) == 3
    index = TextIndex.build(catalog, cache_dir=tmp_path, encoder=encoder, model_id="model@v1")
    assert index.dense_ready
    assert index.embeddings.dtype == np.float16
    assert not index.embeddings.flags.writeable
    with pytest.raises(ValueError):
        index.embeddings.flags.writeable = True
    assert np.allclose(np.linalg.norm(index.embeddings.astype(np.float32), axis=1), 1, atol=0.001)
    assert len(encoder.encoded) == 3
    changed = [dict(item) for item in catalog]
    changed[0]["description"] = "Nội dung thay đổi"
    prepare_embeddings(changed, cache_dir=tmp_path, encoder=encoder, model_id="model@v1")
    assert len(encoder.encoded) == 4
    prepare_embeddings(changed, cache_dir=tmp_path, encoder=encoder, model_id="model@v2")
    assert len(encoder.encoded) == 7


def test_invalid_encoder_vectors_never_become_cache(tmp_path, catalog):
    invalid = SimpleNamespace(encode_documents=lambda texts: np.full((len(texts), 3), np.nan))
    with pytest.raises(ValueError, match="finite"):
        prepare_embeddings(catalog, cache_dir=tmp_path, encoder=invalid, model_id="broken")
    assert not list(tmp_path.rglob("*.npy"))


def test_snapshot_and_results_own_catalog_and_keep_grounding(tmp_path, catalog):
    index = TextIndex.build(catalog, cache_dir=tmp_path)
    catalog[2]["visual_summary"] = "MUTATED"
    copy = index.documents
    copy[2]["visual_summary"] = "ALSO MUTATED"
    result = index.search("bình hoa")[0]
    assert result["id"] == "ep1"
    assert result["title"] == "Tập 1"
    assert result["startMs"] == 520_000
    assert result["calibratedScore"] is None
    assert result["matchPercentage"] is None
    assert "Jadoo làm vỡ bình hoa" in result["evidence"][0]["text"]
    result["genres"].append("MUTATED")
    assert "MUTATED" not in index.search("bình hoa")[0]["genres"]


def test_number_filters_are_hard_and_negations_do_not_become_positive(tmp_path, catalog):
    index = TextIndex.build(catalog, cache_dir=tmp_path)
    assert {item["episodeId"] for item in index.search("mùa 2 tập 1")} == {"ep1"}
    assert index.search("S02E999") == []
    assert all(item["episodeId"] != "ep10" for item in index.search("bình hoa, không phải tập 10"))
    assert index.search("bình hoa", constraints={"exclude_genres": ["animation"]}) == []
    assert index.search("bình hoa", constraints={"year_min": 2021}) == []


def test_accented_queries_distinguish_minimal_pairs_and_folded_queries_find_both(tmp_path):
    catalog = [{"id": "pillar", "title": "Trụ"}, {"id": "shelter", "title": "Trú"}]
    index = TextIndex.build(catalog, cache_dir=tmp_path)

    assert [item["id"] for item in index.search("trú")] == ["shelter"]
    assert [item["id"] for item in index.search("TRU\u0323")] == ["pillar"]
    assert {item["id"] for item in index.search("tru")} == {"pillar", "shelter"}


@pytest.mark.parametrize("term", ["trú", "trụ", "tru\u0301"])
def test_accented_tru_words_do_not_negate_following_episode_number(tmp_path, term):
    catalog = [
        {"id": "ep1", "title": "Trú và trụ", "item_type": "episode", "episode_number": 1},
        {"id": "ep2", "title": "Trú và trụ", "item_type": "episode", "episode_number": 2},
    ]
    index = TextIndex.build(catalog, cache_dir=tmp_path)

    assert [item["id"] for item in index.search(f"{term} tập 1")] == ["ep1"]
    assert [item["id"] for item in index.search(f"{term} trừ tập 1")] == ["ep2"]
    assert [item["id"] for item in index.search(f"{term} tru tap 1")] == ["ep2"]


def test_dialogue_windows_only_from_eligible_episodes(tmp_path, catalog):
    catalog[0]["primary_media_asset_id"] = "asset1"
    payload = {"text_tracks": [
        {"id": "t1", "media_asset_id": "asset1", "cues": [
            {"start_ms": 100_000, "end_ms": 103_000, "text": "mật khẩu cà rốt"}]},
        {"id": "private", "media_asset_id": "hidden", "cues": [
            {"start_ms": 0, "end_ms": 1000, "text": "bí mật riêng tư"}]},
    ], "media_assets": [{"id": "asset1", "access_policy": "public", "enabled": True}]}
    index = TextIndex.build(catalog, cache_dir=tmp_path, payload=payload)
    result = index.search("mật khẩu cà rốt")[0]
    assert result["episodeId"] == "ep1"
    assert result["startMs"] == 100_000
    assert "mật khẩu cà rốt" in result["evidence"][0]["text"]
    assert index.search("riêng tư") == []


def test_search_requires_a_ready_snapshot_and_preserves_captured_index(tmp_path, catalog):
    service = SearchService()
    assert service.search(None, "bình hoa") == []
    index = TextIndex.build(catalog, cache_dir=tmp_path)
    snapshot = SimpleNamespace(is_ready=True, hybrid_index=index)
    assert service.search(snapshot, "bình hoa")[0]["episodeId"] == "ep1"


def test_dimension_mismatch_fails_without_publishing_matrix(tmp_path, catalog):
    encoder = Encoder()
    prepare_embeddings(catalog[:1], cache_dir=tmp_path, encoder=encoder, model_id="model@v1")
    invalid = SimpleNamespace(encode_documents=lambda texts: np.ones((len(texts), 2)))
    with pytest.raises(ValueError, match="dimension"):
        prepare_embeddings(catalog, cache_dir=tmp_path, encoder=invalid, model_id="model@v1")


def test_corrupt_cache_is_rejected_before_snapshot_build(tmp_path, catalog):
    encoder = Encoder()
    prepare_embeddings(catalog, cache_dir=tmp_path, encoder=encoder, model_id="model@v1")
    path = next(tmp_path.rglob("documents/*.npy"))
    np.save(path, np.ones((2, 3)), allow_pickle=False)
    with pytest.raises(ValueError, match="one-dimensional"):
        TextIndex.build(catalog, cache_dir=tmp_path, encoder=encoder, model_id="model@v1")


def test_finite_non_normalized_cached_vector_is_rejected(tmp_path, catalog):
    encoder = Encoder()
    prepare_embeddings(catalog, cache_dir=tmp_path, encoder=encoder, model_id="model@v1")
    path = next(tmp_path.rglob("documents/*.npy"))
    np.save(path, np.array([20.0, 0.0, 0.0], dtype=np.float16), allow_pickle=False)
    with pytest.raises(ValueError, match="normalized"):
        TextIndex.build(catalog, cache_dir=tmp_path, encoder=encoder, model_id="model@v1")


def test_results_keep_legacy_timestamps_and_serialize_unknown_year(tmp_path, catalog):
    from schemas import MovieItem

    catalog[0]["year"] = None
    result = TextIndex.build(catalog, cache_dir=tmp_path).search("bình hoa")[0]
    parsed = MovieItem(**result)
    assert parsed.year == 0
    assert parsed.start_ms == parsed.startMs == 520_000


def test_reranker_calibration_cannot_be_applied_to_lexical_scores(tmp_path, catalog):
    calibration = SimpleNamespace(score_type="reranker")
    with pytest.raises(ValueError, match="score stage"):
        TextIndex.build(catalog, cache_dir=tmp_path).search("bình hoa", calibration=calibration)


@pytest.mark.parametrize("asset_patch", [
    {"access_policy": "private"}, {"access_policy": "authenticated"}, {"enabled": False},
    {"record": {"status": "draft"}}, {"record": {"status": "archived"}},
])
def test_private_or_unpublished_media_cues_never_enter_search(tmp_path, catalog, asset_patch):
    catalog[0]["primary_media_asset_id"] = "asset1"
    asset = {"id": "asset1", "access_policy": "public", "enabled": True, **asset_patch}
    payload = {"media_assets": [asset], "text_tracks": [{"id": "t1", "media_asset_id": "asset1", "cues": [
        {"start_ms": 100, "end_ms": 500, "text": "credential secretos"}]}]}
    index = TextIndex.build(catalog, cache_dir=tmp_path, payload=payload)
    assert index.search("credential secretos") == []
    assert all("credential secretos" not in item.get("dialogue_summary", "") for item in index.documents)


def test_unknown_asset_or_draft_track_cues_are_not_indexed(tmp_path, catalog):
    catalog[0]["primary_media_asset_id"] = "asset1"
    track = {"id": "t1", "media_asset_id": "asset1", "cues": [
        {"start_ms": 100, "end_ms": 500, "text": "unpublished secreto"}]}
    assert TextIndex.build(catalog, cache_dir=tmp_path, payload={"text_tracks": [track]}).search("secreto") == []
    track["record"] = {"status": "draft"}
    payload = {"media_assets": [{"id": "asset1", "access_policy": "public"}], "text_tracks": [track]}
    assert TextIndex.build(catalog, cache_dir=tmp_path, payload=payload).search("secreto") == []


def test_cue_coverage_is_episode_specific_and_keeps_both_timelines(tmp_path, catalog):
    catalog[0]["primary_media_asset_id"] = catalog[1]["primary_media_asset_id"] = "compilation"
    payload = {"media_assets": [{"id": "compilation", "access_policy": "public", "coverage": [
        {"episode_id": "ep1", "source_in_ms": 100_000, "source_out_ms": 160_000, "episode_in_ms": 10_000},
        {"episode_id": "ep10", "source_in_ms": 200_000, "source_out_ms": 260_000, "episode_in_ms": 0},
    ]}], "text_tracks": [{"id": "t1", "media_asset_id": "compilation", "cues": [
        {"start_ms": 120_000, "end_ms": 123_000, "text": "quả cà tím"},
        {"start_ms": 220_000, "end_ms": 223_000, "text": "cây bắp cải"},
    ]}]}
    index = TextIndex.build(catalog, cache_dir=tmp_path, payload=payload)
    result = index.search("quả cà tím")[0]
    assert result["episodeId"] == "ep1"
    assert result["startMs"] == 30_000
    assert result["start_ms"] == 120_000
    assert result["evidence"][0]["sourceStartMs"] == 120_000
    assert result["evidence"][0]["mediaAssetId"] == "compilation"
    assert index.search("cây bắp cải")[0]["episodeId"] == "ep10"
    assert all(item["episodeId"] != "ep10" for item in index.search("quả cà tím"))


def test_scene_grouped_episode_time_maps_from_source_coverage(tmp_path, catalog):
    catalog[2]["media_asset_id"] = "asset1"
    payload = {"media_assets": [{"id": "asset1", "access_policy": "public", "coverage": [
        {"episode_id": "ep1", "source_in_ms": 500_000, "source_out_ms": 560_000, "episode_in_ms": 0},
    ]}]}
    result = TextIndex.build(catalog, cache_dir=tmp_path, payload=payload).search("bình hoa")[0]
    assert result["startMs"] == 20_000
    assert result["start_ms"] == 520_000
    assert result["evidence"][0]["sourceStartMs"] == 520_000
