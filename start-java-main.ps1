[CmdletBinding()]
param(
    [int]$SpringPort = 8080,
    [int]$FastApiPort = 8000,
    [int]$FrontendPort = 3000,
    [string]$MysqlHost = $(if ($env:MYSQL_HOST) { $env:MYSQL_HOST } else { "localhost" }),
    [int]$MysqlPort = $(if ($env:MYSQL_PORT) { [int]$env:MYSQL_PORT } else { 3306 }),
    [string]$MysqlDb = $(if ($env:MYSQL_DB) { $env:MYSQL_DB } else { "movie_rcm_db" }),
    [string]$MysqlUser = $(if ($env:MYSQL_USER) { $env:MYSQL_USER } else { "root" }),
    [string]$MysqlPassword = $(if ($env:MYSQL_PASSWORD) { $env:MYSQL_PASSWORD } else { "" }),
    [ValidateSet("off", "light", "full", "cloud")]
    [string]$ModelMode = "light",
    [switch]$MountDrive,
    [switch]$Background
)

$env:MYSQL_HOST = $MysqlHost
$env:MYSQL_PORT = [string]$MysqlPort
$env:MYSQL_DB = $MysqlDb
$env:MYSQL_USER = $MysqlUser
$env:MYSQL_PASSWORD = $MysqlPassword
$env:SPRING_DATASOURCE_URL = "jdbc:mysql://${MysqlHost}:${MysqlPort}/${MysqlDb}?createDatabaseIfNotExist=true&useSSL=false&allowPublicKeyRetrieval=true&characterEncoding=UTF-8&serverTimezone=UTC"
$env:SPRING_DATASOURCE_USERNAME = $MysqlUser
$env:SPRING_DATASOURCE_PASSWORD = $MysqlPassword
$env:BACKEND_INTERNAL_URL = "http://127.0.0.1:$SpringPort"

Write-Host "==========================================================================" -ForegroundColor Cyan
Write-Host " DIPPIE CINEMA — CHẾ ĐỘ JAVA MAIN (Spring Boot + FastAPI AI + MySQL 8.0)" -ForegroundColor Cyan
Write-Host "==========================================================================" -ForegroundColor Cyan

& (Join-Path $PSScriptRoot "scripts\start_preview_stack.ps1") `
    -SpringPort $SpringPort `
    -FastApiPort $FastApiPort `
    -FrontendPort $FrontendPort `
    -ModelMode $ModelMode `
    -MountDrive:$MountDrive `
    -Background:$Background
