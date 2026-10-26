"""
=============================================================================
SERVE-01 UNIT TEST SUITE: Qwen3-4B + Phase 23 LoRA Serving Gateway
=============================================================================
Coverage requirements:
1. Artifact tồn tại nhưng model chưa load.
2. Adapter thiếu hoặc không hợp lệ.
3. Full PEFT load thành công.
4. DEVICE=cpu khi máy có CUDA.
5. DEVICE=cuda khi CUDA không khả dụng.
6. NF4/dtype label đúng.
7. PEFT load thất bại, fallback tắt.
8. PEFT load thất bại, fallback bật và GGUF load thành công.
9. Cả full model và fallback đều thất bại.
10. Nhiều request khởi tạo không tạo load trùng.
11. Giới hạn inference/concurrency được thực thi.
12. Health/readiness đúng từng trạng thái.
=============================================================================
"""

import os
import sys
import json
import threading
import time
import unittest
import torch
from pathlib import Path
from typing import Optional
from unittest.mock import patch, MagicMock

# Đảm bảo import được backend/fastapi
FASTAPI_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(FASTAPI_DIR))

from services.qwen_service import (
    QwenRecommendationService,
    InferenceCapacityError,
    ModelNotReadyError,
    InferenceGenerationError,
    ModelOutputParseError,
    qwen_service,
)
from schemas import HealthResponse, ReadinessResponse
from fastapi.testclient import TestClient
from main import app


class TestServingGateway(unittest.TestCase):
    def setUp(self):
        # Đường dẫn adapter giả lập hoặc có sẵn
        self.valid_adapter_dir = str(FASTAPI_DIR / "../../ai/models/qwen3-4b-phase23-lora")

    # -------------------------------------------------------------------------
    # 1. Artifact tồn tại nhưng model chưa load
    # -------------------------------------------------------------------------
    def test_01_artifact_exists_but_model_not_loaded(self):
        service = QwenRecommendationService(
            serving_mode="full",
            phase23_adapter_dir=self.valid_adapter_dir
        )
        self.assertFalse(service.is_loaded)
        self.assertFalse(service.phase23_adapter_loaded)

        health = service.get_health_status()
        self.assertEqual(health["status"], "unhealthy")
        self.assertFalse(health["modelLoaded"])
        self.assertFalse(health["phase23AdapterLoaded"])
        self.assertEqual(health["activeInferenceBackend"], "uninitialized")

        is_ready, http_code, ready_data = service.get_readiness_status()
        self.assertFalse(is_ready)
        self.assertEqual(http_code, 503)
        self.assertEqual(ready_data["status"], "not_ready")

    # -------------------------------------------------------------------------
    # 2. Adapter thiếu hoặc không hợp lệ
    # -------------------------------------------------------------------------
    def test_02_adapter_missing_or_invalid(self):
        service = QwenRecommendationService(
            serving_mode="full",
            phase23_adapter_dir="invalid/non_existent/path",
            enable_fallback=False
        )
        with patch.object(service, "_resolve_phase23_adapter", return_value=None):
            service.load_model()

        self.assertFalse(service.is_loaded)
        self.assertFalse(service.phase23_adapter_loaded)
        self.assertIsNotNone(service.load_error)
        self.assertIn("Không tìm thấy adapter", service.load_error)
        self.assertEqual(service.active_inference_backend, "uninitialized")

    # -------------------------------------------------------------------------
    # 3. Full PEFT load thành công
    # -------------------------------------------------------------------------
    @patch("transformers.AutoTokenizer.from_pretrained")
    @patch("transformers.AutoModelForCausalLM.from_pretrained")
    @patch("peft.PeftModel.from_pretrained")
    @patch("torch.cuda.is_available", return_value=True)
    def test_03_full_peft_load_success(self, mock_cuda, mock_peft, mock_base, mock_tok):
        mock_model = MagicMock()
        mock_model.hf_device_map = {"model.layers.0": "cuda:0"}
        mock_peft.return_value = mock_model

        service = QwenRecommendationService(
            serving_mode="full",
            device="cuda",
            phase23_adapter_dir=self.valid_adapter_dir
        )
        fake_path = Path(self.valid_adapter_dir)
        with patch.object(service, "_resolve_phase23_adapter", return_value=fake_path):
            service.load_model()

        self.assertTrue(service.is_loaded)
        self.assertTrue(service.phase23_adapter_loaded)
        self.assertFalse(service.is_degraded)
        self.assertTrue(service.active_inference_backend.startswith("qwen3-4b-peft-lora-"))
        self.assertIn("cuda:0", service.actual_device)

        is_ready, http_code, ready_data = service.get_readiness_status()
        self.assertTrue(is_ready)
        self.assertEqual(http_code, 200)
        self.assertEqual(ready_data["status"], "ready")

    # -------------------------------------------------------------------------
    # 4. DEVICE=cpu khi máy có CUDA
    # -------------------------------------------------------------------------
    @patch("transformers.AutoTokenizer.from_pretrained")
    @patch("transformers.AutoModelForCausalLM.from_pretrained")
    @patch("peft.PeftModel.from_pretrained")
    @patch("torch.cuda.is_available", return_value=True)
    def test_04_device_cpu_enforced_when_cuda_available(self, mock_cuda, mock_peft, mock_base, mock_tok):
        service = QwenRecommendationService(
            serving_mode="full",
            device="cpu",
            phase23_adapter_dir=self.valid_adapter_dir
        )
        fake_path = Path(self.valid_adapter_dir)
        with patch.object(service, "_resolve_phase23_adapter", return_value=fake_path):
            service.load_model()

        self.assertTrue(service.is_loaded)
        self.assertTrue(service.phase23_adapter_loaded)
        self.assertEqual(service.actual_dtype, "float32")
        self.assertIn("cpu", service.actual_device)
        self.assertEqual(service.active_inference_backend, "qwen3-4b-peft-lora-float32")

    # -------------------------------------------------------------------------
    # 5. DEVICE=cuda khi CUDA không khả dụng
    # -------------------------------------------------------------------------
    @patch("torch.cuda.is_available", return_value=False)
    def test_05_device_cuda_when_cuda_not_available_fails(self, mock_cuda):
        service = QwenRecommendationService(
            serving_mode="full",
            device="cuda",
            enable_fallback=False,
            phase23_adapter_dir=self.valid_adapter_dir
        )
        fake_path = Path(self.valid_adapter_dir)
        with patch.object(service, "_resolve_phase23_adapter", return_value=fake_path):
            service.load_model()

        self.assertFalse(service.is_loaded)
        self.assertFalse(service.phase23_adapter_loaded)
        self.assertIsNotNone(service.load_error)
        self.assertIn("CUDA", service.load_error)
        self.assertEqual(service.active_inference_backend, "uninitialized")

    # -------------------------------------------------------------------------
    # 6. NF4/dtype label đúng
    # -------------------------------------------------------------------------
    @patch("transformers.AutoTokenizer.from_pretrained")
    @patch("transformers.AutoModelForCausalLM.from_pretrained")
    @patch("peft.PeftModel.from_pretrained")
    @patch("torch.cuda.is_available", return_value=True)
    def test_06_nf4_and_cpu_dtype_labels(self, mock_cuda, mock_peft, mock_base, mock_tok):
        fake_path = Path(self.valid_adapter_dir)

        # 6a. CUDA với bitsandbytes NF4
        with patch.dict("sys.modules", {"bitsandbytes": MagicMock()}):
            with patch("transformers.BitsAndBytesConfig"):
                service_cuda = QwenRecommendationService(
                    serving_mode="full",
                    device="cuda",
                    phase23_adapter_dir=self.valid_adapter_dir
                )
                with patch.object(service_cuda, "_resolve_phase23_adapter", return_value=fake_path):
                    service_cuda.load_model()
                self.assertEqual(service_cuda.quantization, "4bit-nf4")
                self.assertEqual(service_cuda.active_inference_backend, "qwen3-4b-peft-lora-4bit-nf4")

        # 6b. CUDA khi bitsandbytes KHÔNG khả dụng -> FP16 label (trung thực, không giả vờ NF4)
        with patch.dict("sys.modules", {"bitsandbytes": None}):
            service_cuda_nobnb = QwenRecommendationService(
                serving_mode="full",
                device="cuda",
                phase23_adapter_dir=self.valid_adapter_dir
            )
            with patch.object(service_cuda_nobnb, "_resolve_phase23_adapter", return_value=fake_path):
                service_cuda_nobnb.load_model()
            self.assertEqual(service_cuda_nobnb.quantization, "none")
            self.assertEqual(service_cuda_nobnb.actual_dtype, "float16")
            self.assertEqual(service_cuda_nobnb.active_inference_backend, "qwen3-4b-peft-lora-float16")

        # 6c. CPU bắt buộc là float32 (không được dán nhãn nhầm là fp16)
        service_cpu = QwenRecommendationService(
            serving_mode="full",
            device="cpu",
            phase23_adapter_dir=self.valid_adapter_dir
        )
        with patch.object(service_cpu, "_resolve_phase23_adapter", return_value=fake_path):
            service_cpu.load_model()
        self.assertEqual(service_cpu.actual_dtype, "float32")
        self.assertEqual(service_cpu.active_inference_backend, "qwen3-4b-peft-lora-float32")

    # -------------------------------------------------------------------------
    # 7. PEFT load thất bại, fallback tắt
    # -------------------------------------------------------------------------
    @patch("transformers.AutoTokenizer.from_pretrained", side_effect=RuntimeError("Lỗi đọc trọng số"))
    def test_07_peft_load_failed_fallback_disabled(self, mock_tok):
        service = QwenRecommendationService(
            serving_mode="full",
            enable_fallback=False,
            phase23_adapter_dir=self.valid_adapter_dir
        )
        fake_path = Path(self.valid_adapter_dir)
        with patch.object(service, "_resolve_phase23_adapter", return_value=fake_path):
            service.load_model()

        self.assertFalse(service.is_loaded)
        self.assertFalse(service.phase23_adapter_loaded)
        self.assertEqual(service.active_inference_backend, "uninitialized")
        self.assertIsNotNone(service.load_error)

        is_ready, http_code, ready_data = service.get_readiness_status()
        self.assertFalse(is_ready)
        self.assertEqual(http_code, 503)

    # -------------------------------------------------------------------------
    # 8. PEFT load thất bại, fallback bật và GGUF load thành công
    # -------------------------------------------------------------------------
    @patch("transformers.AutoTokenizer.from_pretrained", side_effect=RuntimeError("Hết bộ nhớ VRAM"))
    def test_08_peft_load_failed_fallback_enabled(self, mock_tok):
        service = QwenRecommendationService(
            serving_mode="full",
            enable_fallback=True,
            strict_readiness=True,
            phase23_adapter_dir=self.valid_adapter_dir
        )
        fake_path = Path(self.valid_adapter_dir)
        with patch.object(service, "_resolve_phase23_adapter", return_value=fake_path):
            with patch.object(service, "_load_light_model") as mock_light:
                def fake_light():
                    service.is_loaded = True
                    service.is_gguf = True
                    service.phase23_adapter_loaded = False
                    service.active_base_model_name = "Qwen3-0.6B-Q8_0.gguf"
                    service.resolved_gguf_path = "D:/Class/movie-rcm-system/ai/models/qwen-0.6b/Qwen3-0.6B-Q8_0.gguf"
                    service.active_inference_backend = "qwen3-0.6b-gguf+phase23-normalizer"
                    service.actual_device = "llama_cpp (Qwen3-0.6B-Q8_0 GGUF + Phase23 Normalizer)"
                mock_light.side_effect = fake_light
                service.load_model()

        self.assertTrue(service.is_loaded)
        self.assertFalse(service.phase23_adapter_loaded)
        self.assertTrue(service.is_degraded)
        self.assertEqual(service.active_inference_backend, "qwen3-0.6b-gguf+phase23-normalizer")

        # Với strict_readiness=True, readiness phải trả về 503 Degraded (không giả vờ full 4B ready)
        is_ready, http_code, ready_data = service.get_readiness_status()
        self.assertFalse(is_ready)
        self.assertEqual(http_code, 503)
        self.assertEqual(ready_data["status"], "degraded")
        self.assertTrue(ready_data["degraded"])

        # SERVE-01-F01: Health phản ánh GGUF thực tế trong trạng thái fallback, không giữ Qwen/Qwen3-4B
        health = service.get_health_status()
        self.assertEqual(health["status"], "degraded")
        self.assertEqual(health["servingMode"], "full")
        self.assertEqual(health["activeInferenceBackend"], "qwen3-0.6b-gguf+phase23-normalizer")
        self.assertEqual(health["activeBaseModelName"], "Qwen3-0.6B-Q8_0.gguf")
        self.assertIsNone(health["activeAdapterPath"])
        self.assertNotEqual(health["modelNameOrPath"], "Qwen/Qwen3-4B")
        self.assertIn("Qwen3-0.6B", health["modelNameOrPath"])
        self.assertEqual(health["fallbackModelPath"], service.model_name_or_path)
        self.assertTrue(health["degraded"])
        self.assertFalse(health["phase23AdapterLoaded"])

    # -------------------------------------------------------------------------
    # 9. Cả full model và fallback đều thất bại
    # -------------------------------------------------------------------------
    @patch("transformers.AutoTokenizer.from_pretrained", side_effect=RuntimeError("Lỗi nạp PEFT"))
    def test_09_both_full_and_fallback_fail(self, mock_tok):
        service = QwenRecommendationService(
            serving_mode="full",
            enable_fallback=True,
            phase23_adapter_dir=self.valid_adapter_dir
        )
        fake_path = Path(self.valid_adapter_dir)
        with patch.object(service, "_resolve_phase23_adapter", return_value=fake_path):
            with patch.object(service, "_load_light_model", side_effect=RuntimeError("Lỗi nạp GGUF")):
                service.load_model()

        self.assertFalse(service.is_loaded)
        self.assertFalse(service.phase23_adapter_loaded)
        self.assertEqual(service.active_inference_backend, "uninitialized")

        is_ready, http_code, ready_data = service.get_readiness_status()
        self.assertFalse(is_ready)
        self.assertEqual(http_code, 503)

        # SERVE-01-F01: Khi cả hai đều thất bại, active fields phải là None
        health = service.get_health_status()
        self.assertEqual(health["status"], "unhealthy")
        self.assertFalse(health["modelLoaded"])
        self.assertIsNone(health["activeBaseModelName"])
        self.assertIsNone(health["activeAdapterPath"])
        self.assertEqual(health["modelNameOrPath"], "Qwen/Qwen3-4B")
        self.assertEqual(health["fallbackModelPath"], service.model_name_or_path)

    # -------------------------------------------------------------------------
    # 10. Nhiều request khởi tạo không tạo load trùng
    # -------------------------------------------------------------------------
    def test_10_concurrent_load_requests_no_duplicate(self):
        service = QwenRecommendationService(
            serving_mode="light",
            enable_fallback=True
        )
        load_count = 0
        def fake_load_light():
            nonlocal load_count
            time.sleep(0.05)
            load_count += 1
            service.is_loaded = True
            service.active_inference_backend = "qwen3-0.6b-gguf+phase23-normalizer"

        with patch.object(service, "_load_light_model", side_effect=fake_load_light):
            threads = [threading.Thread(target=service.load_model) for _ in range(5)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

        self.assertEqual(load_count, 1)
        self.assertTrue(service.is_loaded)

    # -------------------------------------------------------------------------
    # 11. Giới hạn inference/concurrency được thực thi
    # -------------------------------------------------------------------------
    def test_11_inference_concurrency_limit_enforced(self):
        service = QwenRecommendationService(
            max_concurrent_inference=1
        )
        slot_acquired_event = threading.Event()
        release_slot_event = threading.Event()
        thread_error = None

        def blocking_inference():
            try:
                with service.acquire_inference_slot(timeout=1.0):
                    slot_acquired_event.set()
                    release_slot_event.wait(timeout=2.0)
            except Exception as e:
                nonlocal thread_error
                thread_error = e

        t = threading.Thread(target=blocking_inference)
        t.start()
        slot_acquired_event.wait(timeout=1.0)

        # Thread 2 cố acquire slot khi slot đã đầy -> phải bị từ chối với timeout
        with self.assertRaises(InferenceCapacityError):
            with service.acquire_inference_slot(timeout=0.1):
                pass

        release_slot_event.set()
        t.join()
        self.assertIsNone(thread_error)

    # -------------------------------------------------------------------------
    # 12. Health/readiness đúng từng trạng thái
    # -------------------------------------------------------------------------
    def test_12_health_and_readiness_state_matrix(self):
        # 12a. Light mode sẵn sàng
        s_light = QwenRecommendationService(serving_mode="light")
        s_light.is_loaded = True
        s_light.active_inference_backend = "qwen3-0.6b-gguf+phase23-normalizer"
        s_light.actual_device = "llama_cpp"
        is_ready, code, res = s_light.get_readiness_status()
        self.assertTrue(is_ready)
        self.assertEqual(code, 200)
        self.assertEqual(res["status"], "ready")
        h_light = s_light.get_health_status()
        self.assertEqual(h_light["status"], "healthy")
        self.assertEqual(h_light["activeBaseModelName"], "Qwen3-0.6B-Q8_0.gguf")
        self.assertIsNone(h_light["activeAdapterPath"])

        # 12b. Full mode degraded (fallback) với strict_readiness=False -> 200 Degraded
        s_degraded = QwenRecommendationService(serving_mode="full", strict_readiness=False)
        s_degraded.is_loaded = True
        s_degraded.is_degraded = True
        s_degraded.phase23_adapter_loaded = False
        s_degraded.active_inference_backend = "qwen3-0.6b-gguf+phase23-normalizer"
        is_ready, code, res = s_degraded.get_readiness_status()
        self.assertTrue(is_ready)
        self.assertEqual(code, 200)
        self.assertEqual(res["status"], "degraded")
        h_degraded = s_degraded.get_health_status()
        self.assertEqual(h_degraded["status"], "degraded")
        self.assertEqual(h_degraded["activeBaseModelName"], "Qwen3-0.6B-Q8_0.gguf")
        self.assertIsNone(h_degraded["activeAdapterPath"])
        self.assertNotEqual(h_degraded["modelNameOrPath"], "Qwen/Qwen3-4B")

        # 12c. Test FastAPI Endpoints qua TestClient (offline mock)
        with patch("services.qwen_service.qwen_service.load_model"):
            client = TestClient(app)
            h_resp = client.get("/health")
            self.assertEqual(h_resp.status_code, 200)
            h_json = h_resp.json()
            self.assertIn("status", h_json)
            self.assertIn("modelLoaded", h_json)
            self.assertIn("servingMode", h_json)
            self.assertIn("activeInferenceBackend", h_json)
            self.assertIn("activeBaseModelName", h_json)
            self.assertIn("fallbackModelPath", h_json)

    # -------------------------------------------------------------------------
    # 13. Khế ước API /v1/discover và /api/chat được mock offline (Zero GPU / Zero Network)
    # -------------------------------------------------------------------------
    def test_13_api_contracts_mocked_offline(self):
        fake_intent = {
            "schema_version": "1.0",
            "intent_type": "DISCOVERY",
            "query": {"text": "phim hoạt hình trước năm 2010 không có kinh dị"},
            "reference": {"text": None, "status": "NO_REFERENCE"},
            "constraints": {
                "year_min": None,
                "year_max": 2009,
                "include_genres": ["Animation"],
                "exclude_genres": ["Horror"]
            },
            "preferences": {"use_personalization": None, "unsupported_facets": []},
            "requested_k": None,
            "diversify": None,
            "clarification": {"required": False, "reason": None, "question": None},
            "no_op": False,
            "year_min": None,
            "year_max": 2009,
            "include_genres": ["Animation"],
            "exclude_genres": ["Horror"],
            "reference_films": []
        }
        with patch("services.qwen_service.qwen_service.load_model"):
            with patch("services.qwen_service.qwen_service.parse_discovery_intent", return_value=fake_intent):
                client = TestClient(app)

                # 13a. POST /v1/discover
                disc_resp = client.post("/v1/discover", json={"query": "phim hoạt hình trước năm 2010 không có kinh dị"})
                self.assertEqual(disc_resp.status_code, 200)
                disc_json = disc_resp.json()
                self.assertIn("structuredIntent", disc_json)
                self.assertIn("explanation", disc_json)
                self.assertIn("results", disc_json)
                self.assertIn("pipelineStages", disc_json)
                intent = disc_json["structuredIntent"]
                self.assertEqual(intent.get("constraints", {}).get("year_max"), 2009)
                self.assertIn("Horror", intent.get("constraints", {}).get("exclude_genres", []))

                # 13b. POST /api/chat
                chat_resp = client.post("/api/chat", json={"query": "gợi ý phim phiêu lưu hay"})
                self.assertEqual(chat_resp.status_code, 200)
                chat_json = chat_resp.json()
                self.assertIn("text", chat_json)
                self.assertIn("recommendedMovies", chat_json)
                self.assertIn("structuredIntent", chat_json)

    # -------------------------------------------------------------------------
    # 14. Full mode + Fallback false: Model chưa sẵn sàng -> HTTP 503
    # -------------------------------------------------------------------------
    def test_14_full_mode_model_unavailable_returns_503(self):
        with patch("services.qwen_service.qwen_service.load_model"):
            with patch.object(qwen_service, "serving_mode", "full"), \
                 patch.object(qwen_service, "enable_fallback", False), \
                 patch.object(qwen_service, "is_loaded", False), \
                 patch.object(qwen_service, "phase23_adapter_loaded", False):
                client = TestClient(app)
                resp = client.post("/v1/discover", json={"query": "gợi ý phim hay"})
                self.assertEqual(resp.status_code, 503)
                self.assertIn("Mô hình chưa sẵn sàng", resp.json().get("detail", ""))

    # -------------------------------------------------------------------------
    # 15. Full mode + Fallback false: Lỗi generation -> HTTP 502 (không che bằng normalizer)
    # -------------------------------------------------------------------------
    def test_15_full_mode_generation_failure_returns_502(self):
        mock_model = MagicMock()
        mock_model.generate.side_effect = RuntimeError("CUDA Out of Memory hoặc lỗi phần cứng GPU")
        mock_tok = MagicMock()
        mock_tok.apply_chat_template.return_value = "dummy prompt"
        mock_tok.return_value.to.return_value = MagicMock(input_ids=MagicMock(shape=[1, 1]))

        with patch("services.qwen_service.qwen_service.load_model"):
            with patch.object(qwen_service, "serving_mode", "full"), \
                 patch.object(qwen_service, "enable_fallback", False), \
                 patch.object(qwen_service, "is_loaded", True), \
                 patch.object(qwen_service, "is_gguf", False), \
                 patch.object(qwen_service, "phase23_adapter_loaded", True), \
                 patch.object(qwen_service, "model", mock_model), \
                 patch.object(qwen_service, "tokenizer", mock_tok):
                client = TestClient(app)
                resp = client.post("/v1/discover", json={"query": "gợi ý phim phiêu lưu trước 2010"})
                self.assertEqual(resp.status_code, 502)
                self.assertIn("Lỗi suy luận sinh văn bản", resp.json().get("detail", ""))

    # -------------------------------------------------------------------------
    # 16. Full mode + Fallback false: JSON parsing lỗi -> HTTP 502 (không che bằng normalizer)
    # -------------------------------------------------------------------------
    def test_16_full_mode_invalid_json_output_returns_502(self):
        mock_model = MagicMock()
        mock_model.generate.return_value = torch.tensor([[1, 2, 3]])
        mock_tok = MagicMock()
        mock_tok.apply_chat_template.return_value = "dummy prompt"
        mock_tok.return_value.to.return_value = MagicMock(input_ids=MagicMock(shape=[1, 1]))
        mock_tok.decode.return_value = "Tôi là AI không thể trả lời dưới dạng JSON"

        with patch("services.qwen_service.qwen_service.load_model"):
            with patch.object(qwen_service, "serving_mode", "full"), \
                 patch.object(qwen_service, "enable_fallback", False), \
                 patch.object(qwen_service, "is_loaded", True), \
                 patch.object(qwen_service, "is_gguf", False), \
                 patch.object(qwen_service, "phase23_adapter_loaded", True), \
                 patch.object(qwen_service, "model", mock_model), \
                 patch.object(qwen_service, "tokenizer", mock_tok):
                client = TestClient(app)
                resp = client.post("/v1/discover", json={"query": "gợi ý phim hoạt hình"})
                self.assertEqual(resp.status_code, 502)
                self.assertIn("JSON không hợp lệ", resp.json().get("detail", ""))

    # -------------------------------------------------------------------------
    # 17. Full mode + Fallback false: Generation thành công -> chuẩn hóa được bảo toàn
    # -------------------------------------------------------------------------
    def test_17_full_mode_valid_generation_preserves_normalization(self):
        valid_json = '{"intent_type": "DISCOVERY", "constraints": {"include_genres": ["Animation", "Adventure"], "exclude_genres": ["Horror"]}}'
        mock_model = MagicMock()
        mock_model.generate.return_value = torch.tensor([[1, 2, 3]])
        mock_tok = MagicMock()
        mock_tok.apply_chat_template.return_value = "dummy prompt"
        mock_tok.return_value.to.return_value = MagicMock(input_ids=MagicMock(shape=[1, 1]))
        mock_tok.decode.return_value = valid_json

        with patch("services.qwen_service.qwen_service.load_model"):
            with patch.object(qwen_service, "serving_mode", "full"), \
                 patch.object(qwen_service, "enable_fallback", False), \
                 patch.object(qwen_service, "is_loaded", True), \
                 patch.object(qwen_service, "is_gguf", False), \
                 patch.object(qwen_service, "phase23_adapter_loaded", True), \
                 patch.object(qwen_service, "model", mock_model), \
                 patch.object(qwen_service, "tokenizer", mock_tok):
                client = TestClient(app)
                resp = client.post("/v1/discover", json={"query": "phim hoạt hình phiêu lưu trước năm 2010 không có kinh dị"})
                self.assertEqual(resp.status_code, 200)
                data = resp.json()
                intent = data["structuredIntent"]
                self.assertEqual(intent["intent_type"], "DISCOVERY")
                # Chuẩn hóa quy tắc năm 2009 được áp dụng trên output hợp lệ
                self.assertEqual(intent["constraints"]["year_max"], 2009)
                self.assertIn("Horror", intent["constraints"]["exclude_genres"])

    # -------------------------------------------------------------------------
    # 18. Health status phân biệt active model và fallback model
    # -------------------------------------------------------------------------
    def test_18_health_distinguishes_active_and_fallback_models(self):
        s_full = QwenRecommendationService(
            serving_mode="full",
            base_model_name="Qwen/Qwen3-4B",
            model_name_or_path="../../ai/models/qwen-0.6b",
            phase23_adapter_dir=self.valid_adapter_dir
        )
        s_full.is_loaded = True
        s_full.phase23_adapter_loaded = True
        s_full.resolved_phase23_path = self.valid_adapter_dir
        s_full.active_inference_backend = "qwen3-4b-peft-lora-4bit-nf4"

        h_full = s_full.get_health_status()
        self.assertEqual(h_full["activeBaseModelName"], "Qwen/Qwen3-4B")
        self.assertEqual(h_full["modelNameOrPath"], "Qwen/Qwen3-4B")
        self.assertEqual(h_full["activeAdapterPath"], self.valid_adapter_dir)
        self.assertEqual(h_full["fallbackModelPath"], "../../ai/models/qwen-0.6b")

        s_light = QwenRecommendationService(
            serving_mode="light",
            model_name_or_path="../../ai/models/qwen-0.6b/Qwen3-0.6B-Q8_0.gguf"
        )
        s_light.is_loaded = True
        s_light.active_inference_backend = "qwen3-0.6b-gguf+phase23-normalizer"
        s_light.resolved_gguf_path = s_light.model_name_or_path

        h_light = s_light.get_health_status()
        self.assertEqual(h_light["activeBaseModelName"], "Qwen3-0.6B-Q8_0.gguf")
        self.assertIsNone(h_light["activeAdapterPath"])
        self.assertEqual(h_light["fallbackModelPath"], "../../ai/models/qwen-0.6b/Qwen3-0.6B-Q8_0.gguf")
        self.assertEqual(h_light["modelNameOrPath"], "../../ai/models/qwen-0.6b/Qwen3-0.6B-Q8_0.gguf")

    # -------------------------------------------------------------------------
    # 19. Full mode: base resolution khác configured default qua adapter metadata
    # -------------------------------------------------------------------------
    @patch("transformers.AutoTokenizer.from_pretrained")
    @patch("transformers.AutoModelForCausalLM.from_pretrained")
    @patch("peft.PeftModel.from_pretrained")
    @patch("torch.cuda.is_available", return_value=True)
    def test_19_full_success_with_base_resolved_from_adapter_metadata(self, mock_cuda, mock_peft, mock_base, mock_tok):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            cfg_file = tmp_path / "adapter_config.json"
            cfg_file.write_text(json.dumps({"base_model_name_or_path": "Qwen/Qwen2.5-3B-Instruct"}), encoding="utf-8")
            (tmp_path / "adapter_model.safetensors").write_text("fake_weights", encoding="utf-8")

            # Cô lập env khỏi .env máy: không có explicit constructor / env -> adapter metadata được dùng
            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("BASE_MODEL_NAME", None)
                service = QwenRecommendationService(
                    serving_mode="full",
                    device="cuda",
                    phase23_adapter_dir=str(tmp_path)
                )
                with patch.object(service, "_resolve_phase23_adapter", return_value=tmp_path):
                    service.load_model()

            self.assertTrue(service.is_loaded)
            self.assertTrue(service.phase23_adapter_loaded)
            mock_base.assert_called_once()
            called_base = mock_base.call_args[0][0]
            self.assertEqual(called_base, "Qwen/Qwen2.5-3B-Instruct")

            self.assertEqual(service.active_base_model_name, "Qwen/Qwen2.5-3B-Instruct")
            self.assertEqual(service.active_adapter_path, str(tmp_path))

            health = service.get_health_status()
            self.assertEqual(health["status"], "healthy")
            self.assertEqual(health["activeBaseModelName"], "Qwen/Qwen2.5-3B-Instruct")
            self.assertEqual(health["modelNameOrPath"], "Qwen/Qwen2.5-3B-Instruct")
            self.assertEqual(health["activeAdapterPath"], str(tmp_path))
            self.assertEqual(health["fallbackModelPath"], service.model_name_or_path)

    # -------------------------------------------------------------------------
    # 20. Light GGUF: direct filesystem helper regression tests (không mock _resolve_gguf_file)
    # -------------------------------------------------------------------------
    def test_20_light_gguf_resolved_from_directory_and_explicit_file(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp_dir_str:
            tmp_root = Path(tmp_dir_str)

            # 20a. Configured explicit valid file -> resolver trả đúng file đó
            valid_file = tmp_root / "explicit_model.gguf"
            valid_file.write_text("dummy gguf content", encoding="utf-8")

            svc_explicit = QwenRecommendationService(
                serving_mode="light",
                model_name_or_path=str(valid_file)
            )
            resolved_explicit = svc_explicit._resolve_gguf_file()
            self.assertIsNotNone(resolved_explicit)
            self.assertEqual(Path(resolved_explicit).resolve(), valid_file.resolve())
            self.assertTrue(os.path.isfile(resolved_explicit))

            with patch.dict("sys.modules", {"llama_cpp": MagicMock()}):
                svc_explicit.load_model()
            self.assertTrue(svc_explicit.is_loaded)
            self.assertTrue(svc_explicit.is_gguf)
            self.assertEqual(svc_explicit.active_base_model_name, "explicit_model.gguf")
            h_file = svc_explicit.get_health_status()
            self.assertEqual(h_file["activeBaseModelName"], "explicit_model.gguf")
            self.assertIsNone(h_file["activeAdapterPath"])

            # 20b. Configured directory chứa GGUF -> resolver trả file cụ thể, không trả tên thư mục
            model_dir = tmp_root / "model_dir"
            model_dir.mkdir(parents=True, exist_ok=True)
            dir_file = model_dir / "Qwen3-0.6B-Q8_0.gguf"
            dir_file.write_text("dummy gguf in dir", encoding="utf-8")

            svc_dir = QwenRecommendationService(
                serving_mode="light",
                model_name_or_path=str(model_dir)
            )
            with patch.object(svc_dir, "_get_gguf_search_candidates", return_value=[model_dir]):
                resolved_dir = svc_dir._resolve_gguf_file()
            self.assertIsNotNone(resolved_dir)
            self.assertEqual(Path(resolved_dir).resolve(), dir_file.resolve())
            self.assertTrue(os.path.isfile(resolved_dir))
            self.assertNotEqual(Path(resolved_dir).name, "model_dir")
            self.assertEqual(Path(resolved_dir).name, "Qwen3-0.6B-Q8_0.gguf")

            with patch.dict("sys.modules", {"llama_cpp": MagicMock()}):
                with patch.object(svc_dir, "_get_gguf_search_candidates", return_value=[model_dir]):
                    svc_dir.load_model()
            self.assertTrue(svc_dir.is_loaded)
            self.assertTrue(svc_dir.is_gguf)
            self.assertEqual(svc_dir.active_base_model_name, "Qwen3-0.6B-Q8_0.gguf")
            self.assertNotEqual(svc_dir.active_base_model_name, "model_dir")
            h_dir = svc_dir.get_health_status()
            self.assertEqual(h_dir["activeBaseModelName"], "Qwen3-0.6B-Q8_0.gguf")

            # 20c. Configured file missing, standard search candidate valid -> tiếp tục search và chọn valid candidate
            missing_configured_file = tmp_root / "missing_config.gguf"
            std_search_dir = tmp_root / "std_search_candidate"
            std_search_dir.mkdir(parents=True, exist_ok=True)
            std_file = std_search_dir / "Qwen3-0.6B-Fallback.gguf"
            std_file.write_text("dummy fallback gguf", encoding="utf-8")

            svc_fallback = QwenRecommendationService(
                serving_mode="light",
                model_name_or_path=str(missing_configured_file)
            )
            with patch.object(svc_fallback, "_get_gguf_search_candidates", return_value=[missing_configured_file, std_search_dir]):
                resolved_fallback = svc_fallback._resolve_gguf_file()
            self.assertIsNotNone(resolved_fallback)
            self.assertEqual(Path(resolved_fallback).resolve(), std_file.resolve())
            self.assertTrue(os.path.isfile(resolved_fallback))
            self.assertNotEqual(Path(resolved_fallback).resolve(), missing_configured_file.resolve())

            # 20d. Không có file ở bất kỳ candidate nào -> resolver trả None
            empty_candidate_dir = tmp_root / "empty_dir"
            empty_candidate_dir.mkdir(parents=True, exist_ok=True)
            svc_none = QwenRecommendationService(
                serving_mode="light",
                model_name_or_path=str(missing_configured_file)
            )
            with patch.object(svc_none, "_get_gguf_search_candidates", return_value=[missing_configured_file, empty_candidate_dir]):
                resolved_none = svc_none._resolve_gguf_file()
            self.assertIsNone(resolved_none)

    # -------------------------------------------------------------------------
    # 21. Normalizer-only: không có active LLM/adapter, legacy field giữ nhãn string
    # -------------------------------------------------------------------------
    def test_21_normalizer_only_has_no_active_model_or_adapter(self):
        service = QwenRecommendationService(
            serving_mode="light",
            model_name_or_path="non/existent/path"
        )
        with patch.object(service, "_resolve_gguf_file", return_value=None):
            service.load_model()

        self.assertTrue(service.is_loaded)
        self.assertFalse(service.is_gguf)
        self.assertFalse(service.phase23_adapter_loaded)
        self.assertEqual(service.active_inference_backend, "phase23-deterministic-normalizer")
        self.assertIsNone(service.active_base_model_name)
        self.assertIsNone(service.active_adapter_path)

        health = service.get_health_status()
        self.assertEqual(health["status"], "healthy")
        self.assertTrue(health["modelLoaded"])
        self.assertIsNone(health["activeBaseModelName"])
        self.assertIsNone(health["activeAdapterPath"])
        self.assertEqual(health["modelNameOrPath"], "phase23-deterministic-normalizer")
        self.assertEqual(health["fallbackModelPath"], "non/existent/path")

        # Khế ước Pydantic schema validation
        health_schema = HealthResponse(**health)
        self.assertIsNone(health_schema.activeBaseModelName)
        self.assertIsNone(health_schema.activeAdapterPath)
        self.assertEqual(health_schema.modelNameOrPath, "phase23-deterministic-normalizer")

    # -------------------------------------------------------------------------
    # 22. Unloaded và failed load: không giữ stale identity
    # -------------------------------------------------------------------------
    def test_22_unloaded_and_failed_load_do_not_retain_stale_identity(self):
        # 22a. Fresh uninitialized service
        s_unloaded = QwenRecommendationService(
            serving_mode="full",
            base_model_name="Qwen/Qwen3-4B",
            model_name_or_path="../../ai/models/qwen-0.6b"
        )
        self.assertFalse(s_unloaded.is_loaded)
        h_unloaded = s_unloaded.get_health_status()
        self.assertEqual(h_unloaded["status"], "unhealthy")
        self.assertFalse(h_unloaded["modelLoaded"])
        self.assertIsNone(h_unloaded["activeBaseModelName"])
        self.assertIsNone(h_unloaded["activeAdapterPath"])
        self.assertEqual(h_unloaded["modelNameOrPath"], "Qwen/Qwen3-4B")
        self.assertEqual(h_unloaded["fallbackModelPath"], "../../ai/models/qwen-0.6b")

        # 22b. Đã từng nạp, sau đó cleanup / failed reload -> không giữ stale identity
        s_loaded = QwenRecommendationService(
            serving_mode="full",
            phase23_adapter_dir=self.valid_adapter_dir
        )
        s_loaded.is_loaded = True
        s_loaded.phase23_adapter_loaded = True
        s_loaded.active_base_model_name = "Qwen/Qwen3-4B"
        s_loaded.active_adapter_path = self.valid_adapter_dir

        s_loaded._cleanup_partial_model()
        self.assertFalse(s_loaded.is_loaded)
        self.assertFalse(s_loaded.phase23_adapter_loaded)
        self.assertIsNone(s_loaded.active_base_model_name)
        self.assertIsNone(s_loaded.active_adapter_path)
        self.assertIsNone(s_loaded.resolved_gguf_path)

        h_after_clean = s_loaded.get_health_status()
        self.assertEqual(h_after_clean["status"], "unhealthy")
        self.assertIsNone(h_after_clean["activeBaseModelName"])
        self.assertIsNone(h_after_clean["activeAdapterPath"])
        self.assertEqual(h_after_clean["modelNameOrPath"], "Qwen/Qwen3-4B")

    # -------------------------------------------------------------------------
    # 23. Base model selection precedence matrix (6 scenarios)
    # -------------------------------------------------------------------------
    @patch("transformers.AutoTokenizer.from_pretrained")
    @patch("transformers.AutoModelForCausalLM.from_pretrained")
    @patch("peft.PeftModel.from_pretrained")
    @patch("torch.cuda.is_available", return_value=True)
    def test_23_base_model_selection_precedence_matrix(self, mock_cuda, mock_peft, mock_base, mock_tok):
        import tempfile

        def create_test_adapter(tmp_path: Path, meta_base: Optional[str]) -> Path:
            adapter_dir = tmp_path / f"adapter_{meta_base.replace('/', '_') if meta_base else 'none'}"
            adapter_dir.mkdir(parents=True, exist_ok=True)
            cfg = {}
            if meta_base is not None:
                cfg["base_model_name_or_path"] = meta_base
            (adapter_dir / "adapter_config.json").write_text(json.dumps(cfg), encoding="utf-8")
            (adapter_dir / "adapter_model.safetensors").write_text("weights", encoding="utf-8")
            return adapter_dir

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_root = Path(tmp_dir)

            scenarios = [
                # 1. Không constructor/env -> adapter metadata được dùng
                ("1_no_constructor_no_env_uses_adapter_meta", None, None, "Meta/AdapterBase", "Meta/AdapterBase"),
                # 2. Constructor explicit khác adapter, env absent -> constructor được dùng
                ("2_constructor_explicit_wins_over_adapter", "Caller/ExplicitBase", None, "Meta/AdapterBase", "Caller/ExplicitBase"),
                # 3. Env explicit khác adapter, constructor absent -> env được dùng
                ("3_env_explicit_wins_over_adapter", None, "Env/ExplicitBase", "Meta/AdapterBase", "Env/ExplicitBase"),
                # 4. Constructor và env đều có -> constructor được dùng
                ("4_constructor_wins_over_env_and_adapter", "Caller/ExplicitBase", "Env/ExplicitBase", "Meta/AdapterBase", "Caller/ExplicitBase"),
                # 5. Env explicit đúng chuỗi default nhưng adapter khác -> env vẫn được dùng
                ("5_env_explicit_default_string_wins_over_adapter", None, "Qwen/Qwen3-4B", "Meta/AdapterBase", "Qwen/Qwen3-4B"),
                # 6. Không có explicit/metadata -> default được dùng
                ("6_no_explicit_no_metadata_uses_default", None, None, None, "Qwen/Qwen3-4B"),
            ]

            for case_id, c_arg, env_val, a_meta, expected in scenarios:
                with self.subTest(case=case_id):
                    mock_base.reset_mock()
                    adapter_dir = create_test_adapter(tmp_root, a_meta)

                    with patch.dict(os.environ, {}, clear=False):
                        if env_val is not None:
                            os.environ["BASE_MODEL_NAME"] = env_val
                        else:
                            os.environ.pop("BASE_MODEL_NAME", None)

                        kwargs = {
                            "serving_mode": "full",
                            "device": "cuda",
                            "phase23_adapter_dir": str(adapter_dir)
                        }
                        if c_arg is not None:
                            kwargs["base_model_name"] = c_arg

                        svc = QwenRecommendationService(**kwargs)
                        with patch.object(svc, "_resolve_phase23_adapter", return_value=adapter_dir):
                            svc.load_model()

                        self.assertTrue(svc.is_loaded)
                        self.assertTrue(svc.phase23_adapter_loaded)
                        mock_base.assert_called_once()
                        called_base = mock_base.call_args[0][0]
                        self.assertEqual(called_base, expected, f"Scenario {case_id} failed: expected {expected}, got {called_base}")
                        self.assertEqual(svc.active_base_model_name, expected)

                        health = svc.get_health_status()
                        self.assertEqual(health["status"], "healthy")
                        self.assertEqual(health["activeBaseModelName"], expected)
                        self.assertEqual(health["modelNameOrPath"], expected)


if __name__ == "__main__":
    unittest.main()
