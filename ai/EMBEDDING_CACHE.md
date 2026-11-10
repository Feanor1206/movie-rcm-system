# Preparing text embeddings

The serving process loads a local ONNX encoder directory through
`TEXT_ENCODER_PATH` (or `EMBEDDER_PATH`). It never downloads a model. The directory
contains the ONNX graph, tokenizer JSON, any external tensor files and an
`encoder.json` manifest:

```json
{"model_file":"model.onnx","tokenizer_file":"tokenizer.json","pooling":"cls","max_length":512,"pad_token":"<pad>","pad_id":1}
```

Use `pooling: "mean"` only for an artifact trained with mean pooling. Optional
`output_name`, `query_prefix` and `document_prefix` must match the exported model.
The cache identity fingerprints all artifact files, including tokenizer and
manifest, so changing weights, tokenization or pooling invalidates the cache.
Keep generated embeddings outside the artifact directory.

## BGE-M3 dense export and agreement

Use a separate Python environment with the serving requirements and the offline
packages `transformers==4.57.1`, `accelerate==1.11.0` and `onnx==1.19.1`. The
export and agreement check run on CPU. Keep the source checkpoint and both
output variants outside tracked files. Allow disk space for the checkpoint,
FP32 weights, INT8 weights and intermediate graphs.

```powershell
hf download BAAI/bge-m3 config.json pytorch_model.bin sentencepiece.bpe.model special_tokens_map.json tokenizer.json tokenizer_config.json --revision 5617a9f61b028005a4858fdac845db406aefb181 --local-dir ai/artifacts/models/bge-m3-source
python ai/export_bge_m3.py export --source ai/artifacts/models/bge-m3-source --output ai/artifacts/models/bge-m3-onnx
python ai/export_bge_m3.py compare --source ai/artifacts/models/bge-m3-source --artifact ai/artifacts/models/bge-m3-onnx/int8 --catalog ai/artifacts/pilot/catalog.json --report ai/artifacts/pilot/bge-m3-agreement.json
```

The exporter writes `fp32/` and `int8/` as separate serving artifacts with
CLS pooling and a default input limit of 512 tokens. Point `TEXT_ENCODER_PATH`
at `int8/` for CPU serving. ONNX Runtime quantizes the constant weights of
matrix multiplications and calculates activation scales at runtime. [BAAI model
card](https://huggingface.co/BAAI/bge-m3) · [ONNX Runtime quantization](https://onnxruntime.ai/docs/performance/model-optimizations/quantization.html)

The agreement command samples 200 distinct document texts with seed 3050 and
compares the normalized PyTorch FP32 and ONNX INT8 embeddings. It reports mean
and minimum cosine similarity and mean top-10 neighbor overlap, excluding each
document from its own neighbors. The catalog reader uses public serving
eligibility. For a local preview corpus, supply a separate `--documents` JSONL
file with one `{"text": "…"}` per line. A smaller corpus requires an explicit
`--sample-size` for a smoke check and reports its actual sample count.

For the first build, use a separate offline Python environment with the `ai/`
requirements. The default path requires CUDA and local transformer weights:

```powershell
python ai/build_text_embeddings.py --catalog data/catalog/committed_catalog_snapshot.json --artifact ai/models/text-onnx --torch-model ai/models/text-source --device cuda --batch-size 4
```

The ONNX manifest must include `source_model_fingerprint` equal to
`services.encoders.artifact_fingerprint` of the local transformer source
directory. This explicitly binds offline weights to the serving export. Perform
this binding when exporting the artifact, then keep both directories immutable.
Both environments use the serving export fingerprint as their cache namespace.
Validate ONNX quantization against the original GPU embeddings before deployment;
the code does not claim that an arbitrary pair of exports is numerically equal.

CPU preparation is an explicit alternative for small deltas or development:

```powershell
python ai/build_text_embeddings.py --catalog data/catalog/committed_catalog_snapshot.json --artifact ai/models/text-onnx --device cpu
```

Only content hashes not already present are encoded. Documents that share exact
retrieval text share their vector. Each vector is normalized, validated and stored
as numeric float16 NPY; complete matrices use snapshot-content filenames. Writes
use temporary files and atomic replacement. A serving sync build reads this cache
without encoding documents. Missing embeddings disable dense retrieval explicitly
and retain lexical search; `missingEmbeddings` reports the gap. Initial catalog
encoding and model training are separate operations, never a request side effect.

Calibrated probabilities require a separate held-out dev calibration artifact:

```json
{"model_id":"reranker-artifact-fingerprint","score_type":"reranker","x":[-3,0,3],"y":[0.05,0.5,0.95],"threshold":0.6}
```

The numbers above describe the format only; they are not a fitted artifact.
Without actual calibration, result `calibratedScore` and `matchPercentage` remain
null. Fit on dev data, set the rejection threshold there, and evaluate once on the
locked human test set.
