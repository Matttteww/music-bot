@echo off
chcp 65001 >nul
cd /d "%~dp0"
set BOT_TOKEN=8737713182:AAEJeimCuY_nMTcSY-lbrc1fKHj0bVlktI4
set DB_PATH=%~dp0music_ratings (16).db

if not exist "logs" mkdir logs

powershell -NoProfile -ExecutionPolicy Bypass -File ".\run_local_bot_bg.ps1" -BotToken "%BOT_TOKEN%" -DbPath "%DB_PATH%"
echo Готово. Бот запущен в фоне.
pause
