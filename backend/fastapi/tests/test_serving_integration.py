"""
=============================================================================
SERVE-01 FULL-MODEL GPU INTEGRATION TEST SUITE
=============================================================================
Chỉ chạy khi có cờ RUN_FULL_INTEGRATION=1 và GPU NVIDIA với VRAM khả dụng.
Không chạy tự động trong suite unit test offline để tránh chiếm GPU thứ hai
hoặc tải model trùng lặp.
=============================================================================
"""

import os
import sys
import time
import json
import unittest
from pathlib import Path

FASTAPI_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(FASTAPI_DIR))


@unittest.skipUnless(
    os.getenv("RUN_FULL_INTEGRATION") == "1",
    "Bỏ qua integration tests khi chạy offline. Đặt RUN_FULL_INTEGRATION=1 để kích hoạt kiểm thử với GPU thật."
)
class TestServingFullModelIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import torch
        if not torch.cuda.is_available():
            raise unittest.SkipTest("CUDA không khả dụng trên máy này.")
        from services.qwen_service import QwenRecommendationService
        cls.service = QwenRecommendationService(
            serving_mode="full",
            device="cuda",
            enable_fallback=False
        )
        cls.service.load_model()

    def test_full_model_live_health_and_readiness(self):
        health = self.service.get_health_status()
        self.assertEqual(health["status"], "healthy")
        self.assertTrue(health["modelLoaded"])
        self.assertTrue(health["phase23AdapterLoaded"])
        self.assertEqual(health["servingMode"], "full")
        self.assertEqual(health["activeBaseModelName"], "Qwen/Qwen3-4B")
        self.assertIn("4bit-nf4", health["quantization"])

        is_ready, code, readiness = self.service.get_readiness_status()
        self.assertTrue(is_ready)
        self.assertEqual(code, 200)
        self.assertEqual(readiness["status"], "ready")

    def test_full_model_live_intent_generation(self):
        query = "Gợi ý cho tôi phim hoạt hình phiêu lưu trước năm 2010 không có kinh dị"
        t0 = time.time()
        intent = self.service.parse_discovery_intent(query)
        latency = time.time() - t0

        self.assertLess(latency, 120.0)
        self.assertEqual(intent["intent_type"], "DISCOVERY")
        self.assertEqual(intent["constraints"]["year_max"], 2009)
        self.assertIn("Animation", intent["constraints"]["include_genres"])
        self.assertIn("Horror", intent["constraints"]["exclude_genres"])


if __name__ == "__main__":
    unittest.main()
