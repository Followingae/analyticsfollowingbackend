@echo off
echo 🚨 STARTING ANALYTICS BACKEND WITH MANDATORY AI SYSTEM
echo ===============================================

echo.
echo 1. Starting Redis Server (Required for AI background processing)...
start /B redis-server
timeout /t 3 >nul

echo.
echo 2. Verifying Redis connection...
redis-cli ping
if errorlevel 1 (
    echo ❌ Redis connection failed - Install and start Redis first
    pause
    exit /b 1
)
echo ✅ Redis is running

echo.
echo 3. Starting FastAPI with MANDATORY AI initialization...
echo 🚨 System will FAIL if AI models cannot be loaded
echo.
python main.py

pause