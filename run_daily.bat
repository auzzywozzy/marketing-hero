@echo off
REM ===========================================================
REM  Marketing Hero - daily lead generator
REM  Runs lead_generator.py and logs output.
REM  Register this file with Windows Task Scheduler to run daily.
REM ===========================================================

setlocal
cd /d "%~dp0"

echo [%date% %time%] Starting Marketing Hero daily run >> data\run_log.txt

python lead_generator.py >> data\run_log.txt 2>&1

if errorlevel 1 (
    echo [%date% %time%] Run FAILED with exit code %errorlevel% >> data\run_log.txt
    exit /b %errorlevel%
)

echo [%date% %time%] Run complete >> data\run_log.txt
endlocal
