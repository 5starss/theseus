@echo off
setlocal

set "REPO_DIR=%~dp0"
for %%I in ("%REPO_DIR%.") do set "REPO_DIR=%%~fI"

set "PACKAGER=%REPO_DIR%\backend\theseus-core-server\scripts\package-test-distribution.ps1"
if not exist "%PACKAGER%" (
    echo Theseus test package builder was not found.
    echo.
    echo Expected:
    echo   %PACKAGER%
    echo.
    pause
    exit /b 1
)

echo Theseus test package build
echo Repository: %REPO_DIR%
echo Packager  : %PACKAGER%
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%PACKAGER%" -BuildVsix %*
set "EXIT_CODE=%ERRORLEVEL%"

echo.
if not "%EXIT_CODE%"=="0" (
    echo Theseus test package build failed with exit code %EXIT_CODE%.
    pause
    exit /b %EXIT_CODE%
)

echo Theseus test package build complete.
pause
exit /b 0
