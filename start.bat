@echo off
cd /d %~dp0

if not exist logs mkdir logs
if exist logs\app.log del /q logs\app.log
set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"

powershell -Command "Start-Process -FilePath '.venv\Scripts\python.exe' -ArgumentList 'main.py' -RedirectStandardOutput 'logs\output.log' -RedirectStandardError 'logs\error.log' -WindowStyle Hidden -WorkingDirectory '%CD%'"

echo NewsFlow started
echo Log file: logs\output.log
echo Error log: logs\error.log
echo Stop service: stop.bat
