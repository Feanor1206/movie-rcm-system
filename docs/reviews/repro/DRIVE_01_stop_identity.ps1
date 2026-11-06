# Execute production script with process operations mocked; never kill a process.
$ErrorActionPreference='Stop'
$repoRoot=Resolve-Path (Join-Path $PSScriptRoot '../../..')
$state=Join-Path $env:TEMP ('codex-drive-stop-'+[guid]::NewGuid()+'.json')
$global:codexDriveFakeStopped=$false
$start=[DateTime]::Now
@{pid=987654;startTime=$start.AddSeconds(-3).ToString('o');executablePath='C:\Expected\rclone.exe';mountPoint='Z:';remoteTarget='fixture:only'} | ConvertTo-Json | Set-Content -LiteralPath $state
function Get-Process { param($Id,$ErrorAction) if(-not $global:codexDriveFakeStopped){[pscustomobject]@{Id=987654;ProcessName='rclone';StartTime=$start;Path='C:\Different\rclone.exe'}} }
function Stop-Process { param($Id,[switch]$Force,$ErrorAction) $global:codexDriveFakeStopped=$true }
try {
  $result=& (Join-Path $repoRoot 'scripts/drive/stop_drive.ps1') -StateFile $state -AsJson
  $result
  Write-Output ('REPRO terminationRequestedDespiteExecutableAndStartMismatch='+$global:codexDriveFakeStopped)
  if(-not $global:codexDriveFakeStopped){throw 'Repro no longer applies'}
} finally {if(Test-Path -LiteralPath $state){Remove-Item -LiteralPath $state -Force}}

