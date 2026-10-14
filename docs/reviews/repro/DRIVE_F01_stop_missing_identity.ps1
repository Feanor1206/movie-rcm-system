# Production stop script; process operations mocked, no actual termination.
$ErrorActionPreference='Stop'
$repoRoot=Resolve-Path (Join-Path $PSScriptRoot '../../..')
$state=Join-Path $env:TEMP ('codex-drive-f01-stop-'+[guid]::NewGuid()+'.json')
$global:codexDriveF01Stopped=$false
$start=[DateTime]::Now
# Missing sessionId/mountPoint/remoteTarget/arguments/status must fail closed per assigned contract.
@{pid=987654;processName='rclone';startTime=$start.ToString('o');executablePath='C:\Fixture\rclone.exe'} | ConvertTo-Json | Set-Content -LiteralPath $state
function Get-Process {param($Id,$ErrorAction) if(-not $global:codexDriveF01Stopped){[pscustomobject]@{Id=987654;ProcessName='rclone';StartTime=$start;Path='C:\Fixture\rclone.exe';SessionId=1}}}
function Stop-Process {param($Id,[switch]$Force,$ErrorAction) $global:codexDriveF01Stopped=$true}
try {
  & (Join-Path $repoRoot 'scripts/drive/stop_drive.ps1') -StateFile $state -AsJson
  Write-Output ('REPRO terminationRequestedWithMissingIdentityFields='+$global:codexDriveF01Stopped)
}finally{if(Test-Path -LiteralPath $state){Remove-Item -LiteralPath $state -Force}}
