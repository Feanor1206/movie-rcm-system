# Reviewer-only: mock prerequisite and launch seams, then exercise native argv with a Node recorder.
# Never installs, authenticates, mounts or stops any user process.
$ErrorActionPreference='Stop'
$repoRoot=Resolve-Path (Join-Path $PSScriptRoot '../../..')
$tempRoot=Join-Path $env:TEMP ('codex-drive-launch-'+[guid]::NewGuid())
New-Item -ItemType Directory -Path $tempRoot | Out-Null
$preflight=Join-Path $tempRoot 'preflight.ps1'
'param($MountPoint,$RclonePath,$ConfigPath); ''{"IsReady":true,"Rclone":{"ExecutablePath":"C:\\Fixture\\rclone.exe"},"BlockReasons":[]}''' | Set-Content -LiteralPath $preflight
$global:codexDriveCapturedArguments=$null
function Start-Process {
  param($FilePath,$ArgumentList,$WindowStyle,[switch]$PassThru)
  $global:codexDriveCapturedArguments=$ArgumentList
  [pscustomobject]@{Id=987654;HasExited=$false;ProcessName='rclone';StartTime=[DateTime]::Now}
}
$source=Get-Content -LiteralPath (Join-Path $repoRoot 'scripts/drive/mount_drive.ps1') -Raw
$source=$source.Replace('$preflightScript = Join-Path $PSScriptRoot "preflight_drive.ps1"',('$preflightScript = '''+$preflight+''''))
$missingMount=Join-Path $tempRoot 'not-mounted'
$config=Join-Path $tempRoot 'secret config.conf'
$result=& ([scriptblock]::Create($source)) -Execute -Remote 'fixture' -RemoteSubpath 'Animation Films' -MountPoint $missingMount -ConfigPath $config -StateFile (Join-Path $tempRoot 'state.json') -AsJson
$result
Write-Output ('REPRO MOUNTEDDespiteMissingMount='+(-not (Test-Path -LiteralPath $missingMount)))
$recorder=Join-Path $tempRoot 'argv.cjs'
'console.log(JSON.stringify(process.argv.slice(2)))' | Set-Content -LiteralPath $recorder
$stdout=Join-Path $tempRoot 'argv.json'
$node=(Get-Command node).Source
$native=Microsoft.PowerShell.Management\Start-Process -FilePath $node -ArgumentList (@($recorder)+$global:codexDriveCapturedArguments) -WindowStyle Hidden -RedirectStandardOutput $stdout -PassThru -Wait
if($native.ExitCode -ne 0){throw 'Argv recorder failed'}
$actual=Get-Content -LiteralPath $stdout -Raw | ConvertFrom-Json
Write-Output ('REPRO NativeArgv='+($actual | ConvertTo-Json -Compress))
Write-Output ('REPRO RemoteArgPreserved='+($actual -contains 'fixture:Animation Films'))
Write-Output ('REPRO ConfigArgPreserved='+($actual -contains $config))
