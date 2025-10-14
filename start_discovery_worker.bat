@echo off
echo ===============================================
echo  ANALYTICS FOLLOWING - DISCOVERY WORKER
echo ===============================================
echo  Industry Standard Background Processing
echo  Zero Impact on Main Application
echo  Processing Profiles for Database Building
echo ===============================================
echo.

echo Starting Discovery Worker...
echo Make sure Redis is running first!
echo.

py scripts/start_discovery_worker.py

pause