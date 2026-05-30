@echo off
cd /d "C:\Users\callu\OneDrive\Documents\RenewaBlox\Claude Code\agile-predictor"
if not exist logs mkdir logs
echo. >> "logs\ingest.log"
echo === run started at %DATE% %TIME% === >> "logs\ingest.log"
".venv\Scripts\python.exe" ingest.py >> "logs\ingest.log" 2>&1
echo === run finished at %DATE% %TIME% === >> "logs\ingest.log"
