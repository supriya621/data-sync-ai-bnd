# Portable Redis Setup for Data Sync AI
# No admin privileges required

Write-Host "===========================================" -ForegroundColor Cyan
Write-Host "   Data Sync AI - Portable Redis Setup" -ForegroundColor Cyan  
Write-Host "===========================================" -ForegroundColor Cyan
Write-Host ""

$redisDir = Join-Path $PSScriptRoot "redis-portable"
$redisZip = Join-Path $redisDir "redis.zip"
$redisExe = Join-Path $redisDir "redis-server.exe"

# Create directory
if (-not (Test-Path $redisDir)) {
    New-Item -ItemType Directory -Path $redisDir -Force | Out-Null
    Write-Host "[INFO] Created Redis directory" -ForegroundColor Yellow
}

# Check if Redis is already downloaded
if (Test-Path $redisExe) {
    Write-Host "[OK] Redis already available" -ForegroundColor Green
    goto StartRedis
} else {
    Write-Host "[INFO] Downloading Redis for Windows..." -ForegroundColor Yellow
    
    try {
        $url = "https://github.com/microsoftarchive/redis/releases/download/win-3.0.504/Redis-x64-3.0.504.zip"
        Invoke-WebRequest -Uri $url -OutFile $redisZip -UseBasicParsing
        Write-Host "[OK] Redis downloaded successfully" -ForegroundColor Green
    } catch {
        Write-Host "[ERROR] Failed to download Redis: $($_.Exception.Message)" -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit 1
    }

    Write-Host "[INFO] Extracting Redis..." -ForegroundColor Yellow
    try {
        Expand-Archive -Path $redisZip -DestinationPath $redisDir -Force
        Write-Host "[OK] Redis extracted successfully" -ForegroundColor Green
    } catch {
        Write-Host "[ERROR] Failed to extract Redis: $($_.Exception.Message)" -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit 1
    }
}

:StartRedis
Write-Host ""
Write-Host "===========================================" -ForegroundColor Cyan
Write-Host "         Starting Redis Server" -ForegroundColor Cyan
Write-Host "===========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Redis will start on localhost:6379" -ForegroundColor Yellow
Write-Host "Press Ctrl+C to stop Redis when done" -ForegroundColor Yellow
Write-Host "Keep this window open while using your app" -ForegroundColor Yellow
Write-Host ""

# Start Redis
try {
    Set-Location $redisDir
    & $redisExe --port 6379 --bind 127.0.0.1
} catch {
    Write-Host "[ERROR] Failed to start Redis: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host ""
Write-Host "Redis has stopped." -ForegroundColor Yellow
Read-Host "Press Enter to exit"
