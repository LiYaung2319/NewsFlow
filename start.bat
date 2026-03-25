@echo off
cd /d %~dp0

if not exist logs mkdir logs

powershell -Command "Start-Process -FilePath '.venv\Scripts\python.exe' -ArgumentList 'main.py' -RedirectStandardOutput 'logs\output.log' -RedirectStandardError 'logs\error.log' -WindowStyle Hidden -WorkingDirectory '%CD%'"

echo NewsFlow started
echo Log file: logs\output.log
echo Stop service: stop.bat
