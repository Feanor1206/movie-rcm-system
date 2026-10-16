$ErrorActionPreference = "Stop"
$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$classes = Join-Path $root "backend\springboot\target\classes"
$cpFile = Join-Path $root "backend\springboot\target\cp.txt"
$dependencies = (Get-Content $cpFile -Raw).Trim()
$cp = "$classes;$dependencies"

$java = "C:\Program Files\Java\jdk-25.0.3\bin\java.exe"
& $java -cp $cp com.dippie.moviercm.MovieRcmApplication --spring.profiles.active=dev --app.media.drive-mount=X: --app.media.drive-metadata-timeout-ms=15000 --app.media.drive-read-timeout-ms=15000
