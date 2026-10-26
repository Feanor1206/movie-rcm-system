[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$CatalogPath,
    [string]$ApiBaseUrl = "http://127.0.0.1:8080/api",
    [string]$Username,
    [System.Security.SecureString]$Password
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Read-ResponseBody {
    param($Response)

    if (-not $Response) { return $null }
    try {
        $stream = $Response.GetResponseStream()
        if (-not $stream) { return $null }
        $reader = New-Object System.IO.StreamReader($stream)
        try { return $reader.ReadToEnd() } finally { $reader.Dispose() }
    } catch { return $null }
}

function Invoke-PreviewApi {
    param(
        [string]$Uri,
        [string]$Method,
        [string]$Body,
        [hashtable]$Headers,
        [string]$Label
    )

    try {
        $result = Invoke-RestMethod -Uri $Uri -Method $Method -Headers $Headers -Body $Body `
            -ContentType "application/json; charset=utf-8" -TimeoutSec 60 -ErrorAction Stop
        return [PSCustomObject]@{ StatusCode = 200; Body = $result }
    } catch {
        $responseProperty = $_.Exception.PSObject.Properties["Response"]
        $response = if ($responseProperty) { $responseProperty.Value } else { $null }
        if (-not $response) {
            throw "$Label failed: $($_.Exception.Message)"
        }
        $statusCode = 0
        try { $statusCode = [int]$response.StatusCode } catch { }
        $rawBody = Read-ResponseBody $response
        $parsedBody = $null
        if (-not [string]::IsNullOrWhiteSpace($rawBody)) {
            try { $parsedBody = $rawBody | ConvertFrom-Json } catch { }
        }
        return [PSCustomObject]@{ StatusCode = $statusCode; Body = $parsedBody }
    }
}

function Write-ValidationSummary {
    param($Result)

    Write-Host ("Validation: valid={0}, package={1}, revision={2}, create={3}, update={4}, unchanged={5}, conflicts={6}" -f `
        $Result.valid, $Result.packageId, $Result.revision, $Result.toCreate, $Result.toUpdate, $Result.unchanged, $Result.conflicts)
    if ($Result.errors) {
        $shown = 0
        foreach ($item in $Result.errors) {
            if ($shown -ge 5) { break }
            $where = if ($item.path) { [string]$item.path } else { "catalog" }
            $message = if ($item.message) { [string]$item.message } else { [string]$item.code }
            Write-Host ("  {0}: {1}" -f $where, $message)
            $shown++
        }
        if ($Result.errors.Count -gt $shown) { Write-Host ("  ... {0} more validation error(s)" -f ($Result.errors.Count - $shown)) }
    }
}

if (-not (Test-Path -LiteralPath $CatalogPath -PathType Leaf)) {
    throw "Catalog file not found: $CatalogPath"
}
$catalogFullPath = (Resolve-Path -LiteralPath $CatalogPath).Path
$catalogJson = [System.IO.File]::ReadAllText($catalogFullPath, [System.Text.Encoding]::UTF8)
if ([string]::IsNullOrWhiteSpace($catalogJson)) { throw "Catalog file is empty: $catalogFullPath" }

$apiUri = $null
if (-not [System.Uri]::TryCreate($ApiBaseUrl, [System.UriKind]::Absolute, [ref]$apiUri) -or
    -not $apiUri.IsLoopback -or $apiUri.Scheme -notin @("http", "https") -or
    $apiUri.UserInfo -or $apiUri.Query -or $apiUri.Fragment -or $apiUri.AbsolutePath.TrimEnd("/") -notmatch "/api$") {
    throw "ApiBaseUrl must be an HTTP(S) loopback URL ending in /api."
}
$apiBase = $ApiBaseUrl.TrimEnd("/")

if (-not $Username) { $Username = [System.Environment]::GetEnvironmentVariable("PREVIEW_ADMIN_USERNAME", "Process") }
if (-not $Username) { $Username = Read-Host "Admin username or email" }
if (-not $Password -and [string]::IsNullOrEmpty([System.Environment]::GetEnvironmentVariable("PREVIEW_ADMIN_PASSWORD", "Process"))) {
    $Password = Read-Host -AsSecureString "Admin password"
}
if (-not $Username) { throw "An admin username is required." }
if (-not $Password -and [string]::IsNullOrEmpty([System.Environment]::GetEnvironmentVariable("PREVIEW_ADMIN_PASSWORD", "Process"))) {
    throw "An admin password is required."
}

$passwordText = [System.Environment]::GetEnvironmentVariable("PREVIEW_ADMIN_PASSWORD", "Process")
$passwordPtr = [IntPtr]::Zero
if ($Password) {
    $passwordPtr = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($Password)
    $passwordText = [System.Runtime.InteropServices.Marshal]::PtrToStringBSTR($passwordPtr)
}

try {
    $loginBody = @{ usernameOrEmail = $Username; password = $passwordText } | ConvertTo-Json -Compress
    $login = Invoke-PreviewApi -Uri "$apiBase/auth/login" -Method "Post" -Body $loginBody -Headers @{} -Label "Login"
} finally {
    $passwordText = $null
    $loginBody = $null
    if ($passwordPtr -ne [IntPtr]::Zero) { [System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($passwordPtr) }
}

if ($login.StatusCode -ne 200 -or -not $login.Body -or -not $login.Body.success -or -not $login.Body.data.token) {
    throw ("Login failed (HTTP {0}); check the local server and administrator credentials." -f $login.StatusCode)
}
if ([string]$login.Body.data.role -ne "ROLE_ADMIN") {
    throw "The authenticated account is not an administrator; no catalog changes were made."
}
$headers = @{ Authorization = "Bearer $($login.Body.data.token)" }

$validation = Invoke-PreviewApi -Uri "$apiBase/admin/catalog/validate" -Method "Post" `
    -Body $catalogJson -Headers $headers -Label "Catalog validation"
if ($validation.StatusCode -notin @(200, 400) -or -not $validation.Body -or $null -eq $validation.Body.valid) {
    throw ("Catalog validation request failed (HTTP {0}); no catalog was imported." -f $validation.StatusCode)
}
Write-ValidationSummary $validation.Body
if (-not $validation.Body.valid -or [int]$validation.Body.conflicts -gt 0) {
    throw "Catalog validation failed or reported conflicts; no catalog was imported."
}

$import = Invoke-PreviewApi -Uri "$apiBase/admin/catalog/import" -Method "Post" `
    -Body $catalogJson -Headers $headers -Label "Catalog import"
if ($import.StatusCode -ne 200 -or -not $import.Body -or -not $import.Body.success) {
    $message = if ($import.Body -and $import.Body.message) { [string]$import.Body.message } else { "server rejected the import" }
    throw ("Catalog import failed (HTTP {0}): {1}" -f $import.StatusCode, $message)
}

$countText = "none reported"
if ($import.Body.counts) {
    $pairs = @()
    foreach ($property in $import.Body.counts.PSObject.Properties) { $pairs += ("{0}={1}" -f $property.Name, $property.Value) }
    if ($pairs.Count -eq 0 -and $import.Body.counts -is [System.Collections.IDictionary]) {
        foreach ($key in $import.Body.counts.Keys) { $pairs += ("{0}={1}" -f $key, $import.Body.counts[$key]) }
    }
    if ($pairs.Count -gt 0) { $countText = $pairs -join ", " }
}
$indexStatus = if ($import.Body.indexStatus) { [string]$import.Body.indexStatus } else { "not reported" }
Write-Host ("Imported package {0} revision {1}; importId={2}; counts: {3}; indexStatus={4}" -f `
    $import.Body.packageId, $import.Body.revision, $import.Body.importId, $countText, $indexStatus)
if ($import.Body.message) { Write-Host ([string]$import.Body.message) }
