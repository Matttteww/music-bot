param(
    [string]$BotToken = "",
    [switch]$DisableReengagement = $true,
    [string]$DbPath = ""
)

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

if (-not $BotToken) {
    if ($env:BOT_TOKEN) {
        $BotToken = $env:BOT_TOKEN
    } else {
        $BotToken = Read-Host "Введи BOT_TOKEN"
    }
}

if (-not $BotToken) {
    Write-Error "BOT_TOKEN пустой. Запуск невозможен."
}

$logDir = Join-Path $PSScriptRoot "logs"
if (-not (Test-Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir | Out-Null
}
$logFile = Join-Path $logDir "bot.log"

$reengagement = if ($DisableReengagement) { "0" } else { "1" }
if (-not $DbPath) {
    $candidate = Join-Path $PSScriptRoot "music_ratings (16).db"
    if (Test-Path $candidate) {
        $DbPath = $candidate
    }
}

$command = @(
    "`$env:BOT_TOKEN='$BotToken'"
    "`$env:REENGAGEMENT_ENABLED='$reengagement'"
    "$(if ($DbPath) { "`$env:DB_PATH='$DbPath'" })"
    "cd '$PSScriptRoot'"
    "python main.py *>> '$logFile'"
) -join "; "

Start-Process -FilePath "powershell" -ArgumentList "-NoProfile -ExecutionPolicy Bypass -Command $command" -WindowStyle Hidden

Write-Host "Бот запущен в фоне."
Write-Host "Лог: $logFile"
Write-Host "Проверка лога: Get-Content -Path '$logFile' -Wait"
