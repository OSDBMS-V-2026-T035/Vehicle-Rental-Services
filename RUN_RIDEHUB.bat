@echo off
cd /d "%~dp0"
setlocal

echo [RideHub] Starting Docker-based RideHub stack...
docker compose version >nul 2>&1
if errorlevel 1 (
    echo [RideHub] Docker Desktop is not available. Start Docker Desktop, wait until it is running, then run this file again.
    pause
    exit /b 1
)

docker compose up --build -d --wait
if errorlevel 1 (
    echo [RideHub] Startup failed. Run "docker compose logs --tail 100" in this folder to see the error.
    pause
    exit /b 1
)

echo.
echo [RideHub] Services started. Checking status...
docker compose ps
echo.
echo [RideHub] Open http://127.0.0.1:8000/ in your browser.
start "" "http://127.0.0.1:8000/"
echo [RideHub] MySQL, Django web/API, migrations, and startup verification are managed by Docker Compose.
pause
