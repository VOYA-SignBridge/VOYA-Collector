@echo off
REM Vo boc cho Task Scheduler.
REM
REM Hai cai bay, deu da mac that ngay 13/08/2026, va deu HONG TRONG IM LANG:
REM
REM 1. Dang ky truc tiep `bash "E:/duong/dan.sh"`: Task Scheduler chen them
REM    mot dau backslash vao dau tham so, bash bao "No such file or directory".
REM
REM 2. Goi `bash` tran: PATH cua MAY chi co "C:\Program Files\Git\cmd", noi co
REM    git.exe nhung KHONG co bash.exe. Shell tuong tac tim thay vi MSYS them
REM    /usr/bin vao PATH cua rieng no - nen chay tay thi duoc, chay theo lich
REM    thi khong. Phai dung duong dan TUYET DOI.
REM
REM Ca hai lan, schtasks van bao SUCCESS va Status Ready; chi "Last Result: 1"
REM cung mot tep log khong bao gio dai them moi to cao. Vi the wrapper nay tu
REM ghi log rieng: mot lan chay hong phai de lai dau vet doc duoc.

set "TASKLOG=E:\CTU_ProjectOutside\voya_backups\docker_watch_task.log"

set "BASH=C:\Program Files\Git\bin\bash.exe"
if not exist "%BASH%" set "BASH=C:\Program Files\Git\usr\bin\bash.exe"
if not exist "%BASH%" (
  echo %DATE% %TIME% KHONG TIM THAY bash.exe >> "%TASKLOG%"
  exit /b 2
)

cd /d "%~dp0.."
echo %DATE% %TIME% bat dau >> "%TASKLOG%"
"%BASH%" scripts/docker_watch.sh >> "%TASKLOG%" 2>&1
echo %DATE% %TIME% ket thuc ma=%ERRORLEVEL% >> "%TASKLOG%"
exit /b %ERRORLEVEL%
