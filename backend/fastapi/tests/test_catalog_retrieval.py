"""
=============================================================================
CATALOG-01 UNIT & INTEGRATION TEST SUITE: Catalog Retrieval & CineBot Integration
=============================================================================
Coverage requirements:
1. Multi-level catalog flattening (series, episodes, segments, scenes).
2. Retrieval by series title, episode title, character alias, plot fact memory, scene description.
3. Hard constraint filtering (genre exclusion, year range).
4. Comparative constraint evaluation and explicit diagnostics when trait missing.
5. Grounded Stage 5 explanation (plot facts, characters, scene timestamps).
6. FastAPI endpoints integration (/api/index/sync, /api/chat, /v1/discover, /api/recommend).
=============================================================================
"""

import os
import sys
import json
import unittest
from pathlib import Path
from typing import Dict, Any
from unittest.mock import patch

FASTAPI_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(FASTAPI_DIR))

from services.catalog_sync import CatalogSyncManager, catalog_sync_manager
from services.hybrid_retrieval import HybridMovieIndex
from services.ai_pipeline import (
    CascadingAIPipeline,
    cascading_pipeline,
    evaluate_comparative_constraints,
)
from schemas import IndexSyncRequest, ChatRequest, DiscoverRequest, RecommendRequest
from fastapi.testclient import TestClient
from main import app


SAMPLE_TEST_CATALOG: Dict[str, Any] = {
    "schema_version": "dippie.catalog.v1",
    "package": {
        "id": "pkg_test_01",
        "revision": 1,
        "created_at": "2026-10-16T00:00:00Z",
        "default_language": "vi",
        "import_mode": "upsert",
        "reference_scope": "self_contained",
        "description": "Test catalog fixture for CATALOG-01 retrieval."
    },
    "genres": [
        {
            "id": "animation",
            "labels": [{"language": "vi", "text": "Hoạt hình"}, {"language": "en", "text": "Animation"}],
            "aliases": ["anime", "cartoon"]
        },
        {
            "id": "comedy",
            "labels": [{"language": "vi", "text": "Hài"}, {"language": "en", "text": "Comedy"}],
            "aliases": ["hai huoc"]
        },
        {
            "id": "sci-fi",
            "labels": [{"language": "vi", "text": "Khoa học viễn tưởng"}, {"language": "en", "text": "Sci-Fi"}],
            "aliases": ["vien tuong"]
        },
        {
            "id": "horror",
            "labels": [{"language": "vi", "text": "Kinh dị"}, {"language": "en", "text": "Horror"}],
            "aliases": ["rung ron"]
        }
    ],
    "attribute_scales": [
        {
            "id": "darkness_v1",
            "name": "Mức u tối",
            "definition": "Thang đo mức độ đen tối/u ám từ 0 đến 4.",
            "minimum": 0,
            "maximum": 4,
            "levels": [
                {"value": 0, "meaning": "Tươi sáng"},
                {"value": 1, "meaning": "Nhẹ"},
                {"value": 2, "meaning": "Vừa"},
                {"value": 3, "meaning": "Nặng"},
                {"value": 4, "meaning": "Rất u tối"}
            ]
        },
        {
            "id": "pacing_v1",
            "name": "Nhịp kể",
            "definition": "Thang đo nhịp kể chuyện từ 0 đến 4.",
            "minimum": 0,
            "maximum": 4,
            "levels": [
                {"value": 0, "meaning": "Rất chậm"},
                {"value": 1, "meaning": "Chậm"},
                {"value": 2, "meaning": "Vừa"},
                {"value": 3, "meaning": "Nhanh"},
                {"value": 4, "meaning": "Rất dồn dập"}
            ]
        }
    ],
    "sources": [],
    "characters": [
        {
            "id": "char_bao",
            "series_ids": ["ser_chronicles"],
            "name": "Bảo Thần Tốc",
            "aliases": ["Tiểu Bảo", "Bao The Swift", "Tia Chớp Nhỏ"],
            "description": "Cậu bé giao hàng dũng cảm mang bảo vật xuyên không gian.",
            "role": "main",
            "traits": ["brave", "fast"]
        },
        {
            "id": "char_chi",
            "series_ids": ["ser_chronicles"],
            "name": "Chi Công Nghệ",
            "aliases": ["Hacker Chi", "Chi Chi"],
            "description": "Nhà khoa học trẻ giải mã tín hiệu vệ tinh cổ.",
            "role": "main",
            "traits": ["smart"]
        }
    ],
    "series": [
        {
            "id": "ser_chronicles",
            "title": "Biên Niên Sử Dippie",
            "aliases": ["Dippie Chronicles", "Biên Niên Sử Vũ Trụ"],
            "synopsis": "Hành trình khám phá các hành tinh bí ẩn của nhóm bạn trẻ Dippie.",
            "genre_ids": ["animation", "sci-fi"],
            "keywords": ["vũ trụ", "phiêu lưu", "khám phá"],
            "themes": ["tình bạn", "trách nhiệm"],
            "character_ids": ["char_bao", "char_chi"],
            "release_year_start": 2026,
            "attributes": [
                {"scale_id": "darkness_v1", "value": None},
                {"scale_id": "pacing_v1", "value": 3}
            ]
        },
        {
            "id": "ser_spooky",
            "title": "Ngôi Nhà Bí Ẩn",
            "aliases": ["Spooky Mansion"],
            "synopsis": "Những câu chuyện rùng rợn kỳ quái trong ngôi nhà bỏ hoang.",
            "genre_ids": ["animation", "horror"],
            "keywords": ["ma quái", "bóng tối"],
            "themes": ["nỗi sợ"],
            "character_ids": [],
            "release_year_start": 2018,
            "attributes": [
                {"scale_id": "darkness_v1", "value": 4},
                {"scale_id": "pacing_v1", "value": 1}
            ]
        }
    ],
    "seasons": [
        {
            "id": "sea_01",
            "series_id": "ser_chronicles",
            "number": 1,
            "title": "Mùa 1: Tín Hiệu Đầu Tiên"
        }
    ],
    "episodes": [
        {
            "id": "ep_chronicles_01",
            "series_id": "ser_chronicles",
            "season_id": "sea_01",
            "number": 1,
            "title": "Bình Minh Trên Sao Hỏa",
            "aliases": ["Mars Sunrise", "Tập 1 Bình Minh"],
            "release_date": "2026-03-01",
            "duration_ms": 1320000,
            "synopsis": "Bảo và Chi hạ cánh xuống căn cứ Sao Hỏa và phát hiện máy bay không người lái bị hỏng.",
            "genre_ids": ["animation", "sci-fi"],
            "keywords": ["sao hỏa", "hạ cánh"],
            "themes": ["khám phá"],
            "character_ids": ["char_bao", "char_chi"],
            "plot_facts": [
                {
                    "id": "fact_ep01_01",
                    "text": "Bảo tìm thấy chiếc chìa khóa năng lượng nguyên thủy giấu dưới đáy hố thiên thạch."
                }
            ],
            "attributes": [
                {"scale_id": "darkness_v1", "value": None},
                {"scale_id": "pacing_v1", "value": 3}
            ]
        },
        {
            "id": "ep_spooky_01",
            "series_id": "ser_spooky",
            "season_id": "sea_spooky_01",
            "number": 1,
            "title": "Đêm Trăng Máu",
            "release_date": "2018-10-31",
            "duration_ms": 1200000,
            "synopsis": "Một đêm kinh hoàng khi bóng ma xuất hiện trong gương lúc nửa đêm.",
            "genre_ids": ["animation", "horror"],
            "keywords": ["trăng máu", "ma quái"],
            "themes": ["ác mộng"],
            "character_ids": [],
            "plot_facts": [
                {"id": "fact_spooky_01", "text": "Chiếc gương cổ phản chiếu một hành lang không có lối ra."}
            ],
            "attributes": [
                {"scale_id": "darkness_v1", "value": 4},
                {"scale_id": "pacing_v1", "value": 2}
            ]
        }
    ],
    "segments": [
        {
            "id": "seg_chronicles_01a",
            "episode_id": "ep_chronicles_01",
            "title": "Vượt Qua Bão Cát Sao Hỏa",
            "aliases": ["Mars Sandstorm Passage"],
            "synopsis": "Bảo lái xe địa hình chở Chi vượt qua cơn bão cát khổng lồ đang quét qua hẻm núi.",
            "episode_start_ms": 60000,
            "episode_end_ms": 360000,
            "character_ids": ["char_bao"],
            "keywords": ["bão cát", "hẻm núi"],
            "themes": ["nguy hiểm"],
            "plot_facts": [
                {"id": "fact_seg01_01", "text": "Cơn bão cát làm tê liệt hệ thống radar dẫn đường của xe địa hình."}
            ],
            "attributes": [
                {"scale_id": "darkness_v1", "value": None},
                {"scale_id": "pacing_v1", "value": 4}
            ]
        }
    ],
    "media_assets": [
        {
            "id": "asset_mars_ep01",
            "content_type": "video",
            "role": "feature",
            "duration_ms": 1320000,
            "coverage": [
                {
                    "episode_id": "ep_chronicles_01",
                    "sequence": 1,
                    "source_in_ms": 0,
                    "source_out_ms": 1320000,
                    "episode_in_ms": 0,
                    "scope": "full_episode"
                }
            ]
        }
    ],
    "text_tracks": [
        {
            "id": "track_ep01_vi",
            "media_asset_id": "asset_mars_ep01",
            "language": "vi",
            "cues": [
                {
                    "id": "cue_01",
                    "start_ms": 75000,
                    "end_ms": 82000,
                    "text": "Bão cát đang đến rất gần! Giữ chắc tay lái, Bảo!"
                }
            ]
        }
    ],
    "scenes": [
        {
            "id": "scene_mars_canyon",
            "episode_id": "ep_chronicles_01",
            "segment_id": "seg_chronicles_01a",
            "media_asset_id": "asset_mars_ep01",
            "start_ms": 70000,
            "end_ms": 95000,
            "title": "Cú Nhảy Vực Thẳm",
            "visual_description": "Chiếc xe địa hình phóng qua bờ vực sâu khi những tảng đá đỏ sạt lở dữ dội.",
            "character_ids": ["char_bao", "char_chi"],
            "keywords": ["nhảy vực", "đá đỏ", "hẻm núi"],
            "themes": ["sinh tồn"],
            "sound_events": ["tiếng động cơ gầm", "tiếng đá rơi"],
            "attributes": [
                {"scale_id": "darkness_v1", "value": None},
                {"scale_id": "pacing_v1", "value": 4}
            ]
        }
    ]
}


class TestCatalogRetrievalSuite(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Exercise the lexical retrieval and normalization paths without model downloads.
        from services.qwen_service import qwen_service
        cls.encoder_patch = patch("services.hybrid_retrieval.DenseEncoder.load")
        cls.intent_patch = patch.object(
            qwen_service, "parse_discovery_intent",
            side_effect=lambda query, history=None, catalog=None: qwen_service.normalize_phase23_intent({}, query, catalog),
        )
        cls.encoder_patch.start()
        cls.intent_patch.start()
        cls.addClassCleanup(cls.encoder_patch.stop)
        cls.addClassCleanup(cls.intent_patch.stop)
        # Sync test fixture into manager and index
        cls.manager = CatalogSyncManager()
        cls.counts = cls.manager.load_from_payload(SAMPLE_TEST_CATALOG)
        cls.flattened = cls.manager.get_flattened_catalog()

        # Build index over the flattened catalog
        cls.hybrid_index = HybridMovieIndex()
        cls.hybrid_index.build_from_catalog(cls.flattened, save_to_disk=False)

        # Set up global manager with sample data
        catalog_sync_manager.load_from_payload(SAMPLE_TEST_CATALOG)
        cascading_pipeline.retrieval_node.hybrid_index = cls.hybrid_index
        cls.client = TestClient(app)

    # -------------------------------------------------------------------------
    # 1. Multi-level catalog flattening verification
    # -------------------------------------------------------------------------
    def test_01_catalog_flattening_entities(self):
        self.assertEqual(self.counts["series"], 2)
        self.assertEqual(self.counts["episodes"], 2)
        self.assertEqual(self.counts["segments"], 1)
        self.assertEqual(self.counts["scenes"], 1)
        self.assertEqual(self.counts["total"], 6)

        # Verify Series item structure
        series_item = self.manager.get_item_by_id("ser_chronicles")
        self.assertIsNotNone(series_item)
        self.assertEqual(series_item["title"], "Biên Niên Sử Dippie")
        self.assertIn("Dippie Chronicles", series_item["aliases"])
        self.assertIn("Bảo Thần Tốc", series_item["characters"])
        self.assertIn("Tiểu Bảo", series_item["characters"])
        self.assertEqual(series_item["release_year"], 2026)
        self.assertEqual(series_item["item_type"], "series")

        # Verify Episode item structure
        ep_item = self.manager.get_item_by_id("ep_chronicles_01")
        self.assertIsNotNone(ep_item)
        self.assertEqual(ep_item["series_id"], "ser_chronicles")
        self.assertEqual(ep_item["season_id"], "sea_01")
        self.assertEqual(ep_item["episode_number"], 1)
        self.assertEqual(ep_item["primary_media_asset_id"], "asset_mars_ep01")
        self.assertTrue(len(ep_item["plot_facts"]) > 0)
        self.assertIn("Bảo tìm thấy chiếc chìa khóa năng lượng nguyên thủy", ep_item["plot_facts"][0])

        # Verify Segment item structure
        seg_item = self.manager.get_item_by_id("seg_chronicles_01a")
        self.assertIsNotNone(seg_item)
        self.assertEqual(seg_item["episode_id"], "ep_chronicles_01")
        self.assertEqual(seg_item["start_ms"], 60000)
        self.assertEqual(seg_item["end_ms"], 360000)

        # Verify Scene item structure
        scene_item = self.manager.get_item_by_id("scene_mars_canyon")
        self.assertIsNotNone(scene_item)
        self.assertEqual(scene_item["episode_id"], "ep_chronicles_01")
        self.assertEqual(scene_item["media_asset_id"], "asset_mars_ep01")
        self.assertIn("Chiếc xe địa hình phóng qua bờ vực sâu", scene_item["visual_summary"])
        self.assertIn("tiếng động cơ gầm", scene_item["sound_events"])

    # -------------------------------------------------------------------------
    # 2. Retrieval by Series Title
    # -------------------------------------------------------------------------
    def test_02_retrieval_by_series_title(self):
        query = "Biên Niên Sử Dippie"
        results = self.hybrid_index.search_hybrid(
            query_text=query,
            nlu_intent={"query": {"text": query}},
            catalog=self.flattened
        )
        self.assertTrue(len(results) > 0)
        top_item = results[0]["movie"]
        self.assertEqual(top_item["id"], "ser_chronicles")
        self.assertEqual(top_item["item_type"], "series")

    # -------------------------------------------------------------------------
    # 3. Retrieval by Episode Title
    # -------------------------------------------------------------------------
    def test_03_retrieval_by_episode_title(self):
        query = "Bình Minh Trên Sao Hỏa"
        results = self.hybrid_index.search_hybrid(
            query_text=query,
            nlu_intent={"query": {"text": query}},
            catalog=self.flattened
        )
        self.assertTrue(len(results) > 0)
        top_ids = [r["movie"]["id"] for r in results[:2]]
        self.assertIn("ep_chronicles_01", top_ids)

    # -------------------------------------------------------------------------
    # 4. Retrieval by Character Alias
    # -------------------------------------------------------------------------
    def test_04_retrieval_by_character_alias(self):
        # Character alias: "Tiểu Bảo" or "Hacker Chi"
        query = "Tìm nội dung có nhân vật Tiểu Bảo và Hacker Chi"
        results = self.hybrid_index.search_hybrid(
            query_text=query,
            nlu_intent={"query": {"text": query}},
            catalog=self.flattened
        )
        self.assertTrue(len(results) > 0)
        top_item = results[0]["movie"]
        # Must match an item that features Bảo or Chi
        chars = [c.lower() for c in top_item.get("characters", [])]
        self.assertTrue(any("bảo" in c or "chi" in c for c in chars))

    def test_character_alias_with_year_filter(self):
        query = "tìm phim có nhân vật Tiểu Bảo trước năm 2030"
        results = self.hybrid_index.search_hybrid(
            query_text=query, nlu_intent={"query": {"text": query}}, catalog=self.flattened
        )
        self.assertTrue(results)
        self.assertIn("Tiểu Bảo", results[0]["movie"]["characters"])

    def test_character_alias_does_not_validate_fabricated_plot(self):
        query = "Tiểu Bảo lái tàu ngầm xuống đáy đại dương săn khủng long"
        results = self.hybrid_index.search_hybrid(
            query_text=query, nlu_intent={"query": {"text": query}}, catalog=self.flattened
        )
        self.assertEqual(results, [])

    # -------------------------------------------------------------------------
    # 5. Retrieval by Plot Fact Memory
    # -------------------------------------------------------------------------
    def test_05_retrieval_by_plot_fact_memory(self):
        query = "Tìm tập phim mà nhân vật tìm thấy chiếc chìa khóa năng lượng nguyên thủy dưới đáy hố thiên thạch"
        results = self.hybrid_index.search_hybrid(
            query_text=query,
            nlu_intent={"query": {"text": query}},
            catalog=self.flattened
        )
        self.assertTrue(len(results) > 0)
        top_item = results[0]["movie"]
        self.assertEqual(top_item["id"], "ep_chronicles_01")
        self.assertTrue(any("chìa khóa năng lượng" in str(f) for f in top_item.get("plot_facts", [])))

    # -------------------------------------------------------------------------
    # 6. Retrieval by Scene Description
    # -------------------------------------------------------------------------
    def test_06_retrieval_by_scene_description(self):
        query = "cảnh xe địa hình phóng qua bờ vực sâu đá đỏ sạt lở"
        results = self.hybrid_index.search_hybrid(
            query_text=query,
            nlu_intent={"query": {"text": query}},
            catalog=self.flattened
        )
        self.assertTrue(len(results) > 0)
        top_item = results[0]["movie"]
        self.assertEqual(top_item["id"], "scene_mars_canyon")
        self.assertEqual(top_item["item_type"], "scene")

    # -------------------------------------------------------------------------
    # 7. Hard Constraint Filtering: Genre Exclusion
    # -------------------------------------------------------------------------
    def test_07_hard_constraint_genre_exclusion(self):
        # Query for animation but exclude Horror
        query = "hoạt hình phiêu lưu"
        nlu_intent = {
            "query": {"text": query},
            "constraints": {
                "exclude_genres": ["Horror", "kinh dị"]
            }
        }
        results = self.hybrid_index.search_hybrid(
            query_text=query,
            nlu_intent=nlu_intent,
            catalog=self.flattened
        )
        result_ids = [r["movie"]["id"] for r in results]
        # ser_spooky and ep_spooky_01 must be completely excluded
        self.assertNotIn("ser_spooky", result_ids)
        self.assertNotIn("ep_spooky_01", result_ids)

    # -------------------------------------------------------------------------
    # 8. Hard Constraint Filtering: Year Range
    # -------------------------------------------------------------------------
    def test_08_hard_constraint_year_filtering(self):
        # Filter for year >= 2025
        query = "phim hoạt hình"
        nlu_intent = {
            "query": {"text": query},
            "constraints": {
                "year_min": 2025
            }
        }
        results = self.hybrid_index.search_hybrid(
            query_text=query,
            nlu_intent=nlu_intent,
            catalog=self.flattened
        )
        for r in results:
            m = r["movie"]
            m_year = m.get("year") or m.get("release_year")
            if m_year and m_year > 0:
                self.assertGreaterEqual(m_year, 2025)

        # ser_spooky (2018) must not appear
        result_ids = [r["movie"]["id"] for r in results]
        self.assertNotIn("ser_spooky", result_ids)
        self.assertNotIn("ep_spooky_01", result_ids)

    # -------------------------------------------------------------------------
    # 9. Comparative Constraint Diagnostics when Trait is Missing
    # -------------------------------------------------------------------------
    def test_09_comparative_constraint_diagnostics_when_trait_missing(self):
        # ep_chronicles_01 has darkness_v1 = null (uncalibrated / missing)
        ep_item = self.manager.get_item_by_id("ep_chronicles_01")
        self.assertIsNotNone(ep_item)

        nlu_intent = {
            "query": {"text": "Gợi ý tập phim u tối hơn"},
            "constraints": {"darkness": "high"}
        }

        score_delta, diagnostics = evaluate_comparative_constraints(
            item=ep_item,
            nlu_output=nlu_intent,
            query_text="Gợi ý tập phim u tối hơn"
        )

        # Must report explicit diagnostics that trait data is missing
        self.assertIn("darkness", diagnostics["missing_traits"])
        self.assertTrue(len(diagnostics["trait_diagnostics"]) > 0)
        diag_msg = diagnostics["trait_diagnostics"][0]["message"]
        self.assertIn("darkness_v1", diag_msg)
        self.assertEqual(diagnostics["trait_diagnostics"][0]["status"], "missing_trait_data")

    # -------------------------------------------------------------------------
    # 10. Comparative Constraint Evaluation when Trait is Present
    # -------------------------------------------------------------------------
    def test_10_comparative_constraint_evaluation_when_trait_present(self):
        # ep_spooky_01 has darkness_v1 = 4 (calibrated)
        spooky_item = self.manager.get_item_by_id("ep_spooky_01")
        self.assertIsNotNone(spooky_item)

        nlu_intent = {
            "query": {"text": "nội dung đen tối u ám"},
            "constraints": {"darkness": "high"}
        }

        score_delta, diagnostics = evaluate_comparative_constraints(
            item=spooky_item,
            nlu_output=nlu_intent,
            query_text="nội dung đen tối u ám"
        )

        # Must evaluate successfully without missing trait
        self.assertNotIn("darkness", diagnostics["missing_traits"])
        self.assertTrue(score_delta > 0.0)
        self.assertEqual(diagnostics["evaluated_traits"][0]["status"], "evaluated")
        self.assertEqual(diagnostics["evaluated_traits"][0]["value"], 4.0)

    # -------------------------------------------------------------------------
    # 11. Grounded Stage 5 Explanation Verification
    # -------------------------------------------------------------------------
    def test_11_grounded_stage_5_explanation(self):
        pipeline = CascadingAIPipeline()
        pipeline.retrieval_node.hybrid_index = self.hybrid_index

        result = pipeline.run(
            query="cảnh nhảy vực sâu của xe địa hình",
            catalog=self.flattened
        )

        explanation = result["text"]
        self.assertTrue(len(explanation) > 0)

        # Verify grounding on scene timestamp, character, and visual detail
        self.assertTrue(
            "01:10–01:35" in explanation or "xe địa hình" in explanation or "Bảo Thần Tốc" in explanation
        )

    # -------------------------------------------------------------------------
    # 12. FastAPI Endpoints Integration (/api/index/sync, /api/chat, /v1/discover, /api/recommend)
    # -------------------------------------------------------------------------
    def test_12_fastapi_endpoints_sync_and_serve_real_catalog(self):
        import main
        old_secret = main.FASTAPI_SYNC_SECRET
        old_gen = getattr(main, "_current_sync_generation", 0)
        old_hash = getattr(main, "_current_sync_hash", "")
        old_state_content = None
        if hasattr(main, "SYNC_STATE_PATH") and main.SYNC_STATE_PATH.exists():
            try:
                old_state_content = main.SYNC_STATE_PATH.read_text(encoding="utf-8")
            except Exception:
                old_state_content = None

        main._current_sync_generation = 0
        main._current_sync_hash = ""

        try:
            # 1a. Missing configuration fail-closed check (503)
            main.FASTAPI_SYNC_SECRET = ""
            missing_cfg_resp = self.client.post("/api/index/sync", json={"catalog": SAMPLE_TEST_CATALOG})
            self.assertEqual(missing_cfg_resp.status_code, 503)

            # Configure test secret
            test_token = "test-internal-sync-secret-2026"
            main.FASTAPI_SYNC_SECRET = test_token

            # 1b. Unauthorized access without service token must be rejected (401)
            unauth_resp = self.client.post("/api/index/sync", json={"catalog": SAMPLE_TEST_CATALOG})
            self.assertEqual(unauth_resp.status_code, 401)

            # 1c. Forbidden access with bad token must be rejected (403)
            bad_token_resp = self.client.post("/api/index/sync", json={"catalog": SAMPLE_TEST_CATALOG}, headers={"X-Service-Token": "invalid-token"})
            self.assertEqual(bad_token_resp.status_code, 403)

            # 1d. Authorized access with valid service token succeeds (200)
            sync_resp = self.client.post(
                "/api/index/sync",
                json={"catalog": SAMPLE_TEST_CATALOG, "generation": 10},
                headers={"X-Service-Token": test_token}
            )
            self.assertEqual(sync_resp.status_code, 200)
            sync_data = sync_resp.json()
            self.assertEqual(sync_data["status"], "success")
            self.assertEqual(sync_data["item_counts"]["total"], 6)

            # 1e. Stale generation must be safely skipped (SKIPPED)
            stale_resp = self.client.post(
                "/api/index/sync",
                json={"catalog": SAMPLE_TEST_CATALOG, "generation": 5},
                headers={"X-Service-Token": test_token}
            )
            self.assertEqual(stale_resp.status_code, 200)
            self.assertEqual(stale_resp.json()["status"], "SKIPPED")
        finally:
            main.FASTAPI_SYNC_SECRET = old_secret
            main._current_sync_generation = old_gen
            main._current_sync_hash = old_hash
            if hasattr(main, "SYNC_STATE_PATH"):
                if old_state_content is not None:
                    main.SYNC_STATE_PATH.write_text(old_state_content, encoding="utf-8")
                elif main.SYNC_STATE_PATH.exists():
                    try:
                        main.SYNC_STATE_PATH.unlink()
                    except Exception:
                        pass

        # 2. POST /api/chat with real catalog query
        chat_resp = self.client.post("/api/chat", json={
            "query": "Tìm phân cảnh xe địa hình nhảy qua hẻm núi"
        })
        self.assertEqual(chat_resp.status_code, 200)
        chat_data = chat_resp.json()
        self.assertTrue(len(chat_data["recommendedMovies"]) > 0)
        # Top result should be from real catalog (e.g. scene_mars_canyon or chronicles)
        top_rec = chat_data["recommendedMovies"][0]
        self.assertIn("scene_mars_canyon", [m["id"] for m in chat_data["recommendedMovies"]])
        self.assertTrue(len(chat_data["text"]) > 0)

        # 3. POST /v1/discover
        disc_resp = self.client.post("/v1/discover", json={
            "query": "Biên Niên Sử Dippie"
        })
        self.assertEqual(disc_resp.status_code, 200)
        disc_data = disc_resp.json()
        self.assertIn("structuredIntent", disc_data)
        disc_ids = [r["id"] for r in disc_data["results"]]
        self.assertTrue(any("chronicles" in i or "mars" in i for i in disc_ids))

        # 4. POST /api/recommend
        rec_resp = self.client.post("/api/recommend", json={
            "genres": ["Sci-Fi"],
            "limit": 3
        })
        self.assertEqual(rec_resp.status_code, 200)
        rec_data = rec_resp.json()
        self.assertTrue(len(rec_data["recommendedMovies"]) > 0)
        # Verify recommended items come from real catalog
        rec_ids = [m["id"] for m in rec_data["recommendedMovies"]]
        self.assertTrue(any("chronicles" in i or "mars" in i for i in rec_ids))


if __name__ == "__main__":
    unittest.main()
