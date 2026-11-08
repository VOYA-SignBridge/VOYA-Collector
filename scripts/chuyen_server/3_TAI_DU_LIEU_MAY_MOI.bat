@echo off
rem Chay bang chuot phai -> Run as administrator. Chay lai bao nhieu lan cung duoc.
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0TAI_DU_LIEU_MAY_MOI.ps1" %*
pause
