param(
    [string]$ServingMode = "full",
    [string]$Device = "cuda",
    [string]$Port = "8000"
)

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$fastapiDir = Join-Path $root "backend\fastapi"

$env:PYTHONPATH = $fastapiDir
$env:PORT = $Port
$env:SERVING_MODE = $ServingMode
$env:USE_FULL_QWEN3_4B_LORA = if ($ServingMode -eq "full") { "true" } else { "false" }
$env:DEVICE = $Device
$env:ENABLE_FALLBACK = "false"
$env:STRICT_READINESS = "true"
$env:BASE_MODEL_NAME = "Qwen/Qwen3-4B"
$env:PHASE23_ADAPTER_DIR = (Join-Path $root "ai\models\qwen3-4b-phase23-lora")
$env:MAX_CONCURRENT_INFERENCE = "1"
$env:MAX_NEW_TOKENS = "512"
$env:DEFAULT_CATALOG_PATH = (Join-Path $root "data\catalog.jadoo_all.json")
$env:FASTAPI_SYNC_SECRET = "test_sync_secret"
$env:CATALOG_SYNC_TOKEN = "test_sync_secret"

Write-Host "Starting FastAPI in $ServingMode mode on port $Port (Device: $Device)..."
cd $fastapiDir
python -m uvicorn main:app --host 127.0.0.1 --port $Port
