@echo off
rem VOYA - mot cua cho moi viec van hanh. Bam dup de mo menu,
rem hoac go:  VOYA status | VOYA logs | VOYA backup | VOYA help
cd /d "%~dp0"
python "%~dp0scripts/voya.py" %*
if "%~1"=="" pause
