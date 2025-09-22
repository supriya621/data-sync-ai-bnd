# Redis Installation Script for Windows
# Downloads and sets up Redis for Windows

Write-Host "===========================================" -ForegroundColor Cyan
Write-Host "     Installing Redis for Windows" -ForegroundColor Cyan
Write-Host "===========================================" -ForegroundColor Cyan

# Create Redis directory
$redisDir = "C:\Redis"
if (-not (Test-Path $redisDir)) {
    New-Item -ItemType Directory -Path $redisDir -Force
    Write-Host "[INFO] Created Redis directory at $redisDir" -ForegroundColor Green
}

# Download Redis for Windows
$redisUrl = "https://github.com/microsoftarchive/redis/releases/download/win-3.0.504/Redis-x64-3.0.504.zip"
$zipPath = "$redisDir\Redis-x64-3.0.504.zip"

try {
    Write-Host "[INFO] Downloading Redis for Windows..." -ForegroundColor Yellow
    Invoke-WebRequest -Uri $redisUrl -OutFile $zipPath -UseBasicParsing
    Write-Host "[OK] Redis downloaded successfully" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Failed to download Redis: $_" -ForegroundColor Red
    exit 1
}

# Extract Redis
try {
    Write-Host "[INFO] Extracting Redis..." -ForegroundColor Yellow
    Expand-Archive -Path $zipPath -DestinationPath $redisDir -Force
    Write-Host "[OK] Redis extracted successfully" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Failed to extract Redis: $_" -ForegroundColor Red
    exit 1
}

# Add Redis to PATH
$currentPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($currentPath -notlike "*$redisDir*") {
    [Environment]::SetEnvironmentVariable("Path", "$currentPath;$redisDir", "User")
    Write-Host "[OK] Added Redis to PATH" -ForegroundColor Green
}

# Create Redis configuration file
$redisConf = @"
port 6379
bind 127.0.0.1
timeout 0
save 900 1
save 300 10  
save 60 10000
rdbcompression yes
dbfilename dump.rdb
dir $redisDir
"@

$redisConf | Out-File -FilePath "$redisDir\redis.conf" -Encoding UTF8
Write-Host "[OK] Created Redis configuration file" -ForegroundColor Green

# Create startup script
$startScript = @"
@echo off
echo Starting Redis Server...
cd /d "$redisDir"
redis-server.exe redis.conf
"@

$startScript | Out-File -FilePath "$redisDir\start-redis.bat" -Encoding ASCII
Write-Host "[OK] Created Redis startup script" -ForegroundColor Green

Write-Host "" 
Write-Host "===========================================" -ForegroundColor Cyan
Write-Host "     Redis Installation Complete!" -ForegroundColor Cyan
Write-Host "===========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "To start Redis server:" -ForegroundColor Yellow
Write-Host "1. Open a new PowerShell window (to refresh PATH)" -ForegroundColor White
Write-Host "2. Run: redis-server" -ForegroundColor White
Write-Host "   OR" -ForegroundColor White  
Write-Host "3. Run: $redisDir\start-redis.bat" -ForegroundColor White
Write-Host ""
Write-Host "Test Redis connection with: redis-cli ping" -ForegroundColor Yellow
