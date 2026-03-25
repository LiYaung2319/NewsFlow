@echo off
tasklist /FI "IMAGENAME eq python.exe" 2>nul | findstr /I "python.exe" >nul
if %errorlevel% neq 0 (
    echo NewsFlow service not running
) else (
    taskkill /F /IM python.exe >nul 2>nul
    echo NewsFlow service stopped
)
