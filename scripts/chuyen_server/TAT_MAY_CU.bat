@echo off
rem Chay bang chuot phai -> Run as administrator.
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0TAT_MAY_CU.ps1" %*
pause
