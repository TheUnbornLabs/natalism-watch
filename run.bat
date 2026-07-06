@echo off
REM Manual run: collect fresh data, then open the dashboard in your browser.
cd /d "%~dp0"
echo Collecting latest items...
python collect.py
echo.
echo Opening dashboard...
start "" "%~dp0dashboard.html"
