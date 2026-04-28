@echo off
chcp 65001 >nul
cd /d "%~dp0"
if not exist "logs\bot.log" (
  echo Лог еще не создан. Сначала запусти бота.
  pause
  exit /b 0
)
powershell -NoProfile -Command "Get-Content -Path '.\logs\bot.log' -Wait"
