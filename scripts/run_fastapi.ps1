param(
    [ValidateSet("light", "full", "cloud")][string]$ServingMode = "cloud",
    [string]$Device = "cuda",
    [string]$Port = "8000"
)

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$fastapiDir = Join-Path $root "backend\fastapi"
if ($ServingMode -eq "full") { $ServingMode = "cloud" }

$env:PYTHONPATH = $fastapiDir
$env:PORT = $Port
$env:MODEL_MODE = $ServingMode
$env:SERVING_MODE = $ServingMode
$env:RERANKER_DEVICE = $Device
$env:DEFAULT_CATALOG_PATH = (Join-Path $root "data\catalog.jadoo_all.json")

Write-Host "Starting FastAPI in $ServingMode mode on port $Port..."
cd $fastapiDir
python -m uvicorn main:app --host 127.0.0.1 --port $Port
