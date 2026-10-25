@echo off
chcp 65001 >nul
call "%~dp0launch.cmd" rollback
set "PATCH_EXIT=%ERRORLEVEL%"
pause
exit /b %PATCH_EXIT%
