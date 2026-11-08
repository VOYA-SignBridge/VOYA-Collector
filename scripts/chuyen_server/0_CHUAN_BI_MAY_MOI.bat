@echo off
rem May trang: cai Git, Python, Docker Desktop, WSL2; hoi ve che do nguon. Chuot phai -> Run as administrator.
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0CHUAN_BI_MAY_MOI.ps1" %*
pause
