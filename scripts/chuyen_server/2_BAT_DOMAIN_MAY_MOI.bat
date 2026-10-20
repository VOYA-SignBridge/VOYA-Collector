@echo off
rem Chay bang chuot phai -> Run as administrator.
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0BAT_DOMAIN_MAY_MOI.ps1" %*
pause
