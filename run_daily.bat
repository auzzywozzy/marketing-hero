@echo off
REM ===========================================================
REM  Marketing Hero - daily lead generator + auto-deploy
REM  Runs lead_generator.py, commits, and pushes to GitHub
REM  so the live dashboard stays up to date.
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

echo [%date% %time%] Run complete, deploying... >> data\run_log.txt

REM Commit and push updated lead data. Safe to run even if nothing changed.
git add data/leads.json data/leads.js data/run_log.txt >> data\run_log.txt 2>&1
git diff --cached --quiet
if errorlevel 1 (
    git commit -m "Daily lead refresh %date% %time%" >> data\run_log.txt 2>&1
    git push origin main >> data\run_log.txt 2>&1
    if errorlevel 1 (
        echo [%date% %time%] WARNING: git push failed - leads saved locally but live site not updated >> data\run_log.txt
    ) else (
        echo [%date% %time%] Deployed to live dashboard >> data\run_log.txt
    )
) else (
    echo [%date% %time%] No new lead data to deploy >> data\run_log.txt
)

echo [%date% %time%] Done >> data\run_log.txt
endlocal
