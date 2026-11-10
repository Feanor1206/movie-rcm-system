[CmdletBinding()]
param([switch]$Clear)

$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent $PSScriptRoot
$name = '.env.deepseek.local'
$path = Join-Path $repo $name
$temporaryName = "$name.$([Guid]::NewGuid().ToString('N')).tmp"
$temporary = Join-Path $repo $temporaryName

function Assert-Ignored([string]$relativePath) {
    $tracked = git -C $repo ls-files -- $relativePath 2>$null
    if ($LASTEXITCODE -ne 0 -or $tracked) { throw 'Configuration path is tracked or Git is unavailable.' }
    git -C $repo check-ignore -q -- $relativePath 2>$null
    if ($LASTEXITCODE -ne 0) { throw 'Configuration path is not ignored by Git.' }
}

$status = 'N/A'
$reportedModel = $null
try {
    Assert-Ignored $name
    if ($Clear) {
        [IO.File]::Delete($path)
        Write-Output 'Success'
        exit 0
    }

    Assert-Ignored $temporaryName
    $baseUrl = (Read-Host 'Base URL [https://api.deepseek.com]').Trim()
    if (!$baseUrl) { $baseUrl = 'https://api.deepseek.com' }
    $uri = $null
    if (![Uri]::TryCreate($baseUrl, [UriKind]::Absolute, [ref]$uri) -or $uri.Scheme -ne 'https' -or !$uri.Host -or $uri.UserInfo -or $uri.Query -or $uri.Fragment) {
        throw 'Invalid base URL.'
    }
    $baseUrl = $uri.AbsoluteUri.TrimEnd('/')
    $model = (Read-Host 'Model ID').Trim()
    if ($model -cnotmatch '\A[A-Za-z0-9][A-Za-z0-9._:/-]{0,199}\z') { throw 'Invalid model ID.' }
    $secureKey = Read-Host 'API key' -AsSecureString
    $pointer = [IntPtr]::Zero
    try {
        $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
        $key = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    } finally {
        if ($pointer -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer) }
        $secureKey.Dispose()
    }
    if ($key -cnotmatch '\A[A-Za-z0-9._~+/=-]+\z' -or $model.Contains($key)) { throw 'Invalid API key format.' }
    $settings = "DEEPSEEK_BASE_URL=$baseUrl`nDEEPSEEK_MODEL=$model`nDEEPSEEK_API_KEY=$key`n"
    [IO.File]::WriteAllText($temporary, $settings, [Text.UTF8Encoding]::new($false))
    if ([IO.File]::Exists($path)) { [IO.File]::Replace($temporary, $path, [NullString]::Value) }
    else { [IO.File]::Move($temporary, $path) }

    Add-Type -AssemblyName System.Net.Http
    $handler = [Net.Http.HttpClientHandler]::new()
    $handler.AllowAutoRedirect = $false
    $client = [Net.Http.HttpClient]::new($handler)
    $client.Timeout = [TimeSpan]::FromSeconds(20)
    $client.DefaultRequestHeaders.Authorization = [Net.Http.Headers.AuthenticationHeaderValue]::new('Bearer', $key)
    $testRequest = @{ model = $model; messages = @(@{ role = 'user'; content = 'ping' }); max_tokens = 8; stream = $false }
    if ($uri.IdnHost -eq 'api.deepseek.com') { $testRequest.thinking = @{ type = 'disabled' } }
    $payload = $testRequest | ConvertTo-Json -Depth 4 -Compress
    $body = [Net.Http.StringContent]::new($payload, [Text.Encoding]::UTF8, 'application/json')
    $response = $client.PostAsync("$baseUrl/chat/completions", $body).GetAwaiter().GetResult()
    $status = [int]$response.StatusCode
    try {
        $returned = ($response.Content.ReadAsStringAsync().GetAwaiter().GetResult() | ConvertFrom-Json).model
        if ($returned -is [string] -and $returned -cmatch '\A[A-Za-z0-9][A-Za-z0-9._:/-]{0,199}\z' -and !$returned.Contains($key)) { $reportedModel = $returned }
    } catch {}
    if (!$response.IsSuccessStatusCode -or !$reportedModel) { throw 'Model verification failed.' }
    Write-Output "Success | Model: $reportedModel"
} catch {
    if (!$reportedModel) { $reportedModel = 'N/A' }
    Write-Output "Failure | Model: $reportedModel | HTTP: $status"
    exit 1
} finally {
    if ($response) { $response.Dispose() }
    if ($body) { $body.Dispose() }
    if ($client) { $client.Dispose() }
    if ([IO.File]::Exists($temporary)) { [IO.File]::Delete($temporary) }
}
