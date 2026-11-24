#Requires -Version 5.1
param(
    [Parameter(Mandatory)] [string] $Database,
    [string] $Server = '127.0.0.1',
    [ValidateRange(1, 65535)] [int] $Port = 3306,
    [string] $User = 'root',
    [string] $Client = 'mysql',
    [string] $DefaultsFile
)

$ErrorActionPreference = 'Stop'
$objects = Join-Path $PSScriptRoot '../database/objects'
$accountVariables = foreach ($role in @('app', 'readonly', 'admin')) {
    $variable = 'DIPPIE_DB_' + $role.ToUpperInvariant() + '_PASSWORD'
    $password = [Environment]::GetEnvironmentVariable($variable)
    if ([string]::IsNullOrEmpty($password)) { throw "Required environment variable $variable is empty." }
    $encoded = [BitConverter]::ToString([Text.Encoding]::UTF8.GetBytes($password)).Replace('-', '')
    "SET @dippie_db_${role}_password = CONVERT(0x$encoded USING utf8mb4);"
}
$definitions = foreach ($file in @('views.sql', 'functions.sql', 'procedures.sql', 'triggers.sql', 'security.sql')) {
    Get-Content -LiteralPath (Join-Path $objects $file) -Raw -Encoding UTF8
}

$options = @()
if ($DefaultsFile) {
    $options += '--defaults-extra-file=' + (Resolve-Path -LiteralPath $DefaultsFile).Path
}
$options += @('--default-character-set=utf8mb4', '--batch', "--host=$Server", "--port=$Port", "--user=$User", "--database=$Database")
$previousEncoding = $OutputEncoding
try {
    $OutputEncoding = [Text.UTF8Encoding]::new($false)
    (($accountVariables + $definitions) -join "`n") | & $Client @options
    if ($LASTEXITCODE -ne 0) { throw "MySQL object installation failed with exit code $LASTEXITCODE." }
} finally {
    $OutputEncoding = $previousEncoding
}
