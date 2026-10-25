@echo off
if not exist "%~dp0config.local.json" copy "%~dp0config.json" "%~dp0config.local.json" >nul
notepad.exe "%~dp0config.local.json"
