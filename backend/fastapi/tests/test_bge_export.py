import json
from types import SimpleNamespace

import numpy as np
import pytest

from ai.export_bge_m3 import compare_embeddings, export_artifacts, sample_documents
from services.encoders import OnnxTextEncoder


def test_agreement_compares_top_ten_sets_without_self_match():
    rng = np.random.default_rng(92)
    reference = rng.normal(size=(14, 8))
    identical = compare_embeddings(reference, reference * 2)
    assert identical == pytest.approx({"meanCosine": 1, "minCosine": 1, "meanTop10Overlap": 1})
    changed = reference.copy()
    changed[3] *= -1
    metrics = compare_embeddings(reference, changed)
    assert metrics["minCosine"] == pytest.approx(-1)
    assert metrics["meanCosine"] == pytest.approx(12 / 14)
    assert 0 < metrics["meanTop10Overlap"] < 1


def test_sample_is_order_independent_and_rejects_insufficient_distinct_documents():
    documents = [f"đoạn {index}" for index in range(205)]
    assert sample_documents(documents, 200, 3050) == sample_documents(documents[::-1] + documents, 200, 3050)
    assert len(set(sample_documents(documents, 200, 3050))) == 200
    with pytest.raises(ValueError, match="200.*199"):
        sample_documents(documents[:199] * 2, 200, 3050)


def test_exports_real_fp32_and_int8_onnx_with_dynamic_shapes(tmp_path, monkeypatch):
    import onnx
    import torch
    from tokenizers import Tokenizer, models, pre_tokenizers

    source = tmp_path / "source"
    source.mkdir()
    tokenizer = Tokenizer(models.WordLevel({"[UNK]": 0, "<pad>": 1, "xin": 2, "chào": 3}, unk_token="[UNK]"))
    tokenizer.pre_tokenizer = pre_tokenizers.Whitespace()
    tokenizer.save(str(source / "tokenizer.json"))

    class TinyEncoder(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.embedding = torch.nn.Embedding(4, 4)
            self.dense = torch.nn.Linear(4, 3, bias=False)
            with torch.no_grad():
                self.embedding.weight.copy_(torch.tensor([
                    [0.2, 0.4, 0.6, 0.8],
                    [0.0, 0.0, 0.0, 0.0],
                    [1.0, 0.2, 0.5, 0.3],
                    [0.1, 0.9, 0.3, 0.6],
                ]))
                self.dense.weight.copy_(torch.tensor([
                    [1.0, 0.1, 0.2, 0.0],
                    [0.1, 0.8, 0.0, 0.2],
                    [0.0, 0.2, 0.7, 0.3],
                ]))

        def forward(self, input_ids, attention_mask):
            features = self.embedding(input_ids) * attention_mask.unsqueeze(-1)
            return SimpleNamespace(last_hidden_state=self.dense(features))

    import ai.export_bge_m3 as exporter

    monkeypatch.setattr(exporter, "load_source_model", lambda _: TinyEncoder().eval())
    output = tmp_path / "export"
    export_artifacts(source, output, max_length=32)
    manifest = json.loads((output / "int8/encoder.json").read_text(encoding="utf-8"))
    assert manifest["pooling"] == "cls" and manifest["quantization"] == "dynamic-int8"
    graph = onnx.load(str(output / "int8" / manifest["model_file"]), load_external_data=False)
    assert any(node.op_type == "MatMulInteger" for node in graph.graph.node)
    fp32 = OnnxTextEncoder.from_directory(output / "fp32")
    int8 = OnnxTextEncoder.from_directory(output / "int8")
    texts = ["xin chào", "chào xin xin", "xin"]
    expected, actual = fp32.encode_documents(texts), int8.encode_documents(texts)
    assert expected.shape == actual.shape == (3, 3)
    assert not np.allclose(expected[0], expected[1])
    assert np.min(np.sum(expected * actual, axis=1)) > 0.99
