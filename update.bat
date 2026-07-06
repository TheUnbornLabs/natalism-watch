@echo off
REM Collects fresh data and regenerates dashboard.html. Used by the daily scheduled task.
cd /d "%~dp0"
python collect.py
