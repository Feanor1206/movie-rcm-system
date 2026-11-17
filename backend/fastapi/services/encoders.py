import hashlib
import json
from pathlib import Path

import numpy as np


def artifact_path(directory, filename):
    root = Path(directory).resolve(strict=True)
    target = (root / filename).resolve()
    if not target.is_relative_to(root):
        raise ValueError("Artifact file must stay inside its directory")
    if not target.is_file():
        raise ValueError(f"Missing local artifact file: {target.name}")
    return target


def artifact_fingerprint(directory):
    root = Path(directory).resolve(strict=True)
    digest = hashlib.sha256()
    directories, files = [root], []
    while directories:
        for path in directories.pop().iterdir():
            if not path.resolve().is_relative_to(root):
                raise ValueError("Artifact file must stay inside its directory")
            if path.is_dir():
                if path.is_symlink() or getattr(path, "is_junction", lambda: False)():
                    raise ValueError("Artifact directories must stay inside without directory links")
                directories.append(path)
            elif path.is_file():
                files.append(path)
    for path in sorted(files):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        digest.update(b"\0")
    return "onnx-text:" + digest.hexdigest()


class LocalTokenizer:
    def __init__(self, tokenizer):
        self.tokenizer = tokenizer

    @classmethod
    def from_directory(cls, directory, config=None):
        from tokenizers import Tokenizer

        if config is None:
            config = json.loads(artifact_path(directory, "encoder.json").read_text(encoding="utf-8"))
        path = artifact_path(directory, config.get("tokenizer_file", "tokenizer.json"))
        tokenizer = Tokenizer.from_file(str(path))
        maximum = config.get("max_length", 512)
        if not isinstance(maximum, int) or not 1 <= maximum <= 8192:
            raise ValueError("Tokenizer max_length must be between 1 and 8192")
        tokenizer.enable_truncation(max_length=maximum)
        pad_token = config.get("pad_token")
        if pad_token is None:
            pad_token = next((token for token in ("<pad>", "[PAD]") if tokenizer.token_to_id(token) is not None), None)
        pad_id = config.get("pad_id", tokenizer.token_to_id(pad_token) if pad_token else None)
        if pad_id is None or not isinstance(pad_id, int) or pad_id < 0:
            raise ValueError("Tokenizer artifact must define a padding token")
        tokenizer.enable_padding(pad_id=pad_id, pad_token=pad_token or "[PAD]")
        return cls(tokenizer)

    def encode(self, texts):
        encoded = self.tokenizer.encode_batch(texts)
        return {"input_ids": np.asarray([item.ids for item in encoded], dtype=np.int64),
                "attention_mask": np.asarray([item.attention_mask for item in encoded], dtype=np.int64),
                "token_type_ids": np.asarray([item.type_ids for item in encoded], dtype=np.int64)}


class OnnxTextEncoder:
    def __init__(self, session, tokenizer, config, model_id):
        self.session = session
        self.tokenizer = tokenizer
        self.config = config
        self.model_id = model_id

    @classmethod
    def from_directory(cls, directory):
        import onnxruntime

        config = json.loads(artifact_path(directory, "encoder.json").read_text(encoding="utf-8"))
        if config.get("pooling", "cls") not in ("cls", "mean"):
            raise ValueError("Encoder pooling must be cls or mean")
        model = artifact_path(directory, config.get("model_file", "model.onnx"))
        model_id = artifact_fingerprint(directory)
        tokenizer = LocalTokenizer.from_directory(directory, config=config)
        session = onnxruntime.InferenceSession(str(model), providers=["CPUExecutionProvider"])
        return cls(session, tokenizer, config, model_id)

    def _encode(self, texts, prefix):
        if not texts:
            return np.empty((0, 0), dtype=np.float32)
        inputs = self.tokenizer.encode([prefix + text for text in texts])
        feed = {}
        for item in self.session.get_inputs():
            if item.name not in inputs:
                raise ValueError(f"Unsupported encoder input: {item.name}")
            feed[item.name] = inputs[item.name].astype(np.int32 if item.type == "tensor(int32)" else np.int64)
        output_name = self.config.get("output_name")
        outputs = self.session.run([output_name] if output_name else None, feed)
        vectors = np.asarray(outputs[0], dtype=np.float32)
        if vectors.ndim == 3:
            if self.config.get("pooling", "cls") == "mean":
                mask = inputs["attention_mask"][..., None]
                vectors = (vectors * mask).sum(axis=1) / np.maximum(mask.sum(axis=1), 1)
            else:
                vectors = vectors[:, 0]
        if vectors.ndim != 2 or vectors.shape[0] != len(texts) or not np.isfinite(vectors).all():
            raise ValueError("Encoder must return one finite embedding per input")
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        if (norms == 0).any():
            raise ValueError("Encoder returned an empty embedding")
        return vectors / norms

    def encode_queries(self, texts):
        return self._encode(texts, self.config.get("query_prefix", ""))

    def encode_documents(self, texts):
        return self._encode(texts, self.config.get("document_prefix", ""))
