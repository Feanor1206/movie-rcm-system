import argparse
import gc
import hashlib
import json
from pathlib import Path
import random
import shutil
import sys
from tempfile import TemporaryDirectory

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend" / "fastapi"))

from services.catalog_sync import CatalogSyncManager
from services.encoders import OnnxTextEncoder, artifact_fingerprint, artifact_path
from services.text_index import TextIndex, document_text


def load_source_model(source):
    import torch
    from transformers import AutoModel

    return AutoModel.from_pretrained(
        str(source), local_files_only=True, trust_remote_code=False, weights_only=True,
        dtype=torch.float32, attn_implementation="eager", low_cpu_mem_usage=True,
    ).eval()


def export_fp32(source, target):
    import torch

    class DenseCLS(torch.nn.Module):
        def __init__(self, model):
            super().__init__()
            self.model = model

        def forward(self, input_ids, attention_mask):
            return self.model(input_ids=input_ids, attention_mask=attention_mask).last_hidden_state[:, 0]

    model = DenseCLS(load_source_model(source)).eval()
    sample = (torch.zeros((2, 8), dtype=torch.long), torch.ones((2, 8), dtype=torch.long))
    with torch.inference_mode():
        torch.onnx.export(
            model, sample, str(target), input_names=["input_ids", "attention_mask"],
            output_names=["sentence_embedding"], opset_version=17, dynamo=False,
            external_data=True,
            dynamic_axes={"input_ids": {0: "batch", 1: "sequence"},
                          "attention_mask": {0: "batch", 1: "sequence"},
                          "sentence_embedding": {0: "batch"}},
        )


def export_artifacts(source, output, *, max_length=512):
    import onnx
    from onnxruntime.quantization import QuantType, quantize_dynamic
    from tokenizers import Tokenizer

    source, output = Path(source).resolve(strict=True), Path(output).resolve()
    if output.exists() or output.is_relative_to(source):
        raise ValueError("Output must be a new directory outside the model source")
    if not 8 <= max_length <= 8192:
        raise ValueError("max-length must be between 8 and 8192")
    tokenizer_path = artifact_path(source, "tokenizer.json")
    pad_id = Tokenizer.from_file(str(tokenizer_path)).token_to_id("<pad>")
    if pad_id is None:
        raise ValueError("The BGE-M3 tokenizer must define <pad>")
    source_fingerprint = artifact_fingerprint(source)
    output.parent.mkdir(parents=True, exist_ok=True)

    with TemporaryDirectory(prefix="bge-export-", dir=output.parent) as temporary:
        stage = Path(temporary) / "artifacts"
        fp32 = stage / "fp32"
        int8 = stage / "int8"
        fp32.mkdir(parents=True)
        int8.mkdir()
        fp32_model = fp32 / "model.onnx"
        export_fp32(source, fp32_model)
        gc.collect()
        quantize_dynamic(
            fp32_model, int8 / "model.onnx", op_types_to_quantize=["MatMul", "Gemm"],
            per_channel=True, weight_type=QuantType.QInt8, use_external_data_format=True,
        )
        graph = onnx.load(str(int8 / "model.onnx"), load_external_data=False)
        if not any(node.op_type == "MatMulInteger" for node in graph.graph.node):
            raise RuntimeError("ONNX Runtime did not quantize any matrix multiplications")
        config = {"model_file": "model.onnx", "tokenizer_file": "tokenizer.json",
                  "pooling": "cls", "output_name": "sentence_embedding", "max_length": max_length,
                  "pad_token": "<pad>", "pad_id": pad_id, "source_model_fingerprint": source_fingerprint}
        for artifact, quantization in ((fp32, "fp32"), (int8, "dynamic-int8")):
            shutil.copyfile(tokenizer_path, artifact / "tokenizer.json")
            (artifact / "encoder.json").write_text(
                json.dumps({**config, "quantization": quantization}, indent=2) + "\n", encoding="utf-8",
            )
        stage.rename(output)
    return {"fp32Artifact": str(output / "fp32"), "int8Artifact": str(output / "int8"),
            "sourceFingerprint": source_fingerprint, "maxLength": max_length}


def read_document_texts(catalog, documents):
    if documents is not None:
        texts = []
        for number, line in enumerate(documents.read_text(encoding="utf-8-sig").splitlines(), 1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict) or not isinstance(row.get("text"), str) or not row["text"].strip():
                raise ValueError(f"Expected a nonempty JSON text field at line {number}")
            texts.append(row["text"])
        return texts
    payload = json.loads(catalog.read_text(encoding="utf-8-sig"))
    manager = CatalogSyncManager()
    manager.load_from_payload(payload)
    index = TextIndex.build(manager.get_flattened_catalog(), cache_dir=ROOT / "data/indices/text", payload=payload)
    return [text for item in index.documents if (text := document_text(item)).strip()]


def sample_documents(texts, count, seed):
    distinct = sorted(set(texts))
    if not 11 <= count <= 200:
        raise ValueError("sample-size must be between 11 and 200 for top-10 comparisons")
    if len(distinct) < count:
        raise ValueError(f"Need {count} distinct documents, found {len(distinct)}")
    return random.Random(seed).sample(distinct, count)


def compare_embeddings(reference, quantized):
    reference = np.asarray(reference, dtype=np.float64)
    quantized = np.asarray(quantized, dtype=np.float64)
    if reference.ndim != 2 or reference.shape != quantized.shape or len(reference) < 11:
        raise ValueError("Comparison requires matching embedding matrices with at least 11 documents")
    matrices = []
    for vectors in (reference, quantized):
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        if not np.isfinite(vectors).all() or not np.isfinite(norms).all() or (norms == 0).any():
            raise ValueError("Comparison requires finite nonzero embeddings")
        matrices.append(vectors / norms)
    cosines = np.clip(np.sum(matrices[0] * matrices[1], axis=1), -1, 1)
    ranks = []
    for vectors in matrices:
        similarity = vectors @ vectors.T
        np.fill_diagonal(similarity, -np.inf)
        ranks.append(np.argsort(-similarity, axis=1, kind="stable")[:, :10])
    overlap = np.mean([len(set(before).intersection(after)) / 10 for before, after in zip(*ranks)])
    return {"meanCosine": float(np.mean(cosines)), "minCosine": float(np.min(cosines)),
            "meanTop10Overlap": float(overlap)}


def compare_artifact(source, artifact, texts, *, sample_size, seed, batch_size):
    from ai.build_text_embeddings import TorchOfflineEncoder

    if not 1 <= batch_size <= 64:
        raise ValueError("batch-size must be between 1 and 64")
    sample = sample_documents(texts, sample_size, seed)
    config = json.loads(artifact_path(artifact, "encoder.json").read_text(encoding="utf-8"))
    if config.get("quantization") != "dynamic-int8" or config.get("pooling") != "cls":
        raise ValueError("Comparison requires a dynamic INT8 artifact with CLS pooling")
    reference = TorchOfflineEncoder(source, artifact, batch_size=batch_size, device="cpu")
    before = reference.encode_documents(sample)
    del reference
    gc.collect()
    encoder = OnnxTextEncoder.from_directory(artifact)
    after = np.concatenate([encoder.encode_documents(sample[start:start + batch_size])
                            for start in range(0, len(sample), batch_size)])
    sample_hash = hashlib.sha256(json.dumps(sample, ensure_ascii=False).encode("utf-8")).hexdigest()
    return {"sampleCount": len(sample), "documentCount": len(texts), "distinctDocumentCount": len(set(texts)),
            "seed": seed, "sampleSha256": sample_hash, "device": "cpu", "modelId": encoder.model_id,
            **compare_embeddings(before, after)}


def main():
    parser = argparse.ArgumentParser(description="Export and check the BGE-M3 dense CLS encoder on CPU")
    operations = parser.add_subparsers(dest="operation", required=True)
    export = operations.add_parser("export")
    export.add_argument("--source", type=Path, required=True)
    export.add_argument("--output", type=Path, required=True)
    export.add_argument("--max-length", type=int, default=512)
    compare = operations.add_parser("compare")
    compare.add_argument("--source", type=Path, required=True)
    compare.add_argument("--artifact", type=Path, required=True)
    document_source = compare.add_mutually_exclusive_group(required=True)
    document_source.add_argument("--catalog", type=Path)
    document_source.add_argument("--documents", type=Path)
    compare.add_argument("--sample-size", type=int, default=200)
    compare.add_argument("--seed", type=int, default=3050)
    compare.add_argument("--batch-size", type=int, default=4)
    compare.add_argument("--report", type=Path)
    args = parser.parse_args()
    try:
        if args.operation == "export":
            report = export_artifacts(args.source, args.output, max_length=args.max_length)
        else:
            texts = read_document_texts(args.catalog, args.documents)
            report = compare_artifact(args.source, args.artifact, texts, sample_size=args.sample_size,
                                      seed=args.seed, batch_size=args.batch_size)
            if args.report:
                with args.report.open("x", encoding="utf-8") as stream:
                    stream.write(json.dumps(report, indent=2) + "\n")
        print(json.dumps(report, indent=2))
    except (ImportError, OSError, ValueError, RuntimeError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
