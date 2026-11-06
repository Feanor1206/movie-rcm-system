$ErrorActionPreference = 'Stop'
$global:codexF08StopIntercepted = $false
$global:codexF08FakeStart = [DateTime]::Now
$global:codexF08Fixture = [pscustomobject]@{
    Name = 'java.exe'
    ProcessId = 2000000001
    ExecutablePath = $null
    CommandLine = 'com.dippie.moviercm.MovieRcmApplication --spring.profiles.active=snapshot'
    CreationDate = $global:codexF08FakeStart
}
# These functions shadow OS commands: NO real process inspection or signal occurs.
function Get-CimInstance {
    param($ClassName, $Filter, $ErrorAction)
    if (-not $global:codexF08StopIntercepted) { return $global:codexF08Fixture }
}
function Stop-Process {
    param($Id, [switch]$Force, $ErrorAction)
    $global:codexF08StopIntercepted = $true
}
if ((Get-Command Stop-Process).CommandType -ne 'Function') { throw 'Mock not installed' }
$state = Join-Path $env:TEMP ('f08-stop-fixture-' + [guid]::NewGuid().ToString('N') + '.json')
try {
    @{PID=2000000001;StartTime=$global:codexF08FakeStart.ToString('o')} |
        ConvertTo-Json | Set-Content -LiteralPath $state
    & (Join-Path $PSScriptRoot '../../../scripts/stop_backend_dev.ps1') -StateFile $state
    @{missingExecutableIdentityAccepted=$global:codexF08StopIntercepted;realProcessSignals=0} |
        ConvertTo-Json -Compress
    if ($global:codexF08StopIntercepted) { throw 'Missing executable identity did not fail closed' }
} finally {
    Remove-Item -LiteralPath $state -ErrorAction SilentlyContinue
    Remove-Item Function:\Stop-Process,Function:\Get-CimInstance -ErrorAction SilentlyContinue
}
