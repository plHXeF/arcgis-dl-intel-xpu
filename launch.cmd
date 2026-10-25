@echo off
setlocal DisableDelayedExpansion
chcp 65001 >nul
set "PATCH_ACTION=%~1"
if not defined PATCH_ACTION set "PATCH_ACTION=start"
set "PATCH_CONFIG=%~dp0config.local.json"
if not exist "%PATCH_CONFIG%" set "PATCH_CONFIG=%~dp0config.json"
set "PATCH_PYTHON="
rem PowerShell reads JSON as data only. No .ps1 loading or execution-policy changes.
for /f "usebackq delims=" %%P in (`powershell.exe -NoProfile -NonInteractive -Command "[Console]::OutputEncoding=[Text.UTF8Encoding]::new(); $ErrorActionPreference='Stop'; try { $c=ConvertFrom-Json -InputObject ([IO.File]::ReadAllText($env:PATCH_CONFIG,[Text.Encoding]::UTF8)); $d=$c.arcgis_pro_dir; if(-not $d){$d=Join-Path $env:ProgramFiles 'ArcGIS\Pro'}; $d=[Environment]::ExpandEnvironmentVariables($d); if(-not [IO.Path]::IsPathRooted($d)){$d=Join-Path (Split-Path $env:PATCH_CONFIG) $d}; $p=[IO.Path]::GetFullPath((Join-Path $d 'bin\Python\envs\arcgispro-py3\python.exe')); if(-not [IO.File]::Exists($p)){throw 'ArcGIS Python not found. Check arcgis_pro_dir in config.local.json.'}; [Console]::WriteLine($p) } catch { [Console]::Error.WriteLine($_.Exception.Message); exit 1 }"`) do set "PATCH_PYTHON=%%P"
if not defined PATCH_PYTHON exit /b 1
set "PYTHONUTF8=1"
"%PATCH_PYTHON%" -I -X utf8 -u "%~dp0patch_manager.py" "%PATCH_ACTION%" --config "%PATCH_CONFIG%"
exit /b %ERRORLEVEL%
