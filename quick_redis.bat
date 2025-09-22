@echo off
echo ==========================================
echo   Quick Portable Redis Setup
echo ==========================================
echo.

set REDIS_DIR=%~dp0redis-portable
set REDIS_EXE=%REDIS_DIR%\redis-server.exe

if exist "%REDIS_EXE%" (
    echo [OK] Redis already downloaded
    goto start_redis
)

echo [INFO] Creating Redis directory...
mkdir "%REDIS_DIR%" 2>nul

echo [INFO] Downloading portable Redis...
powershell -Command "& {Invoke-WebRequest -Uri 'https://github.com/microsoftarchive/redis/releases/download/win-3.0.504/Redis-x64-3.0.504.zip' -OutFile '%REDIS_DIR%\redis.zip' -UseBasicParsing}"

if not exist "%REDIS_DIR%\redis.zip" (
    echo [ERROR] Failed to download Redis
    pause
    exit /b 1
)

echo [INFO] Extracting Redis...
powershell -Command "& {Expand-Archive -Path '%REDIS_DIR%\redis.zip' -DestinationPath '%REDIS_DIR%' -Force}"

if not exist "%REDIS_EXE%" (
    echo [ERROR] Failed to extract Redis
    pause
    exit /b 1
)

echo [OK] Redis setup complete

:start_redis
echo.
echo [INFO] Starting Redis server...
echo Press Ctrl+C to stop Redis when you're done
echo.

cd /d "%REDIS_DIR%"
"%REDIS_EXE%" --port 6379 --bind 127.0.0.1

pause
