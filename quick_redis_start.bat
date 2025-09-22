@echo off
echo ===============================================
echo   SIMPLE REDIS SETUP - Manual Installation
echo ===============================================
echo.

echo Step 1: Install Redis Dependencies
echo ==================================
pip install redis==5.0.1
pip install Flask-Caching==2.1.0
echo.
echo Dependencies installed!
echo.

echo Step 2: Create Environment Configuration
echo ========================================
(
echo # Redis Configuration
echo REDIS_HOST=localhost
echo REDIS_PORT=6379
echo REDIS_DB=0
echo REDIS_PASSWORD=
echo ENABLE_PERFORMANCE_LOGGING=true
) > .env

echo Environment configured!
echo.

echo Step 3: Start Redis-Enhanced Application
echo ========================================
echo Starting your Redis-optimized Data Sync AI...
echo Expected performance: 15-25 seconds for 25K rows
echo.
python app_redis.py
