@echo off
chcp 65001 >nul
cd /d "%~dp0"
set BOT_TOKEN=8737713182:AAEJeimCuY_nMTcSY-lbrc1fKHj0bVlktI4
set DB_PATH=%~dp0music_ratings (16).db

echo ==========================================
echo Tracklii Bot - Локальный запуск
echo ==========================================

if not exist ".venv\Scripts\python.exe" (
  echo [1/3] Создаю виртуальное окружение...
  python -m venv .venv
)

if not exist ".venv\.deps_ready" (
  echo [2/3] Первый запуск: устанавливаю зависимости...
  call ".venv\Scripts\python.exe" -m pip install -r requirements.txt
  if errorlevel 1 (
    echo pip не смог скачать пакеты. Проверяю, стоят ли зависимости уже локально...
  )
  call ".venv\Scripts\python.exe" -c "import aiogram, aiosqlite; print('deps_ok')"
  if errorlevel 1 (
    echo Зависимости не установлены. Включи интернет/VPN и повтори запуск.
    pause
    exit /b 1
  ) else (
    type nul > ".venv\.deps_ready"
  )
) else (
  echo [2/3] Зависимости уже установлены, пропускаю.
)

set REENGAGEMENT_ENABLED=0

echo [3/3] Запускаю бота...
echo Остановка: Ctrl + C
call ".venv\Scripts\python.exe" main.py

pause
