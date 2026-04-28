param(
    [string]$BotToken = "",
    [switch]$DisableReengagement = $true,
    [string]$DbPath = ""
)

$ErrorActionPreference = "Stop"

Write-Host "=== Tracklii local bot runner ==="
Set-Location -Path $PSScriptRoot

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Error "Python не найден в PATH. Установи Python и повтори."
}

if (-not (Test-Path ".venv")) {
    Write-Host "Создаю .venv..."
    python -m venv .venv
}

Write-Host "Активирую .venv..."
. ".\.venv\Scripts\Activate.ps1"

Write-Host "Ставлю зависимости..."
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

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

$env:BOT_TOKEN = $BotToken

if ($DisableReengagement) {
    $env:REENGAGEMENT_ENABLED = "0"
}

if (-not $DbPath) {
    $candidate = Join-Path $PSScriptRoot "music_ratings (16).db"
    if (Test-Path $candidate) {
        $DbPath = $candidate
    }
}
if ($DbPath) {
    $env:DB_PATH = $DbPath
    Write-Host "Использую DB_PATH: $DbPath"
}

Write-Host "Запускаю бота (polling)..."
Write-Host "Остановить: Ctrl + C"
python main.py
