import base64
import json
import os
from pathlib import Path
import sys
import subprocess

import numpy as np
import pytest
from tokenizers import Tokenizer, models, pre_tokenizers

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.encoders import LocalTokenizer, OnnxTextEncoder


MODEL = "CAg66AEKJAoJaW5wdXRfaWRzEgZmbG9hdHMiBENhc3QqCQoCdG8YAaABAgoeCgZmbG9hdHMKBGF4ZXMSA291dCIJVW5zcXVlZXplCjIKA291dAoDb3V0EhFsYXN0X2hpZGRlbl9zdGF0ZSIGQ29uY2F0KgsKBGF4aXMYAqABAhIHZW5jb2RlcioNCAEQBzoBAkIEYXhlc1ojCglpbnB1dF9pZHMSFgoUCAcSEAoHEgViYXRjaAoFEgNzZXFiLwoRbGFzdF9oaWRkZW5fc3RhdGUSGgoYCAESFAoHEgViYXRjaAoFEgNzZXEKAggCQgQKABAN"


@pytest.fixture
def artifact(tmp_path):
    tokenizer = Tokenizer(models.WordLevel({"[UNK]": 0, "[PAD]": 1, "hello": 2, "world": 3}, unk_token="[UNK]"))
    tokenizer.pre_tokenizer = pre_tokenizers.Whitespace()
    tokenizer.save(str(tmp_path / "tokenizer.json"))
    (tmp_path / "model.onnx").write_bytes(base64.b64decode(MODEL))
    (tmp_path / "encoder.json").write_text(json.dumps({
        "model_file": "model.onnx", "pooling": "mean", "max_length": 8,
        "pad_id": 1, "pad_token": "[PAD]",
    }), encoding="utf-8")
    return tmp_path


def test_local_onnx_encoder_uses_cpu_and_normalizes(artifact):
    encoder = OnnxTextEncoder.from_directory(artifact)
    assert encoder.session.get_providers() == ["CPUExecutionProvider"]
    values = encoder.encode_queries(["hello world", "hello"])
    assert values.shape == (2, 2)
    assert np.allclose(np.linalg.norm(values, axis=1), 1)
    assert encoder.encode_documents(["hello"]).shape == (1, 2)


def test_model_fingerprint_changes_with_tokenizer_or_config(artifact):
    old = OnnxTextEncoder.from_directory(artifact).model_id
    config = json.loads((artifact / "encoder.json").read_text())
    config["query_prefix"] = "query: "
    (artifact / "encoder.json").write_text(json.dumps(config))
    assert OnnxTextEncoder.from_directory(artifact).model_id != old


def test_local_tokenizer_supports_pairs_and_bounded_inputs(artifact):
    tokenizer = LocalTokenizer.from_directory(artifact)
    values = tokenizer.encode([("hello", "world"), ("hello", "hello world " * 100)])
    assert set(values) == {"input_ids", "attention_mask", "token_type_ids"}
    assert all(value.dtype == np.int64 for value in values.values())
    assert values["input_ids"].shape[1] <= 8


def test_artifact_paths_cannot_escape_directory(artifact):
    (artifact / "encoder.json").write_text(json.dumps({"model_file": "../outside.onnx"}))
    with pytest.raises(ValueError, match="inside"):
        OnnxTextEncoder.from_directory(artifact)


def test_hidden_external_files_are_included_in_artifact_fingerprint(artifact):
    from services.encoders import artifact_fingerprint

    hidden = artifact / ".weights"
    hidden.write_bytes(b"original tensors")
    before = artifact_fingerprint(artifact)
    hidden.write_bytes(b"changed tensors")
    assert artifact_fingerprint(artifact) != before


def test_directory_links_cannot_hide_external_artifact_files(artifact, tmp_path_factory):
    from services.encoders import artifact_fingerprint

    outside = tmp_path_factory.mktemp("external-weights")
    (outside / "tensor.data").write_bytes(b"outside")
    link = artifact / "linked"
    if os.name == "nt":
        subprocess.run(["cmd.exe", "/d", "/c", "mklink", "/J", str(link), str(outside)],
                       check=True, capture_output=True)
    else:
        link.symlink_to(outside, target_is_directory=True)
    with pytest.raises(ValueError, match="inside"):
        artifact_fingerprint(artifact)
