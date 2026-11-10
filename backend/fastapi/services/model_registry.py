import asyncio
import logging
import os
import json
import threading
import time
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path


logger = logging.getLogger(__name__)


class InferenceCapacityError(Exception):
    pass


class ModelRegistry:
    def __init__(self, mode=None, gpu_timeout=30.0):
        self.mode = (mode or os.getenv("MODEL_MODE") or os.getenv("SERVING_MODE") or "light").lower()
        if self.mode not in {"light", "full", "cloud"}:
            raise ValueError("Model mode must be light, full or cloud")
        self.gpu_timeout = gpu_timeout
        self._gpu = threading.BoundedSemaphore(1)
        self._lock = threading.RLock()
        self.models = {}
        self._factories = {}
        self.errors = {}
        self.llm_ready = False
        self.llm_error = None
        embedder_path = os.getenv("TEXT_ENCODER_PATH") or os.getenv("EMBEDDER_PATH")
        if embedder_path:
            self.register("embedder", lambda: self._load_embedder(embedder_path))
        reranker_path = os.getenv("RERANKER_MODEL_PATH")
        if reranker_path:
            self.register("reranker", lambda: TorchScriptReranker(reranker_path), gpu=True)

    @staticmethod
    def _load_embedder(path):
        from services.encoders import OnnxTextEncoder
        return OnnxTextEncoder.from_directory(path)

    def register(self, name, factory, *, gpu=False):
        with self._lock:
            if name in self.models:
                raise ValueError(f"Model already loaded: {name}")
            self.errors.pop(name, None)
            self._factories[name] = (factory, gpu)

    def get(self, name, default=None):
        with self._lock:
            if name in self.models:
                return self.models[name]
            if name in self.errors:
                return default
            registration = self._factories.get(name)
            if registration is None:
                return default
            factory, gpu = registration
            try:
                if gpu:
                    with self.gpu_slot():
                        model = factory()
                else:
                    model = factory()
                if model is None:
                    raise ValueError("Model loader returned no model")
            except Exception:
                logger.exception("Unable to load configured %s model", name)
                self.errors[name] = "Configured model could not be loaded"
                return default
            self.models[name] = model
            self.errors.pop(name, None)
            return model

    async def initialize(self):
        for name in ("embedder", "reranker", "frame_encoder", "frame_search"):
            if name in self._factories:
                await asyncio.to_thread(self.get, name)

    @contextmanager
    def gpu_slot(self, timeout=None):
        acquired = self._gpu.acquire(timeout=self.gpu_timeout if timeout is None else timeout)
        if not acquired:
            raise InferenceCapacityError("GPU đang bận. Vui lòng thử lại sau.")
        try:
            yield
        finally:
            self._gpu.release()

    @asynccontextmanager
    async def async_gpu_slot(self, timeout=None):
        deadline = time.monotonic() + (self.gpu_timeout if timeout is None else timeout)
        while not self._gpu.acquire(blocking=False):
            if time.monotonic() >= deadline:
                raise InferenceCapacityError("GPU đang bận. Vui lòng thử lại sau.")
            await asyncio.sleep(min(0.01, max(0, deadline - time.monotonic())))
        try:
            yield
        finally:
            self._gpu.release()

    def set_llm_status(self, ready, error=None):
        self.llm_ready = ready
        self.llm_error = error if not ready else None

    def health(self):
        backend = {"light": "template", "full": "llama-server", "cloud": "deepseek"}[self.mode]
        return {
            "status": "healthy" if self.mode == "light" or self.llm_ready else "degraded",
            "modelLoaded": self.llm_ready,
            "modelNameOrPath": os.getenv("LLM_MODEL", "Qwen3-4B-GGUF") if self.mode == "full" else "deepseek-chat" if self.mode == "cloud" else "catalog-template",
            "activeBaseModelName": os.getenv("LLM_MODEL", "Qwen3-4B-GGUF") if self.mode == "full" and self.llm_ready else None,
            "activeInferenceBackend": backend,
            "device": "external" if self.mode == "full" else "cpu",
            "servingMode": self.mode,
            "requestedDevice": "external" if self.mode == "full" else "cpu",
            "actualDevice": "external" if self.mode == "full" and self.llm_ready else "cpu",
            "quantization": "external" if self.mode == "full" else "none",
            "phase23AdapterLoaded": False,
            "degraded": self.mode != "light" and not self.llm_ready,
            "loadError": self.llm_error,
        }

    def readiness(self, snapshot=None):
        index = getattr(snapshot, "hybrid_index", None)
        search_ready = bool(snapshot is not None and getattr(snapshot, "is_ready", False) and index is not None and getattr(index, "is_ready", False))
        frame_ready = search_ready and "frame_search" in self.models
        backend = self.health()["activeInferenceBackend"]
        features = {
            "search": {"ready": search_ready, "backend": "dense-hybrid" if getattr(index, "dense_ready", False) else "lexical"},
            "frameSearch": {"ready": frame_ready, "reason": None if frame_ready else "Frame encoder/index assets are not loaded"},
            "recommend": {"ready": search_ready, "backend": "catalog-cpu"},
            "chat": {"ready": search_ready, "backend": backend if self.llm_ready else "template", "degraded": self.mode != "light" and not self.llm_ready},
            "llm": {"ready": self.llm_ready, "backend": backend, "reason": None if self.llm_ready else self.llm_error or ("LLM is disabled in light mode" if self.mode == "light" else "LLM has not passed a provider request")},
            "rerank": {"ready": "reranker" in self.models, "reason": self.errors.get("reranker")},
        }
        return {
            "ready": search_ready,
            "status": "ready" if search_ready else "not_ready",
            "servingMode": self.mode,
            "activeInferenceBackend": backend,
            "phase23AdapterLoaded": False,
            "degraded": self.mode != "light" and not self.llm_ready,
            "loadError": self.llm_error,
            "message": "Catalog features are ready" if search_ready else "No accepted catalog index is available",
            "features": features,
        }


class TorchScriptReranker:
    def __init__(self, directory):
        import torch
        from services.encoders import LocalTokenizer, artifact_fingerprint
        directory = Path(directory).resolve()
        config = json.loads((directory / "reranker.json").read_text(encoding="utf-8"))
        model_path = (directory / config.get("model_file", "model.pt")).resolve()
        if directory not in model_path.parents:
            raise ValueError("Reranker model must be inside its artifact directory")
        requested_device = os.getenv("RERANKER_DEVICE", "auto")
        if requested_device not in {"auto", "cpu", "cuda"}:
            raise ValueError("RERANKER_DEVICE must be auto, cpu or cuda")
        self.device = "cuda" if requested_device == "cuda" or requested_device == "auto" and torch.cuda.is_available() else "cpu"
        self.tokenizer = LocalTokenizer.from_directory(directory, config=config)
        self.input_names = config.get("input_names", ["input_ids", "attention_mask"])
        if not isinstance(self.input_names, list) or not self.input_names or any(name not in {"input_ids", "attention_mask", "token_type_ids"} for name in self.input_names):
            raise ValueError("Invalid reranker input_names")
        self.model = torch.jit.load(str(model_path), map_location=self.device).eval()
        self.model_id = artifact_fingerprint(directory).replace("onnx-text:", "torchscript-rerank:", 1)

    def __call__(self, query, documents):
        import numpy as np
        import torch
        if not documents:
            return []
        encoded = self.tokenizer.encode([(query, document) for document in documents])
        inputs = [torch.as_tensor(encoded[name], device=self.device) for name in self.input_names]
        with torch.inference_mode():
            output = self.model(*inputs)
        if isinstance(output, dict):
            output = output["logits"]
        if isinstance(output, tuple):
            output = output[0]
        scores = output.detach().float().cpu().numpy()
        if scores.shape not in {(len(documents),), (len(documents), 1)} or not np.isfinite(scores).all():
            raise ValueError("Reranker returned invalid scores")
        return scores.reshape(-1).tolist()
