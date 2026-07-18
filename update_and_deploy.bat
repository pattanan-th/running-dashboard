@echo off
REM Daily Garmin → Dashboard pipeline (Level 2 automation)
REM Double-click this file every morning to update everything.
cd /d "%~dp0"

REM Force UTF-8 so Thai output from the Python scripts doesn't crash the console
set PYTHONIOENCODING=utf-8
chcp 65001 >nul

echo.
echo ==========================================
echo  Korat 21 - Daily Update Pipeline
echo ==========================================
echo.

echo [1/4] Scraping Garmin Connect...
python daily_scrape.py
if errorlevel 1 (
    echo.
    echo ERROR: Garmin scrape failed.
    echo Check .env credentials or run: python daily_scrape.py
    pause
    exit /b 1
)

echo.
echo [2/4] Building dashboard...
python build_dashboard.py
if errorlevel 1 (
    echo ERROR: Build failed
    pause
    exit /b 1
)

echo.
echo [3/4] Checking for changes...
git add .
git diff --cached --quiet
if errorlevel 1 (
    echo Changes detected, committing...
    git commit -m "daily update %date% %time:~0,5%"
) else (
    echo No changes to push. Done.
    pause
    exit /b 0
)

echo.
echo [4/4] Pushing to GitHub...
git push
if errorlevel 1 (
    echo ERROR: Push failed - check internet
    pause
    exit /b 1
)

echo.
echo ==========================================
echo  Done! Dashboard updates in ~1 min:
echo  https://pattanan-th.github.io/running-dashboard/dashboard.html
echo ==========================================
pause
