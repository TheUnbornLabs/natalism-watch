@echo off
REM Starts the dashboard server and opens it in your browser.
REM Leave this window open while using the dashboard; close it (or Ctrl+C) to stop.
cd /d "%~dp0"
python serve.py
