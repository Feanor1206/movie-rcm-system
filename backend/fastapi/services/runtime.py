import json
import logging
import os
import shlex
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import HTTPException

from services.catalog_sync import AcceptedSnapshot, CatalogSyncManager
from services.model_registry import ModelRegistry
from services.text_index import TextIndex, prepare_embeddings


logger = logging.getLogger(__name__)
ROOT = next((parent for parent in Path(__file__).resolve().parents if (parent / "backend/fastapi").is_dir()),
            Path(__file__).resolve().parents[1])


class Runtime:
    def __init__(self, *, sync_secret=None, sync_path=None, cache_dir=None,
                 load_default=True, model_mode=None, max_delta_documents=64):
        self.sync_secret = sync_secret if sync_secret is not None else os.getenv("CATALOG_SYNC_TOKEN", os.getenv("FASTAPI_SYNC_SECRET", "")).strip()
        self.sync_path = Path(sync_path or os.getenv("SYNC_STATE_PATH", ROOT / "data/indices/catalog_sync_state.json"))
        self.cache_dir = Path(cache_dir or os.getenv("EMBEDDING_CACHE_DIR", ROOT / "data/indices/text"))
        self.load_default = load_default
        self.registry = ModelRegistry(mode=model_mode)
        self.snapshot = None
        self.publish_lock = threading.RLock()
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="index-delta")
        self.pending = None
        self.max_delta_documents = max_delta_documents
        self.recovery_error = None
        self.chat = None
        self.search = None
        self.llm = None

    def build_index(self, manager, *, payload=None):
        encoder = self.registry.get("embedder")
        return TextIndex.build(manager.get_flattened_catalog(), cache_dir=self.cache_dir, encoder=encoder,
            model_id=getattr(encoder, "model_id", "lexical"), encode_missing=False,
            content_hash=manager.content_hash or "", payload=payload)

    def save(self, snapshot):
        self._write_json(self.sync_path, {"generation": snapshot.generation, "content_hash": snapshot.content_hash,
                                         "catalog": snapshot.payload})

    @staticmethod
    def _write_json(path, payload):
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary = tempfile.mkstemp(prefix=f"{path.stem}-", suffix=".tmp", dir=path.parent)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                json.dump(payload, stream, ensure_ascii=False)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            Path(temporary).unlink(missing_ok=True)

    def restore(self):
        if self.sync_path.exists():
            try:
                saved = json.loads(self.sync_path.read_text(encoding="utf-8"))
                manager = CatalogSyncManager()
                manager.load_from_payload(saved["catalog"], include_draft=False, include_private=False)
                generation = saved["generation"]
                if not isinstance(generation, int) or isinstance(generation, bool) or generation < 0:
                    raise ValueError("Invalid saved generation")
                if manager.content_hash != saved["content_hash"]:
                    raise ValueError("Saved catalog hash does not match")
                self.snapshot = AcceptedSnapshot(generation, manager.content_hash, manager,
                    self.build_index(manager, payload=saved["catalog"]), saved["catalog"])
            except Exception:
                logger.exception("Accepted snapshot recovery failed")
                self.recovery_error = "Không thể phục hồi snapshot đã chấp nhận."
            return
        if self.load_default:
            manager = CatalogSyncManager()
            if manager.load_default_catalog():
                payload = manager._raw_catalog
                self.snapshot = AcceptedSnapshot(0, manager.content_hash, manager,
                    self.build_index(manager, payload=payload), payload)

    def acknowledgement(self, status="success", message="Đã đồng bộ catalog."):
        snapshot = self.snapshot
        return dict(status=status, message=message, generation=snapshot.generation if snapshot else 0,
                    content_hash=snapshot.content_hash if snapshot else "",
                    item_counts=snapshot.catalog_manager.item_counts if snapshot else {},
                    index_ready=snapshot is not None and snapshot.is_ready)

    def compare(self, generation, content_hash=None):
        snapshot = self.snapshot
        if snapshot is None or generation is None:
            return None
        if generation < snapshot.generation:
            return self.acknowledgement("SKIPPED", "Bỏ qua snapshot generation cũ.")
        if generation == snapshot.generation and content_hash is not None:
            if content_hash != snapshot.content_hash:
                raise HTTPException(409, "Generation đã có nội dung khác.")
            return self.acknowledgement("UNCHANGED", "Snapshot đã được chấp nhận.")
        return None

    def publish(self, manager, index, generation, payload):
        with self.publish_lock:
            existing = self.compare(generation, manager.content_hash)
            if existing:
                return existing
            target_generation = generation if generation is not None else (self.snapshot.generation + 1 if self.snapshot else 1)
            snapshot = AcceptedSnapshot(target_generation, manager.content_hash, manager, index, payload)
            self.save(snapshot)
            self.snapshot = snapshot
            return self.acknowledgement()

    def prepare_delta(self, manager, generation, payload):
        encoder = self.registry.get("embedder")
        try:
            prepare_embeddings(manager.get_flattened_catalog(), cache_dir=self.cache_dir,
                encoder=encoder, model_id=encoder.model_id, payload=payload)
            index = self.build_index(manager, payload=payload)
            self.publish(manager, index, generation, payload)
        except Exception:
            logger.exception("Background index preparation failed")
            with self.publish_lock:
                if self.pending is not None:
                    self.pending["error"] = "Không thể chuẩn bị chỉ mục."
        finally:
            with self.publish_lock:
                if self.pending is not None:
                    self.pending["finished"] = True

    def queue_delta(self, manager, index, generation, payload):
        if index.missing_embeddings > self.max_delta_documents:
            return self.cache_required(manager, generation, payload, index.missing_embeddings)
        with self.publish_lock:
            existing = self.compare(generation, manager.content_hash)
            if existing:
                return existing, 200
            if (self.pending and self.pending["finished"] and self.pending["error"]
                    and self.pending["generation"] == generation
                    and self.pending["content_hash"] == manager.content_hash):
                error = self.pending["error"]
                self.pending = None
                raise HTTPException(500, error)
            if self.pending and not self.pending["finished"]:
                if self.pending["generation"] == generation and self.pending["content_hash"] != manager.content_hash:
                    raise HTTPException(409, "Generation đang chuẩn bị có nội dung khác.")
                if self.pending["content_hash"] != manager.content_hash or self.pending["generation"] != generation:
                    raise HTTPException(429, "Một chỉ mục khác đang được chuẩn bị.", headers={"Retry-After": "2"})
            else:
                self.pending = dict(generation=generation, content_hash=manager.content_hash, finished=False, error=None)
                self.executor.submit(self.prepare_delta, manager, generation, payload)
            return dict(status="BUILDING", message="Đang chuẩn bị embedding mới trong nền.", generation=generation,
                        content_hash=manager.content_hash, item_counts=manager.item_counts, index_ready=False), 202

    def cache_required(self, manager, generation, payload, missing_embeddings):
        candidate = self.cache_dir.resolve() / "pending-catalogs" / f"{manager.content_hash}.json"
        if not candidate.exists():
            self._write_json(candidate, payload)
        artifact = Path(os.getenv("TEXT_ENCODER_PATH") or os.getenv("EMBEDDER_PATH") or ROOT / "ai/models/text-onnx").resolve()

        def quote(path):
            value = str(path)
            return "'" + value.replace("'", "''") + "'" if os.name == "nt" else shlex.quote(value)

        command = (f"python {quote(ROOT / 'ai/build_text_embeddings.py')} --catalog {quote(candidate)} "
                   f"--artifact {quote(artifact)} --cache-dir {quote(self.cache_dir.resolve())} --device cpu")
        with self.publish_lock:
            existing = self.compare(generation, manager.content_hash)
            if existing:
                return existing, 200
        return dict(status="CACHE_REQUIRED", message="Dựng cache offline rồi thử đồng bộ lại.",
                    generation=generation, content_hash=manager.content_hash, item_counts=manager.item_counts,
                    index_ready=False, missing_embeddings=missing_embeddings, cache_command=command), 503

    def sync(self, request):
        with self.publish_lock:
            generation = request.generation if request.generation is not None else (self.snapshot.generation + 1 if self.snapshot else 1)
            existing = self.compare(generation)
            if existing:
                return existing, 200
        manager = CatalogSyncManager()
        if request.catalog is not None:
            payload = request.catalog
            manager.load_from_payload(payload, include_draft=False, include_private=False)
        else:
            if not manager.load_default_catalog():
                raise HTTPException(404, "Không tìm thấy catalog hợp lệ để đồng bộ.")
            payload = manager._raw_catalog
        if request.content_hash and request.content_hash.lower() != manager.content_hash.lower():
            raise HTTPException(400, "Mã băm catalog không khớp.")
        with self.publish_lock:
            existing = self.compare(generation, manager.content_hash)
            if existing:
                return existing, 200
            if request.force_rebuild and self.pending and self.pending["finished"]:
                self.pending = None
        index = self.build_index(manager, payload=payload)
        if self.registry.get("embedder") is not None and index.missing_embeddings:
            return self.queue_delta(manager, index, generation, payload)
        return self.publish(manager, index, generation, payload), 200

    def close(self):
        self.executor.shutdown(wait=True, cancel_futures=True)
