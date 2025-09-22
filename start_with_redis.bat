@echo off
echo ==========================================
echo     Data Sync AI - Redis Quick Setup
echo ==========================================

echo.
echo Checking for Redis installation...

where redis-server >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] Redis found in PATH
    goto start_redis
)

echo [WARNING] Redis not found in PATH
echo.
echo Please choose an option:
echo 1. Start Docker Redis (recommended)
echo 2. Install Redis with Chocolatey
echo 3. Manual setup instructions
echo.

set /p choice="Enter your choice (1-3): "

if "%choice%"=="1" goto docker_redis
if "%choice%"=="2" goto choco_install
if "%choice%"=="3" goto manual_setup

:docker_redis
echo.
echo Starting Redis with Docker...
echo Checking if Docker is available...

where docker >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Docker not found. Please install Docker Desktop first.
    echo Download from: https://desktop.docker.com/win/main/amd64/Docker%%20Desktop%%20Installer.exe
    pause
    exit /b 1
)

echo Stopping any existing Redis container...
docker stop redis-server 2>nul
docker rm redis-server 2>nul

echo Starting new Redis container...
docker run -d -p 6379:6379 --name redis-server redis:alpine
if %errorlevel% equ 0 (
    echo [OK] Redis started successfully on port 6379
    echo.
    echo Testing connection...
    timeout /t 3 >nul
    docker exec redis-server redis-cli ping
    if %errorlevel% equ 0 (
        echo [OK] Redis is responding to ping
        goto start_app
    )
)
echo [ERROR] Failed to start Redis with Docker
pause
exit /b 1

:choco_install
echo.
echo Installing Redis with Chocolatey...
where choco >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Chocolatey not found. 
    echo Please install Chocolatey first: https://chocolatey.org/install
    pause
    exit /b 1
)

choco install redis-64 -y
if %errorlevel% equ 0 (
    echo [OK] Redis installed successfully
    goto start_redis
) else (
    echo [ERROR] Failed to install Redis
    pause
    exit /b 1
)

:start_redis
echo.
echo Starting Redis server...
start "Redis Server" redis-server
timeout /t 3 >nul

echo Testing Redis connection...
redis-cli ping >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] Redis is running and responding
    goto start_app
) else (
    echo [ERROR] Redis failed to start or not responding
    pause
    exit /b 1
)

:manual_setup
echo.
echo Manual Setup Instructions:
echo.
echo Option 1 - Redis for Windows:
echo 1. Download Redis from: https://github.com/microsoftarchive/redis/releases
echo 2. Extract and run redis-server.exe
echo.
echo Option 2 - Windows Subsystem for Linux (WSL):
echo 1. Install WSL: wsl --install
echo 2. In WSL: sudo apt update && sudo apt install redis-server
echo 3. Start Redis: redis-server
echo.
echo Option 3 - Docker:
echo 1. Install Docker Desktop
echo 2. Run: docker run -d -p 6379:6379 --name redis-server redis:alpine
echo.
pause
exit /b 0

:start_app
echo.
echo ==========================================
echo Redis is ready! Starting your app...
echo ==========================================
echo.
python app_redis.py

:end
pause
