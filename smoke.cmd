@echo off
chcp 65001 >nul
call "%~dp0launch.cmd" smoke
if errorlevel 1 pause
