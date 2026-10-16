import os
import re
import glob
import json
import logging
import threading
from pathlib import Path
from contextlib import contextmanager
from typing import List, Dict, Any, Optional, Tuple
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class InferenceCapacityError(Exception):
    """Ngoại lệ khi số lượng request suy luận vượt quá giới hạn đồng thời (HTTP 429)."""
    pass


class ModelNotReadyError(Exception):
    """Ngoại lệ khi model chưa sẵn sàng hoặc nạp thất bại ở chế độ không fallback (HTTP 503)."""
    pass


class InferenceGenerationError(Exception):
    """Ngoại lệ khi quá trình sinh văn bản từ mô hình gặp lỗi phần cứng hoặc runtime (HTTP 502)."""
    pass


class ModelOutputParseError(Exception):
    """Ngoại lệ khi output sinh ra từ model không phải là JSON hợp lệ (HTTP 502)."""
    pass

DEFAULT_MOVIES = [
    {
        "id": "the-last-orbit",
        "title": "The Last Orbit",
        "year": 2026,
        "rating": 8.7,
        "runtime": "2h 14m",
        "genres": ["Sci-Fi", "Drama", "Animation"],
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
        "genres": ["Drama", "Mystery", "Animation"],
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
        "genres": ["Thriller", "Sci-Fi", "Animation"],
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
        "genres": ["Adventure", "Drama", "Animation"],
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
        "genres": ["Romance", "Drama", "Animation"],
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
        "genres": ["Crime", "Thriller", "Animation"],
        "description": "A detective investigates a string of elegant crimes committed at midnight.",
        "poster": "https://images.unsplash.com/photo-1478720568477-152d9b164e26?auto=format&fit=crop&w=600&q=85",
        "backdrop": "https://images.unsplash.com/photo-1478720568477-152d9b164e26?auto=format&fit=crop&w=1800&q=85",
        "videoUrl": "/videos/nocturne.mp4"
    },
    {
        "id": "spirited-away",
        "title": "Spirited Away",
        "year": 2001,
        "rating": 8.6,
        "runtime": "2h 05m",
        "genres": ["Animation", "Adventure", "Fantasy", "Family"],
        "description": "During her family's move to the suburbs, a sullen 10-year-old girl wanders into a world ruled by gods, witches, and spirits.",
        "poster": "https://images.unsplash.com/photo-1578632767115-351597cf2477?auto=format&fit=crop&w=600&q=85",
        "backdrop": "https://images.unsplash.com/photo-1578632767115-351597cf2477?auto=format&fit=crop&w=1800&q=85",
        "videoUrl": "/videos/the-last-orbit.mp4"
    },
    {
        "id": "your-name",
        "title": "Your Name",
        "year": 2016,
        "rating": 8.4,
        "runtime": "1h 46m",
        "genres": ["Animation", "Romance", "Fantasy", "Drama"],
        "description": "Two teenagers share a profound, magical connection upon discovering they are swapping bodies across time and space.",
        "poster": "https://images.unsplash.com/photo-1534447677768-be436bb09401?auto=format&fit=crop&w=600&q=85",
        "backdrop": "https://images.unsplash.com/photo-1534447677768-be436bb09401?auto=format&fit=crop&w=1800&q=85",
        "videoUrl": "/videos/quiet-places.mp4"
    },
    {
        "id": "isle-of-dogs",
        "title": "Isle of Dogs",
        "year": 2018,
        "rating": 7.8,
        "runtime": "1h 41m",
        "genres": ["Animation", "Adventure", "Comedy", "Drama"],
        "description": "Set in Japan, Isle of Dogs follows a boy's odyssey in search of his lost dog on a quarantined trash island.",
        "poster": "https://images.unsplash.com/photo-1548199973-03cce0bbc87b?auto=format&fit=crop&w=600&q=85",
        "backdrop": "https://images.unsplash.com/photo-1548199973-03cce0bbc87b?auto=format&fit=crop&w=1800&q=85",
        "videoUrl": "/videos/deep-blue.mp4"
    },
    {
        "id": "spider-verse",
        "title": "Spider-Man: Into the Spider-Verse",
        "year": 2018,
        "rating": 8.4,
        "runtime": "1h 57m",
        "genres": ["Animation", "Action", "Adventure", "Sci-Fi"],
        "description": "Teen Miles Morales becomes the Spider-Man of his universe and must join with five spider-powered individuals from other dimensions.",
        "poster": "https://images.unsplash.com/photo-1635805737707-575885ab0820?auto=format&fit=crop&w=600&q=85",
        "backdrop": "https://images.unsplash.com/photo-1635805737707-575885ab0820?auto=format&fit=crop&w=1800&q=85",
        "videoUrl": "/videos/glass-horizon.mp4"
    },
    {
        "id": "coraline",
        "title": "Coraline",
        "year": 2009,
        "rating": 7.7,
        "runtime": "1h 40m",
        "genres": ["Animation", "Fantasy", "Horror", "Mystery"],
        "description": "An adventurous 11-year-old girl finds another world that is a strangely idealized version of her frustrating home, but it has sinister secrets.",
        "poster": "https://images.unsplash.com/photo-1509198397868-475647b2a1e5?auto=format&fit=crop&w=600&q=85",
        "backdrop": "https://images.unsplash.com/photo-1509198397868-475647b2a1e5?auto=format&fit=crop&w=1800&q=85",
        "videoUrl": "/videos/nocturne.mp4"
    },
    {
        "id": "fantasia-1940",
        "title": "Fantasia",
        "year": 1940,
        "rating": 7.7,
        "runtime": "2h 05m",
        "genres": ["Animation", "Family", "Fantasy", "Music"],
        "description": "A visionary collection of animated interpretations of great works of Western classical music.",
        "poster": "https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?auto=format&fit=crop&w=600&q=85",
        "backdrop": "https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?auto=format&fit=crop&w=1800&q=85",
        "videoUrl": "/videos/quiet-places.mp4"
    }
]

GENRE_SYNONYMS: Dict[str, List[str]] = {
    "Action": ["action", "hành động", "đánh nhau", "chiến đấu"],
    "Adventure": ["adventure", "phiêu lưu", "thám hiểm", "hành trình"],
    "Animation": ["animation", "animated", "hoạt hình", "anime"],
    "Comedy": ["comedy", "hài", "hài hước", "vui nhộn"],
    "Crime": ["crime", "tội phạm", "hình sự"],
    "Documentary": ["documentary", "tài liệu"],
    "Drama": ["drama", "chính kịch", "tâm lý", "cảm xúc", "sâu lắng", "chữa lành"],
    "Family": ["family", "gia đình", "thiếu nhi", "trẻ em"],
    "Fantasy": ["fantasy", "giả tưởng", "phép thuật", "kỳ ảo", "thần thoại"],
    "History": ["history", "historical", "lịch sử", "cổ trang"],
    "Horror": ["horror", "kinh dị", "ma", "rùng rợn", "đáng sợ", "scary"],
    "Music": ["music", "musical", "âm nhạc", "nhạc kịch"],
    "Mystery": ["mystery", "bí ẩn", "trinh thám"],
    "Romance": ["romance", "romantic", "tình cảm", "lãng mạn", "tình yêu"],
    "Sci-Fi": ["sci-fi", "science fiction", "khoa học viễn tưởng", "viễn tưởng", "vũ trụ", "không gian"],
    "Thriller": ["thriller", "giật gân", "hồi hộp", "đấu trí", "kịch tính"],
    "War": ["war", "chiến tranh"],
    "Western": ["western", "viễn tây"],
}

PATCH_INTENT_SYNONYMS = {
    "CONVERSATIONAL_PATCH",
    "UPDATE_CONSTRAINTS",
    "UPDATE_CONSTRAINT",
    "MODIFY",
    "UPDATE",
    "MODIFY_CONSTRAINTS",
    "MODIFY_REQUEST",
    "CLEAR_CONSTRAINT",
}

PATCH_CUE_PATTERNS = [
    r"\bactually\b",
    r"\binstead\b",
    r"\bkeep everything else\b",
    r"\bchange (it|the count|to)\b",
    r"\bmake it\b",
    r"\bupdate\b",
    r"\bremove the\b",
    r"\bđổi (thành|sang|lại)\b",
    r"\bcập nhật\b",
    r"\bgiữ nguyên\b",
    r"\bbỏ (thể loại|ràng buộc|điều kiện)\b",
    r"\bthay vì\b",
]


class QwenRecommendationService:
    def __init__(
        self,
        serving_mode: Optional[str] = None,
        use_full_4b_lora: Optional[bool] = None,
        device: Optional[str] = None,
        enable_fallback: Optional[bool] = None,
        strict_readiness: Optional[bool] = None,
        max_concurrent_inference: Optional[int] = None,
        max_new_tokens: Optional[int] = None,
        base_model_name: Optional[str] = None,
        phase23_adapter_dir: Optional[str] = None,
        model_name_or_path: Optional[str] = None,
    ):
        # 1. Cấu hình chế độ serving (Chính: 'full', Nhẹ: 'light')
        env_full_flag = os.getenv("USE_FULL_QWEN3_4B_LORA", "true").lower() == "true"
        if serving_mode is not None:
            self.serving_mode = serving_mode.lower()
        elif use_full_4b_lora is not None:
            self.serving_mode = "full" if use_full_4b_lora else "light"
        else:
            configured_mode = os.getenv("SERVING_MODE")
            if configured_mode:
                self.serving_mode = configured_mode.lower()
            else:
                self.serving_mode = "full" if env_full_flag else "light"

        self.use_full_4b_lora = (self.serving_mode == "full")

        # 2. Cấu hình chính sách thiết bị ('auto', 'cuda', 'cpu')
        self.device_config = (device or os.getenv("DEVICE", "cuda")).lower()

        # 3. Chính sách fallback khi nạp full model thất bại
        if enable_fallback is not None:
            self.enable_fallback = enable_fallback
        else:
            self.enable_fallback = os.getenv("ENABLE_FALLBACK", "false").lower() == "true"

        # 4. Chính sách readiness khắt khe (nếu requested='full' mà chạy fallback -> readiness báo degraded/unready)
        if strict_readiness is not None:
            self.strict_readiness = strict_readiness
        else:
            self.strict_readiness = os.getenv("STRICT_READINESS", "true").lower() == "true"

        # 5. Giới hạn tài nguyên và concurrency
        self.max_concurrent_inference = max_concurrent_inference or int(os.getenv("MAX_CONCURRENT_INFERENCE", "1"))
        self.max_new_tokens = max_new_tokens or int(os.getenv("MAX_NEW_TOKENS", "256"))
        self._inference_semaphore = threading.BoundedSemaphore(self.max_concurrent_inference)
        self._load_lock = threading.Lock()

        # 6. Đường dẫn artifact và cấu hình base model
        self.constructor_base_model: Optional[str] = base_model_name
        self._has_explicit_constructor_base: bool = (base_model_name is not None)
        self.configured_env_base: Optional[str] = os.getenv("BASE_MODEL_NAME")
        self._has_explicit_env_base: bool = bool(self.configured_env_base and self.configured_env_base.strip())
        self.configured_base_model_name: Optional[str] = self.constructor_base_model or self.configured_env_base
        self.base_model_name: str = self.configured_base_model_name or "Qwen/Qwen3-4B"
        self._explicit_base_model: bool = self._has_explicit_constructor_base or self._has_explicit_env_base
        self.phase23_adapter_dir = phase23_adapter_dir or os.getenv("PHASE23_ADAPTER_DIR", "../../ai/models/qwen3-4b-phase23-lora")
        self.model_name_or_path = model_name_or_path or os.getenv("MODEL_NAME_OR_PATH", "../../ai/models/qwen-0.6b")

        # 7. Trạng thái runtime thực tế
        self.model = None
        self.tokenizer = None
        self.llama_model = None
        self.is_loaded = False
        self.is_gguf = False
        self.phase23_artifact_verified = False
        self.phase23_adapter_loaded = False
        self.resolved_phase23_path: Optional[str] = None
        self.active_inference_backend: str = "uninitialized"
        self.actual_device = "uninitialized"
        self.actual_dtype = "unknown"
        self.quantization = "none"
        self.device_placement: Dict[str, Any] = {}
        self.load_error: Optional[str] = None
        self.is_degraded = False
        self.active_base_model_name: Optional[str] = None
        self.active_adapter_path: Optional[str] = None
        self.resolved_gguf_path: Optional[str] = None

        self.system_prompt_v2_2: str = (
            "You are an expert natural language discovery intent parser for the Dippie Cinema animation system.\n"
            "Convert the user's natural language request into a strict JSON object conforming to StructuredDiscoveryIntent v1.\n"
            "Output raw JSON only. No explanations, no markdown fences."
        )

    @contextmanager
    def acquire_inference_slot(self, timeout: float = 90.0):
        """Giới hạn số request suy luận đồng thời trên GPU/CPU, tránh quá tải VRAM."""
        acquired = self._inference_semaphore.acquire(blocking=True, timeout=timeout)
        if not acquired:
            logger.warning(
                f"Từ chối yêu cầu suy luận: vượt quá giới hạn đồng thời MAX_CONCURRENT_INFERENCE={self.max_concurrent_inference}"
            )
            raise InferenceCapacityError(
                f"Hệ thống đang phục vụ tối đa ({self.max_concurrent_inference}) tiến trình suy luận AI. Vui lòng thử lại sau."
            )
        try:
            yield
        finally:
            self._inference_semaphore.release()

    def _resolve_device(self, requested: str) -> str:
        """
        Thực thi chính sách thiết bị nghiêm ngặt:
        - 'cpu': bắt buộc dùng CPU dù máy có CUDA.
        - 'cuda': bắt buộc CUDA; nếu không có phải raise lỗi rõ ràng.
        - 'auto': chọn CUDA nếu khả dụng, ngược lại fallback CPU.
        """
        req = (requested or "auto").lower().strip()
        if req == "cpu":
            return "cpu"
        elif req == "cuda":
            try:
                import torch
                cuda_ok = torch.cuda.is_available()
            except Exception:
                cuda_ok = False
            if not cuda_ok:
                raise RuntimeError("Thiết bị CUDA được yêu cầu (DEVICE='cuda') nhưng torch.cuda.is_available() là False.")
            return "cuda"
        elif req == "auto":
            try:
                import torch
                return "cuda" if torch.cuda.is_available() else "cpu"
            except Exception:
                return "cpu"
        else:
            raise ValueError(f"Chính sách thiết bị không hợp lệ: '{requested}'. Hỗ trợ: 'auto', 'cuda', 'cpu'.")

    def _resolve_phase23_adapter(self) -> Optional[Path]:
        base_dir = Path(__file__).resolve().parent
        candidates = [
            Path(self.phase23_adapter_dir),
            Path("/app/models/qwen3-4b-phase23-lora"),
            base_dir / "../../ai/models/qwen3-4b-phase23-lora",
            Path("D:/Class/movie-rcm-system/ai/models/qwen3-4b-phase23-lora"),
            Path("D:/A+ test/ai/models/qwen3-4b-phase23-lora"),
        ]
        for c in candidates:
            if c.exists() and (c / "adapter_config.json").exists() and (c / "adapter_model.safetensors").exists():
                return c.resolve()
        return None

    def _cleanup_partial_model(self):
        """Dọn dẹp tham chiếu và giải phóng bộ nhớ khi nạp model thất bại"""
        self.model = None
        self.tokenizer = None
        self.llama_model = None
        self.is_loaded = False
        self.is_gguf = False
        self.phase23_adapter_loaded = False
        self.active_base_model_name = None
        self.active_adapter_path = None
        self.resolved_gguf_path = None
        import gc
        gc.collect()
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass

    def _get_gguf_search_candidates(self) -> List[Path]:
        """Danh sách đường dẫn ứng viên để tìm kiếm file GGUF."""
        base_dir = Path(__file__).resolve().parent
        candidates: List[Path] = []
        if self.model_name_or_path:
            candidates.append(Path(self.model_name_or_path))
        candidates.extend([
            Path("/app/models/qwen-0.6b"),
            base_dir / "../../ai/models/qwen-0.6b",
            Path("../../ai/models/qwen-0.6b"),
            Path("../ai/models/qwen-0.6b"),
            Path("D:/Class/movie-rcm-system/ai/models/qwen-0.6b"),
            Path("D:/A+ test/ai/models/qwen-0.6b"),
        ])
        return candidates

    def _resolve_gguf_file(self) -> Optional[str]:
        """
        Giải quyết đường dẫn file .gguf cụ thể từ cấu hình hoặc các thư mục chuẩn.
        Configured explicit file tồn tại có ưu tiên; missing file tiếp tục search candidates.
        Chỉ trả về đường dẫn file thực tế, không trả directory hoặc non-existent path.
        """
        if self.resolved_gguf_path and os.path.isfile(self.resolved_gguf_path):
            return self.resolved_gguf_path

        candidates = self._get_gguf_search_candidates()
        for c in candidates:
            try:
                if c.is_file() and c.suffix.lower() == ".gguf":
                    return str(c.as_posix())
                elif c.is_dir():
                    found = sorted(list(c.glob("*.gguf")))
                    if found:
                        return str(found[0].as_posix())
            except Exception:
                continue

        return None

    def _load_full_peft_model(self, adapter_path: Path):
        """Nạp Qwen3-4B base model kết hợp Phase 23 LoRA Adapter qua PEFT"""
        import torch
        import peft.import_utils
        peft.import_utils.is_torchao_available = lambda: False
        from transformers import AutoModelForCausalLM, AutoTokenizer
        from peft import PeftModel

        target_device = self._resolve_device(self.device_config)

        cfg_file = adapter_path / "adapter_config.json"
        adapter_base: Optional[str] = None
        if cfg_file.exists():
            try:
                cfg = json.loads(cfg_file.read_text(encoding="utf-8"))
                raw_adapter_base = cfg.get("base_model_name_or_path")
                if raw_adapter_base and isinstance(raw_adapter_base, str) and raw_adapter_base.strip():
                    adapter_base = raw_adapter_base.strip()
            except Exception:
                pass

        # Precedence:
        # 1. Constructor base_model_name explicit
        # 2. BASE_MODEL_NAME explicit từ environment
        # 3. Adapter metadata nếu cả hai không khai báo
        # 4. Default Qwen/Qwen3-4B
        current_env = os.getenv("BASE_MODEL_NAME")
        env_explicit = (current_env.strip() if current_env and current_env.strip() else None)
        if not env_explicit and self._has_explicit_env_base and self.configured_env_base and self.configured_env_base.strip():
            env_explicit = self.configured_env_base.strip()

        if self._has_explicit_constructor_base and self.constructor_base_model and self.constructor_base_model.strip():
            base_model_name = self.constructor_base_model.strip()
        elif env_explicit:
            base_model_name = env_explicit
        elif adapter_base:
            base_model_name = adapter_base
        else:
            base_model_name = "Qwen/Qwen3-4B"

        self.base_model_name = base_model_name

        logger.info(f"Đang nạp tokenizer từ: {adapter_path}")
        self.tokenizer = AutoTokenizer.from_pretrained(str(adapter_path), trust_remote_code=True)

        load_kwargs: Dict[str, Any] = {"trust_remote_code": True}

        if target_device == "cuda":
            # Ưu tiên NF4 4-bit cho GPU laptop 6GB VRAM
            try:
                import bitsandbytes
                from transformers import BitsAndBytesConfig
                load_kwargs["quantization_config"] = BitsAndBytesConfig(
                    load_in_4bit=True,
                    bnb_4bit_quant_type="nf4",
                    bnb_4bit_use_double_quant=True,
                    bnb_4bit_compute_dtype=torch.float16,
                )
                load_kwargs["device_map"] = "auto"
                self.quantization = "4bit-nf4"
                self.actual_dtype = "float16"
            except Exception as bnb_err:
                logger.warning(f"BitsAndBytes NF4 không khả dụng: {bnb_err}. Dùng FP16.")
                load_kwargs["torch_dtype"] = torch.float16
                load_kwargs["device_map"] = "auto"
                self.quantization = "none"
                self.actual_dtype = "float16"
        else:
            # Nhánh CPU: bắt buộc dùng float32 thực tế
            load_kwargs["torch_dtype"] = torch.float32
            self.quantization = "none"
            self.actual_dtype = "float32"

        logger.info(f"Đang nạp base model '{base_model_name}' (device={target_device}, dtype={self.actual_dtype}, quant={self.quantization})...")
        base_model = AutoModelForCausalLM.from_pretrained(base_model_name, **load_kwargs)

        logger.info(f"Đang gắn Phase 23 LoRA Adapter từ: {adapter_path}")
        self.model = PeftModel.from_pretrained(base_model, str(adapter_path))
        self.model.eval()

        # Kiểm tra placement thực tế nếu có device_map
        placement_map: Dict[str, Any] = {}
        if hasattr(self.model, "hf_device_map"):
            placement_map = {str(k): str(v) for k, v in self.model.hf_device_map.items()}
        elif hasattr(base_model, "hf_device_map"):
            placement_map = {str(k): str(v) for k, v in base_model.hf_device_map.items()}
        self.device_placement = placement_map

        has_cpu_or_disk = any(str(v).lower() in ("cpu", "disk") for v in placement_map.values())
        quant_tag = self.quantization if self.quantization != "none" else self.actual_dtype

        if has_cpu_or_disk:
            self.actual_device = f"cuda:0 (with cpu/disk offload, {quant_tag})"
        elif target_device == "cuda":
            self.actual_device = f"cuda:0 ({quant_tag})"
        else:
            self.actual_device = f"cpu ({self.actual_dtype})"

        self.is_loaded = True
        self.is_gguf = False
        self.phase23_adapter_loaded = True
        self.active_base_model_name = base_model_name
        self.active_adapter_path = str(adapter_path)
        self.resolved_gguf_path = None
        self.active_inference_backend = f"qwen3-4b-peft-lora-{quant_tag}"
        self.is_degraded = False
        self.load_error = None
        logger.info(f"Nạp thành công Qwen3-4B + Phase 23 LoRA ({self.active_inference_backend}) trên {self.actual_device}!")

    def _load_light_model(self):
        """Nạp chế độ nhẹ: Qwen3-0.6B GGUF qua llama-cpp-python hoặc Phase 23 Normalizer"""
        gguf_path = self._resolve_gguf_file()

        if gguf_path and os.path.exists(gguf_path):
            try:
                from llama_cpp import Llama
                logger.info(f"Đang nạp model Qwen GGUF trực tiếp từ: {gguf_path}...")
                self.llama_model = Llama(
                    model_path=gguf_path,
                    n_ctx=2048,
                    n_threads=os.cpu_count() or 4,
                    verbose=False
                )
                self.is_loaded = True
                self.is_gguf = True
                self.phase23_adapter_loaded = False
                self.resolved_gguf_path = gguf_path
                self.active_base_model_name = os.path.basename(gguf_path)
                self.active_adapter_path = None
                self.active_inference_backend = "qwen3-0.6b-gguf+phase23-normalizer"
                self.actual_device = f"llama_cpp ({self.active_base_model_name} + Phase23 Normalizer)"
                self.quantization = "q8_0"
                self.actual_dtype = "q8_0"
                logger.info(f"Nạp model Qwen GGUF thành công từ {gguf_path}!")
                return
            except Exception as e:
                logger.error(f"Lỗi nạp qua llama-cpp: {e}")
                if not self.load_error:
                    self.load_error = f"Lỗi nạp GGUF: {str(e).splitlines()[-1]}"

        # Nếu không có GGUF hoặc nạp GGUF lỗi: kích hoạt bộ chuẩn hóa tất định Phase 23
        self.is_loaded = True
        self.is_gguf = False
        self.llama_model = None
        self.phase23_adapter_loaded = False
        self.active_base_model_name = None
        self.active_adapter_path = None
        self.resolved_gguf_path = None
        self.active_inference_backend = "phase23-deterministic-normalizer"
        self.actual_device = "cpu (deterministic-normalizer)"
        self.quantization = "none"
        self.actual_dtype = "none"
        logger.info("Kích hoạt chế độ Phase 23 Deterministic Normalizer.")

    def load_model(self, force_reload: bool = False):
        """
        Nạp model có kiểm soát lifecycle:
        - Thread-safe qua _load_lock (tránh load trùng khi nhiều request đến cùng lúc).
        - Phân biệt rõ chế độ chính (full Qwen3-4B LoRA) và chế độ nhẹ (GGUF).
        - Thực thi chính sách fallback cấu hình được.
        """
        with self._load_lock:
            if self.is_loaded and not force_reload:
                return

            adapter_path = self._resolve_phase23_adapter()
            if adapter_path:
                self.resolved_phase23_path = str(adapter_path)
                self.phase23_artifact_verified = True
                sp_file = adapter_path / "system_prompt_v2_2.txt"
                if sp_file.exists():
                    self.system_prompt_v2_2 = sp_file.read_text(encoding="utf-8").strip()
                logger.info(f"Đã xác thực gói Phase 23 LoRA Artifact tại: {self.resolved_phase23_path}")
            else:
                self.resolved_phase23_path = None
                self.phase23_artifact_verified = False

            # Chế độ 1: Full Qwen3-4B + Phase 23 LoRA
            if self.serving_mode == "full":
                if not adapter_path:
                    err_msg = f"Không tìm thấy adapter Phase 23 LoRA tại {self.phase23_adapter_dir} hoặc các thư mục chuẩn."
                    logger.error(err_msg)
                    self.load_error = err_msg
                    if self.enable_fallback:
                        self.is_degraded = True
                        logger.warning("Kích hoạt fallback sang chế độ nhẹ do thiếu adapter.")
                        self._load_light_model()
                    else:
                        self.is_loaded = False
                        self.phase23_adapter_loaded = False
                        self.active_base_model_name = None
                        self.active_adapter_path = None
                        self.resolved_gguf_path = None
                        self.active_inference_backend = "uninitialized"
                        self.actual_device = "uninitialized"
                    return

                try:
                    self._load_full_peft_model(adapter_path)
                    return
                except Exception as e:
                    clean_err = f"{type(e).__name__}: {str(e).splitlines()[-1]}"
                    logger.error(f"Nạp full Qwen3-4B LoRA thất bại: {clean_err}")
                    self.load_error = clean_err
                    self._cleanup_partial_model()

                    if self.enable_fallback:
                        self.is_degraded = True
                        logger.warning("Kích hoạt fallback sang chế độ nhẹ theo chính sách ENABLE_FALLBACK=true.")
                        try:
                            self._load_light_model()
                        except Exception as fb_err:
                            logger.critical(f"Cả full model và fallback đều thất bại: {fb_err}")
                            self.is_loaded = False
                            self.phase23_adapter_loaded = False
                            self.active_base_model_name = None
                            self.active_adapter_path = None
                            self.resolved_gguf_path = None
                            self.active_inference_backend = "uninitialized"
                            self.actual_device = "uninitialized"
                    else:
                        self.is_loaded = False
                        self.phase23_adapter_loaded = False
                        self.active_base_model_name = None
                        self.active_adapter_path = None
                        self.resolved_gguf_path = None
                        self.active_inference_backend = "uninitialized"
                        self.actual_device = "uninitialized"
                        logger.error("Chính sách ENABLE_FALLBACK=false: Không kích hoạt fallback.")
                    return

            # Chế độ 2: Light GGUF model
            try:
                self._load_light_model()
            except Exception as e:
                clean_err = f"{type(e).__name__}: {str(e).splitlines()[-1]}"
                logger.critical(f"Nạp chế độ nhẹ thất bại: {clean_err}")
                self.load_error = clean_err
                self.is_loaded = False
                self.phase23_adapter_loaded = False
                self.active_base_model_name = None
                self.active_adapter_path = None
                self.resolved_gguf_path = None
                self.active_inference_backend = "uninitialized"
                self.actual_device = "uninitialized"

    def get_health_status(self) -> Dict[str, Any]:
        """Tạo đối tượng HealthResponse trung thực với trạng thái phục vụ thực tế"""
        if not self.is_loaded:
            status_str = "unhealthy"
        elif self.is_degraded:
            status_str = "degraded"
        else:
            status_str = "healthy"

        fallback_model_path = self.model_name_or_path

        if not self.is_loaded:
            # 1. Chưa nạp hoặc nạp thất bại: active fields là None, modelNameOrPath giữ configured target
            active_base_model = None
            active_adapter_path = None
            reported_model_path = self.base_model_name if self.serving_mode == "full" else self.model_name_or_path
        elif self.phase23_adapter_loaded:
            # 2. Full PEFT loaded: activeBaseModelName là base thực sự đã nạp, activeAdapterPath là adapter đã gắn
            active_base_model = self.active_base_model_name or self.base_model_name
            active_adapter_path = self.active_adapter_path or self.resolved_phase23_path
            reported_model_path = active_base_model
        elif self.active_inference_backend == "phase23-deterministic-normalizer":
            # 3. Deterministic normalizer: không có active LLM
            active_base_model = None
            active_adapter_path = None
            reported_model_path = "phase23-deterministic-normalizer"
        else:
            # 4. GGUF đang phục vụ (Light mode hoặc Fallback khi requested full)
            gguf_resolved = self.resolved_gguf_path or self._resolve_gguf_file()
            if self.active_base_model_name:
                active_base_model = self.active_base_model_name
            elif gguf_resolved:
                active_base_model = os.path.basename(gguf_resolved)
            elif self.model_name_or_path.endswith(".gguf") and os.path.isfile(self.model_name_or_path):
                active_base_model = os.path.basename(self.model_name_or_path)
            else:
                active_base_model = "Qwen3-0.6B-Q8_0.gguf"

            active_adapter_path = None
            reported_model_path = gguf_resolved or active_base_model

        return {
            "status": status_str,
            "modelLoaded": self.is_loaded,
            "modelNameOrPath": reported_model_path,
            "activeBaseModelName": active_base_model,
            "activeAdapterPath": active_adapter_path,
            "fallbackModelPath": fallback_model_path,
            "phase23ArtifactVerified": self.phase23_artifact_verified,
            "phase23AdapterLoaded": self.phase23_adapter_loaded,
            "phase23AdapterPath": self.resolved_phase23_path,
            "activeInferenceBackend": self.active_inference_backend,
            "device": self.actual_device,
            "servingMode": self.serving_mode,
            "requestedDevice": self.device_config,
            "actualDevice": self.actual_device,
            "quantization": self.quantization,
            "degraded": self.is_degraded,
            "loadError": self.load_error,
        }

    def get_readiness_status(self) -> Tuple[bool, int, Dict[str, Any]]:
        """
        Xác định tính sẵn sàng (Readiness) theo chính sách cấu hình:
        - Chế độ 'full': sẵn sàng khi adapter đã nạp thành công (200).
        - Nếu full lỗi nhưng đang chạy fallback: trả về 503 (hoặc degraded) nếu STRICT_READINESS=true.
        - Chế độ 'light': sẵn sàng khi light model nạp thành công (200).
        - Khi model chưa nạp / nạp thất bại: trả về 503 Not Ready.
        """
        if self.serving_mode == "full":
            if self.phase23_adapter_loaded:
                return True, 200, {
                    "ready": True,
                    "status": "ready",
                    "servingMode": self.serving_mode,
                    "activeInferenceBackend": self.active_inference_backend,
                    "phase23AdapterLoaded": True,
                    "degraded": False,
                    "loadError": None,
                    "message": "Qwen3-4B + Phase23 LoRA phục vụ đầy đủ theo yêu cầu.",
                }
            elif self.is_loaded:
                # Đang chạy fallback GGUF
                if self.strict_readiness:
                    return False, 503, {
                        "ready": False,
                        "status": "degraded",
                        "servingMode": self.serving_mode,
                        "activeInferenceBackend": self.active_inference_backend,
                        "phase23AdapterLoaded": False,
                        "degraded": True,
                        "loadError": self.load_error,
                        "message": "Yêu cầu chế độ Full Qwen3-4B LoRA nhưng chỉ đang chạy fallback backend.",
                    }
                else:
                    return True, 200, {
                        "ready": True,
                        "status": "degraded",
                        "servingMode": self.serving_mode,
                        "activeInferenceBackend": self.active_inference_backend,
                        "phase23AdapterLoaded": False,
                        "degraded": True,
                        "loadError": self.load_error,
                        "message": "Đang phục vụ ở chế độ degraded fallback backend.",
                    }
            else:
                return False, 503, {
                    "ready": False,
                    "status": "not_ready",
                    "servingMode": self.serving_mode,
                    "activeInferenceBackend": self.active_inference_backend,
                    "phase23AdapterLoaded": False,
                    "degraded": False,
                    "loadError": self.load_error,
                    "message": "Model chưa được nạp hoặc nạp thất bại.",
                }
        else:  # serving_mode == 'light'
            if self.is_loaded:
                return True, 200, {
                    "ready": True,
                    "status": "ready",
                    "servingMode": self.serving_mode,
                    "activeInferenceBackend": self.active_inference_backend,
                    "phase23AdapterLoaded": False,
                    "degraded": False,
                    "loadError": None,
                    "message": "Qwen3-0.6B chế độ nhẹ sẵn sàng phục vụ.",
                }
            else:
                return False, 503, {
                    "ready": False,
                    "status": "not_ready",
                    "servingMode": self.serving_mode,
                    "activeInferenceBackend": self.active_inference_backend,
                    "phase23AdapterLoaded": False,
                    "degraded": False,
                    "loadError": self.load_error,
                    "message": "Chế độ nhẹ chưa được nạp thành công.",
                }

    def normalize_phase23_intent(
        self,
        raw_intent: Dict[str, Any],
        query: str,
        catalog: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Hậu xử lý tất định (Deterministic Schema Normalizer) cho Phase 23:
        1. Chuẩn hóa các nhãn UPDATE_CONSTRAINTS / MODIFY / UPDATE -> CONVERSATIONAL_PATCH.
        2. Chuẩn hóa quy tắc năm tất định (before/after/from-to/until).
        3. Chuẩn hóa thể loại include/exclude và tham chiếu phim.
        """
        q_lower = query.lower().strip()
        movies = catalog or DEFAULT_MOVIES

        intent: Dict[str, Any] = {
            "schema_version": "1.0",
            "intent_type": raw_intent.get("intent_type", "DISCOVERY"),
            "query": {"text": (raw_intent.get("query") or {}).get("text")},
            "reference": {
                "text": (raw_intent.get("reference") or {}).get("text"),
                "status": (raw_intent.get("reference") or {}).get("status", "NO_REFERENCE"),
            },
            "constraints": {
                "year_min": (raw_intent.get("constraints") or {}).get("year_min"),
                "year_max": (raw_intent.get("constraints") or {}).get("year_max"),
                "include_genres": list((raw_intent.get("constraints") or {}).get("include_genres") or []),
                "exclude_genres": list((raw_intent.get("constraints") or {}).get("exclude_genres") or []),
            },
            "preferences": {
                "use_personalization": (raw_intent.get("preferences") or {}).get("use_personalization"),
                "unsupported_facets": list((raw_intent.get("preferences") or {}).get("unsupported_facets") or []),
            },
            "requested_k": raw_intent.get("requested_k"),
            "diversify": raw_intent.get("diversify"),
            "clarification": {
                "required": bool((raw_intent.get("clarification") or {}).get("required", False)),
                "reason": (raw_intent.get("clarification") or {}).get("reason"),
                "question": (raw_intent.get("clarification") or {}).get("question"),
            },
            "no_op": bool(raw_intent.get("no_op", False)),
        }

        # 1. Chuẩn hóa tên intent từ Confusion Matrix của Phase 23
        if intent["intent_type"] in PATCH_INTENT_SYNONYMS or "patch_operations" in raw_intent:
            intent["intent_type"] = "CONVERSATIONAL_PATCH"
        elif intent["intent_type"] in {"NOOP", "NO_OP"}:
            intent["intent_type"] = "NO_OP"
            intent["no_op"] = True

        # Nhận diện cue hội thoại sửa đổi (CONVERSATIONAL_PATCH)
        if any(re.search(pat, q_lower) for pat in PATCH_CUE_PATTERNS):
            intent["intent_type"] = "CONVERSATIONAL_PATCH"

        # 2. Quy tắc năm tất định (Deterministic Year Rules v2.2)
        m_range = re.search(r"(?:from|between|từ(?:\s+năm)?)\s+(19\d\d|20\d\d)\s+(?:to|and|-|đến(?:\s+năm)?|tới)\s+(19\d\d|20\d\d)", q_lower)
        if m_range:
            intent["constraints"]["year_min"] = int(m_range.group(1))
            intent["constraints"]["year_max"] = int(m_range.group(2))
        else:
            m_before = re.search(r"(?:before|prior to|earlier than|trước(?:\s+năm)?)\s+(19\d\d|20\d\d)", q_lower)
            if m_before:
                intent["constraints"]["year_max"] = int(m_before.group(1)) - 1
            m_until = re.search(r"(?:until|up to|through|cho đến(?:\s+năm)?|đến(?:\s+năm)?)\s+(19\d\d|20\d\d)", q_lower)
            if m_until and not m_before:
                intent["constraints"]["year_max"] = int(m_until.group(1))

            m_after = re.search(r"(?:after|later than|sau(?:\s+năm)?)\s+(19\d\d|20\d\d)", q_lower)
            if m_after:
                intent["constraints"]["year_min"] = int(m_after.group(1)) + 1
            m_since = re.search(r"(?:since|from|từ(?:\s+năm)?)\s+(19\d\d|20\d\d)(?:\s+onwards|\s+trở đi)?", q_lower)
            if m_since and not m_after:
                intent["constraints"]["year_min"] = int(m_since.group(1))

            if intent["constraints"]["year_min"] is None and intent["constraints"]["year_max"] is None:
                m_exact = re.search(r"\b(?:năm|year|in|phát hành)\s+(19\d\d|20\d\d)\b", q_lower)
                if m_exact:
                    y = int(m_exact.group(1))
                    intent["constraints"]["year_min"] = y
                    intent["constraints"]["year_max"] = y

        # 3. Trích xuất thể loại Include / Exclude
        neg_clauses = re.findall(
            r"(?:không(?:\s+có|\s+thích|\s+muốn)?|trừ|loại bỏ|bỏ(?:\s+thể loại)?|without|no|exclude|excluding|not)\s+([^,.!?;]+)",
            q_lower
        )
        neg_text = " ".join(neg_clauses)

        for canonical_genre, keywords in GENRE_SYNONYMS.items():
            for kw in keywords:
                if re.search(r"\b" + re.escape(kw) + r"\b", neg_text):
                    if canonical_genre not in intent["constraints"]["exclude_genres"]:
                        intent["constraints"]["exclude_genres"].append(canonical_genre)
                elif re.search(r"\b" + re.escape(kw) + r"\b", q_lower):
                    if canonical_genre not in intent["constraints"]["exclude_genres"]:
                        if canonical_genre not in intent["constraints"]["include_genres"]:
                            intent["constraints"]["include_genres"].append(canonical_genre)

        # 4. Trích xuất số lượng requested_k
        m_k = re.search(r"\b(?:top|gợi ý|tìm|find|give me|show me|make it|change(?:d)?(?:\s+the\s+count)?\s+to|đổi thành|lấy)\s+(\d+)\s*(?:phim|movies|films|bộ|tác phẩm|kết quả)?\b", q_lower)
        if not m_k:
            m_k = re.search(r"\b(\d+)\s+(?:phim|animated movies|movies|films|bộ phim)\b", q_lower)
        if m_k:
            val_k = int(m_k.group(1))
            if not (1900 <= val_k <= 2035):
                intent["requested_k"] = val_k

        # 5. Nhận diện Reference Film
        for m in movies:
            title_low = m["title"].lower()
            if title_low in q_lower:
                intent["reference"]["text"] = m["title"]
                intent["reference"]["status"] = "CLEAR_REFERENCE_TEXT"
                break
        if intent["reference"]["status"] == "NO_REFERENCE":
            m_ref = re.search(r"(?:giống(?:\s+phim)?|tương tự(?:\s+phim)?|like|similar to)\s+([A-Z][\w\s:'\-]{2,35})", query)
            if m_ref:
                ref_candidate = m_ref.group(1).strip()
                for stop_w in ["nhưng", "mà", "không", "but", "without", "with", "under", "before", "after"]:
                    idx = ref_candidate.lower().find(f" {stop_w}")
                    if idx != -1:
                        ref_candidate = ref_candidate[:idx].strip()
                if ref_candidate:
                    intent["reference"]["text"] = ref_candidate
                    intent["reference"]["status"] = "CLEAR_REFERENCE_TEXT"

        # 6. Kiểm tra điều kiện Clarification theo chuẩn v2.2
        ymin = intent["constraints"]["year_min"]
        ymax = intent["constraints"]["year_max"]
        if ymin is not None and ymax is not None and ymin > ymax:
            intent["intent_type"] = "CLARIFICATION"
            intent["clarification"] = {
                "required": True,
                "reason": "CONFLICTING_CONSTRAINTS",
                "question": f"Khoảng năm bạn yêu cầu bị mâu thuẫn (từ {ymin} đến {ymax}). Bạn muốn tìm phim trong khoảng năm nào chính xác?"
            }

        rk = intent["requested_k"]
        if rk is not None and (rk < 1 or rk > 100):
            intent["intent_type"] = "CLARIFICATION"
            intent["clarification"] = {
                "required": True,
                "reason": "INVALID_REQUESTED_K",
                "question": "Số lượng phim yêu cầu phải nằm trong khoảng từ 1 đến 100. Bạn muốn nhận bao nhiêu gợi ý?"
            }

        # In CATALOG-01, animation discovery queries (targeting scenes, episodes, characters, keywords)
        # should never be blocked by spurious model CLARIFICATION unless there are true conflicting constraints
        has_true_conflict = (
            (ymin is not None and ymax is not None and ymin > ymax) or
            (rk is not None and (rk < 1 or rk > 100))
        )
        if intent["intent_type"] == "CLARIFICATION" and not has_true_conflict:
            q_has_cues = any(w in q_lower for w in ("phân cảnh", "cảnh", "tập", "đoạn", "truyện", "nhân vật", "tìm", "xem", "chiếu", "phim"))
            if q_has_cues or len(q_lower.split()) >= 3:
                intent["intent_type"] = "DISCOVERY"
                intent["clarification"]["required"] = False
                intent["clarification"]["reason"] = None
                intent["clarification"]["question"] = None
                if not intent["query"]["text"]:
                    intent["query"]["text"] = query

        # 7. Xây dựng patch_operations nếu là CONVERSATIONAL_PATCH
        if intent["intent_type"] == "CONVERSATIONAL_PATCH":
            ops = list(raw_intent.get("patch_operations") or [])
            if not ops:
                if ymin is not None:
                    ops.append({"op": "SET", "path": "constraints.year_min", "value": ymin})
                if ymax is not None:
                    ops.append({"op": "SET", "path": "constraints.year_max", "value": ymax})
                if intent["constraints"]["include_genres"]:
                    ops.append({"op": "SET", "path": "constraints.include_genres", "value": intent["constraints"]["include_genres"]})
                if intent["constraints"]["exclude_genres"]:
                    ops.append({"op": "SET", "path": "constraints.exclude_genres", "value": intent["constraints"]["exclude_genres"]})
                if rk is not None:
                    ops.append({"op": "SET", "path": "requested_k", "value": rk})
            intent["patch_operations"] = ops

        if intent["query"]["text"] is None and intent["intent_type"] == "DISCOVERY":
            intent["query"]["text"] = query

        # Đồng bộ cả nested schema v1 lẫn top-level alias cho Frontend UI
        intent["year_min"] = intent["constraints"]["year_min"]
        intent["year_max"] = intent["constraints"]["year_max"]
        intent["include_genres"] = intent["constraints"]["include_genres"]
        intent["exclude_genres"] = intent["constraints"]["exclude_genres"]
        intent["reference_films"] = [intent["reference"]["text"]] if intent["reference"].get("text") else []

        return intent

    def parse_discovery_intent(
        self,
        query: str,
        history: Optional[List[Dict[str, Any]]] = None,
        catalog: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Tầng 1 (Phase 23 Intent Parser):
        Chuyển câu truy vấn tự nhiên thành đối tượng StructuredDiscoveryIntent v1 chuẩn hóa.
        """
        if not self.is_loaded:
            self.load_model()

        # 1. Kiểm tra tính sẵn sàng khi ở chế độ Full Mode và Fallback bị tắt
        if self.serving_mode == "full" and not self.enable_fallback:
            if not self.is_loaded or not self.phase23_adapter_loaded or self.model is None or self.tokenizer is None:
                err_detail = self.load_error or "Mô hình Qwen3-4B + Phase 23 LoRA chưa sẵn sàng và ENABLE_FALLBACK=false."
                raise ModelNotReadyError(f"Mô hình chưa sẵn sàng phục vụ (HTTP 503): {err_detail}")

        raw_parsed: Dict[str, Any] = {}

        # 2. Thực thi suy luận qua Full Qwen3-4B + Phase 23 PEFT LoRA trên GPU
        if self.is_loaded and not self.is_gguf and self.model and self.tokenizer:
            clean_text = ""
            try:
                import torch
                messages = [
                    {"role": "system", "content": self.system_prompt_v2_2},
                    {"role": "user", "content": query}
                ]
                try:
                    prompt_text = self.tokenizer.apply_chat_template(
                        messages, tokenize=False, add_generation_prompt=True, enable_thinking=False
                    )
                except TypeError:
                    prompt_text = self.tokenizer.apply_chat_template(
                        messages, tokenize=False, add_generation_prompt=True
                    )
                with self.acquire_inference_slot():
                    inputs = self.tokenizer(prompt_text, return_tensors="pt").to(self.model.device)
                    with torch.no_grad():
                        out_ids = self.model.generate(
                            **inputs,
                            max_new_tokens=self.max_new_tokens,
                            do_sample=False,
                            pad_token_id=self.tokenizer.eos_token_id
                        )
                    raw_text = self.tokenizer.decode(out_ids[0][inputs.input_ids.shape[1]:], skip_special_tokens=True).strip()
                    clean_text = re.sub(r"<think>.*?</think>", "", raw_text, flags=re.DOTALL).strip()
            except InferenceCapacityError:
                raise
            except Exception as gen_err:
                logger.error(f"Lỗi suy luận sinh văn bản từ PEFT model: {gen_err}")
                if self.serving_mode == "full" and not self.enable_fallback:
                    raise InferenceGenerationError(f"Lỗi suy luận sinh văn bản từ Qwen3-4B LoRA: {str(gen_err)}")
                clean_text = ""

            try:
                if clean_text:
                    parsed_json = json.loads(clean_text)
                    if not isinstance(parsed_json, dict):
                        raise ValueError(f"Output của model không phải là JSON object (dict): {type(parsed_json)}")
                    raw_parsed = parsed_json
                else:
                    raise ValueError("Output sinh ra từ model rỗng.")
            except Exception as json_err:
                logger.error(f"Lỗi phân tích cú pháp JSON từ output của model: {json_err}")
                if self.serving_mode == "full" and not self.enable_fallback:
                    raise ModelOutputParseError(f"Mô hình Qwen3-4B LoRA trả về JSON không hợp lệ: {str(json_err)} | Output thô: {clean_text[:200]}")
                raw_parsed = {}

        return self.normalize_phase23_intent(raw_parsed, query, catalog)

    def generate_grounded_explanation(
        self,
        query: str,
        structured_intent: Dict[str, Any],
        ranked_movies: List[Dict[str, Any]],
        history: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """
        Tầng 5 (Qwen Grounded Explanation Generator):
        Sinh lời tư vấn điện ảnh bằng tiếng Việt bám sát kết quả xếp hạng và ràng buộc đã bóc tách.
        """
        if not self.is_loaded:
            self.load_model()

        if structured_intent.get("intent_type") == "CLARIFICATION":
            clar = structured_intent.get("clarification") or {}
            return clar.get("question") or "Yêu cầu của bạn chưa đủ rõ ràng hoặc có mâu thuẫn. Bạn có thể nói rõ hơn được không?"

        if not ranked_movies:
            return (
                "Tôi đã kiểm tra toàn bộ kho phim theo các ràng buộc khắt khe của bạn "
                "(về năm phát hành và thể loại loại trừ), nhưng hiện chưa có tác phẩm nào khớp 100%. "
                "Bạn có muốn nới lỏng bớt điều kiện năm hoặc thể loại không?"
            )

        cons = structured_intent.get("constraints") or {}
        inc = ", ".join(cons.get("include_genres") or [])
        exc = ", ".join(cons.get("exclude_genres") or [])
        ymin = cons.get("year_min")
        ymax = cons.get("year_max")
        ref_title = (structured_intent.get("reference") or {}).get("text")

        movies_desc = "\n".join(
            f"- {m['title']} ({m['year']}, {m['rating']}★, Thể loại: {', '.join(m.get('genres', []))}): {m.get('description', '')}"
            for m in ranked_movies
        )

        system_prompt = (
            "Bạn là CineBot - trợ lý khám phá điện ảnh & hoạt hình thông minh của Dippie Cinema.\n"
            "Hãy trả lời ngắn gọn (2-4 câu), tự nhiên, cuốn hút bằng tiếng Việt, giới thiệu trực tiếp các phim đã được tuyển chọn bên dưới.\n"
            "TUYỆT ĐỐI chỉ nhắc đến các phim trong danh sách kết quả dưới đây, không tự bịa thêm tên phim ngoài danh sách.\n\n"
            f"Danh sách phim phù hợp nhất đã được hệ thống xếp hạng:\n{movies_desc}\n"
        )
        if inc:
            system_prompt += f"\n- Thể loại ưu tiên: {inc}"
        if exc:
            system_prompt += f"\n- Đã loại trừ hoàn toàn thể loại: {exc}"
        if ymin or ymax:
            system_prompt += f"\n- Khoảng năm phát hành: {ymin or '...'} - {ymax or '...'}"
        if ref_title:
            system_prompt += f"\n- Tương đồng với tác phẩm tham chiếu: {ref_title}"

        if self.is_loaded and self.is_gguf and self.llama_model:
            try:
                llama_messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Yêu cầu của tôi: {query}. Hãy giới thiệu các phim phù hợp nhất ở trên."}
                ]
                with self.acquire_inference_slot():
                    output = self.llama_model.create_chat_completion(
                        messages=llama_messages,
                        max_tokens=220,
                        temperature=0.5
                    )
                raw_text = output["choices"][0]["message"]["content"].strip()
                cleaned = re.sub(r"<think>.*?</think>", "", raw_text, flags=re.DOTALL).strip()
                if cleaned:
                    return cleaned
            except InferenceCapacityError:
                raise
            except Exception as e:
                logger.warning(f"Lỗi sinh lời giải thích qua GGUF: {e}")

        # Lời giải thích chuẩn xác bám sát dữ liệu (Grounded Explanation)
        top = ranked_movies[0]
        others = ", ".join(f"**{m['title']}** ({m['year']})" for m in ranked_movies[1:])
        parts = []
        if ref_title:
            parts.append(f"Dựa trên điểm tương đồng về phong cách với **{ref_title}**")
        elif inc:
            parts.append(f"Dựa trên gu thể loại **{inc}** của bạn")
        else:
            parts.append("Dựa trên phân tích ngữ nghĩa yêu cầu của bạn")

        if exc:
            parts.append(f"(đã lọc bỏ hoàn toàn thể loại **{exc}**)")
        if ymin or ymax:
            parts.append(f"trong khoảng năm **{ymin or '...'}–{ymax or '...'}**")

        intro = " ".join(parts)
        reply = (
            f"{intro}, tôi đề xuất hàng đầu tác phẩm **{top['title']}** ({top['year']} · {top['rating']}★) — "
            f"{top.get('description', '')}"
        )
        if others:
            reply += f" Ngoài ra, bạn cũng nên trải nghiệm thêm {others}."
        return reply

    def generate_chat_response(
        self,
        query: str,
        messages_history: Optional[List[Dict[str, Any]]] = None,
        available_movies: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Phương thức tương thích ngược: Ủy quyền sang Cascading Pipeline 5 tầng"""
        from services.ai_pipeline import cascading_pipeline
        return cascading_pipeline.run(
            query=query,
            catalog=available_movies,
            history=messages_history
        )


qwen_service = QwenRecommendationService()
