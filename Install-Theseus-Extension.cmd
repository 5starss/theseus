@echo off
setlocal EnableExtensions DisableDelayedExpansion

set "REPO_ROOT=%~dp0"
for %%I in ("%REPO_ROOT%.") do set "REPO_ROOT=%%~fI"

set "CORE_PATH=%REPO_ROOT%\backend\theseus-core-server"
set "INSTALLER=%CORE_PATH%\scripts\install-vscode-extension.ps1"
set "HAS_CORE_PATH=0"
set "HAS_WORKSPACE_PATH=0"
set "SHOW_HELP=0"
set "POWERSHELL_EXE="

for %%A in (%*) do (
    if /I "%%~A"=="-CorePath" set "HAS_CORE_PATH=1"
    if /I "%%~A"=="--core-path" set "HAS_CORE_PATH=1"
    if /I "%%~A"=="-WorkspacePath" set "HAS_WORKSPACE_PATH=1"
    if /I "%%~A"=="--workspace-path" set "HAS_WORKSPACE_PATH=1"
    if /I "%%~A"=="-Help" set "SHOW_HELP=1"
    if /I "%%~A"=="--help" set "SHOW_HELP=1"
    if /I "%%~A"=="-h" set "SHOW_HELP=1"
    if /I "%%~A"=="/?" set "SHOW_HELP=1"
)

if "%SHOW_HELP%"=="1" goto :show_usage

if not exist "%INSTALLER%" (
    echo Theseus installer was not found:
    echo   %INSTALLER%
    echo.
    echo Run this file from the repository root, or check that backend\theseus-core-server exists.
    pause
    exit /b 1
)

if exist "%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe" (
    set "POWERSHELL_EXE=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
)

if not defined POWERSHELL_EXE (
    for /f "delims=" %%P in ('where powershell.exe 2^>nul') do (
        if not defined POWERSHELL_EXE set "POWERSHELL_EXE=%%P"
    )
)

if not defined POWERSHELL_EXE (
    for /f "delims=" %%P in ('where pwsh.exe 2^>nul') do (
        if not defined POWERSHELL_EXE set "POWERSHELL_EXE=%%P"
    )
)

if not defined POWERSHELL_EXE (
    echo PowerShell was not found.
    echo Install Windows PowerShell or PowerShell 7, then rerun this file.
    pause
    exit /b 1
)

set "DEFAULT_CORE_ARG="
if "%HAS_CORE_PATH%"=="0" set DEFAULT_CORE_ARG=-CorePath "%CORE_PATH%"

set "DEFAULT_WORKSPACE_ARG="
if "%HAS_WORKSPACE_PATH%"=="0" set DEFAULT_WORKSPACE_ARG=-WorkspacePath "%REPO_ROOT%"

echo Theseus one-click extension setup
echo Repository : %REPO_ROOT%
echo Core       : %CORE_PATH%
echo Installer  : %INSTALLER%
echo PowerShell : %POWERSHELL_EXE%
echo.
echo This will create/update the local Python venv, install requirements,
echo write Theseus editor settings, and install the latest VSIX package.
echo.

"%POWERSHELL_EXE%" -NoProfile -ExecutionPolicy Bypass -File "%INSTALLER%" %DEFAULT_CORE_ARG% %DEFAULT_WORKSPACE_ARG% %*
set "EXIT_CODE=%ERRORLEVEL%"

echo.
if not "%EXIT_CODE%"=="0" (
    echo Theseus setup failed with exit code %EXIT_CODE%.
    echo Check the messages above, then rerun this file.
    pause
    exit /b %EXIT_CODE%
)

echo Theseus setup complete.
echo Open VS Code or Antigravity, open the Theseus sidebar, then run "Theseus: Start Agent".
echo Optional: rerun this file with -Ide antigravity or -Ide vscode when auto-detection picks the wrong editor.
pause
exit /b 0

:show_usage
echo Usage:
echo   Install-Theseus-Extension.cmd [PowerShell installer options]
echo.
echo Common options:
echo   -Ide vscode^|antigravity^|auto
echo   -WorkspacePath PATH
echo   -CorePath PATH
echo   -Code PATH
echo   -VsixPath PATH
echo   -RunnerPath PATH
echo   -SkipRequirements
echo   -SkipExtension
echo   -SkipSettings
echo   -InstallPlaywright
echo.
echo Defaults:
echo   CorePath      %CORE_PATH%
echo   WorkspacePath %REPO_ROOT%
echo.
echo Examples:
echo   Install-Theseus-Extension.cmd -Ide vscode
echo   Install-Theseus-Extension.cmd -Ide antigravity
echo   Install-Theseus-Extension.cmd -WorkspacePath C:\path\to\project
echo   Install-Theseus-Extension.cmd -RunnerPath C:\path\to\theseus-runner.exe
echo.
exit /b 0
