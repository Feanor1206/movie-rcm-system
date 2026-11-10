import argparse
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend" / "fastapi"))

from services.catalog_sync import CatalogSyncManager
from services.encoders import OnnxTextEncoder, artifact_fingerprint, artifact_path
from services.text_index import prepare_embeddings


class TorchOfflineEncoder:
    def __init__(self, source, serving_artifact, *, batch_size=4, device="cuda"):
        config = json.loads(artifact_path(serving_artifact, "encoder.json").read_text(encoding="utf-8"))
        if config.get("source_model_fingerprint") != artifact_fingerprint(source):
            raise ValueError("Serving artifact must identify the exact offline source_model_fingerprint")
        import torch
        from transformers import AutoModel, AutoTokenizer

        if device == "cuda" and not torch.cuda.is_available():
            raise ValueError("CUDA is unavailable; select --device cpu for ONNX preparation explicitly")
        self.torch = torch
        self.device = device
        self.config = config
        self.batch_size = batch_size
        self.tokenizer = AutoTokenizer.from_pretrained(str(source), local_files_only=True, trust_remote_code=False)
        self.model = AutoModel.from_pretrained(str(source), local_files_only=True, trust_remote_code=False)
        self.model.to(device=device, dtype=torch.float16 if device == "cuda" else torch.float32).eval()
        self.model_id = artifact_fingerprint(serving_artifact)

    def _encode(self, texts, prefix):
        values = []
        with self.torch.inference_mode():
            for start in range(0, len(texts), self.batch_size):
                inputs = self.tokenizer([prefix + text for text in texts[start:start + self.batch_size]],
                                        padding=True, truncation=True, max_length=self.config.get("max_length", 512),
                                        return_tensors="pt").to(self.device)
                output = self.model(**inputs).last_hidden_state
                if self.config.get("pooling", "cls") == "mean":
                    mask = inputs["attention_mask"].unsqueeze(-1)
                    output = (output * mask).sum(dim=1) / mask.sum(dim=1).clamp(min=1)
                else:
                    output = output[:, 0]
                values.append(self.torch.nn.functional.normalize(output.float(), dim=1).cpu().numpy())
        return np.concatenate(values) if values else np.empty((0, 0), dtype=np.float32)

    def encode_documents(self, texts):
        return self._encode(texts, self.config.get("document_prefix", ""))

    def encode_queries(self, texts):
        return self._encode(texts, self.config.get("query_prefix", ""))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--cache-dir", type=Path, default=ROOT / "data" / "indices" / "text")
    parser.add_argument("--device", choices=("cuda", "cpu"), default="cuda")
    parser.add_argument("--torch-model", type=Path)
    parser.add_argument("--batch-size", type=int, default=4)
    args = parser.parse_args()
    if args.batch_size < 1 or args.batch_size > 64:
        parser.error("batch-size must be between 1 and 64")
    if args.device == "cuda" and args.torch_model is None:
        parser.error("CUDA preparation requires --torch-model and a matching source fingerprint in encoder.json")
    try:
        payload = json.loads(args.catalog.read_text(encoding="utf-8"))
        manager = CatalogSyncManager()
        manager.load_from_payload(payload, include_draft=False, include_private=False)
        encoder = (TorchOfflineEncoder(args.torch_model, args.artifact, batch_size=args.batch_size)
                   if args.device == "cuda" else OnnxTextEncoder.from_directory(args.artifact))
        index = prepare_embeddings(manager.get_flattened_catalog(), cache_dir=args.cache_dir,
                                   encoder=encoder, model_id=encoder.model_id,
                                   payload=payload, content_hash=manager.content_hash)
    except (OSError, ValueError, RuntimeError) as exc:
        parser.error(str(exc))
    print(json.dumps({"modelId": encoder.model_id, "documents": len(index.documents),
                      "denseReady": index.dense_ready, "missingEmbeddings": index.missing_embeddings,
                      "matrixPath": str(index.matrix_path) if index.matrix_path else None}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
