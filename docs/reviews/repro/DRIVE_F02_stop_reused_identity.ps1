# Complete state schema, but process creation differs by200ms and live mount invocation differs.
# All process operations mocked: never stops any actual process.
$ErrorActionPreference='Stop'
$repoRoot=Resolve-Path (Join-Path $PSScriptRoot '../../..')
$state=Join-Path $env:TEMP ('codex-drive-f02-identity-'+[guid]::NewGuid()+'.json')
$global:codexDriveF02Stopped=$false
$start=[DateTime]::Now
@{pid=987654;processName='rclone';startTime=$start.ToString('o');executablePath='C:\Fixture\rclone.exe';sessionId=1;mountPoint='Z:';remoteTarget='expected:media';arguments=@('mount','expected:media','Z:','--read-only');status='MOUNTED'} | ConvertTo-Json | Set-Content -LiteralPath $state
function Get-Process {param($Id,$ErrorAction) if(-not $global:codexDriveF02Stopped){[pscustomobject]@{Id=987654;ProcessName='rclone';StartTime=$start.AddMilliseconds(200);Path='C:\Fixture\rclone.exe';SessionId=1;CommandLine='rclone.exe mount unrelated:other Y:'}}}
function Get-CimInstance {param($ClassName,$Filter,$ErrorAction) [pscustomobject]@{CommandLine='rclone.exe mount unrelated:other Y:';ProcessId=987654}}
function Stop-Process {param($Id,[switch]$Force,$ErrorAction) $global:codexDriveF02Stopped=$true}
try {
  & (Join-Path $repoRoot 'scripts/drive/stop_drive.ps1') -StateFile $state -AsJson
  Write-Output ('REPRO terminationRequestedDespiteCreationAndInvocationMismatch='+$global:codexDriveF02Stopped)
}finally{if(Test-Path -LiteralPath $state){Remove-Item -LiteralPath $state -Force}}
