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
