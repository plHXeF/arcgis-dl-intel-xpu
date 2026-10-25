@echo off
chcp 65001 >nul
call "%~dp0launch.cmd" start
if errorlevel 1 pause
