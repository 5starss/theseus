[CmdletBinding()]
param(
    [string]$CorePath = "",
    [string]$Python = "",
    [string]$OutputDir = "",
    [switch]$InstallPyInstaller,
    [switch]$OneFile
)

$ErrorActionPreference = "Stop"
$ScriptRoot = if ([string]::IsNullOrWhiteSpace($PSScriptRoot)) {
    Split-Path -Parent $MyInvocation.MyCommand.Path
}
else {
    $PSScriptRoot
}

function Resolve-CorePath {
    param([string]$Value)

    if ([string]::IsNullOrWhiteSpace($Value)) {
        $Value = Join-Path $script:ScriptRoot ".."
    }
    if (-not (Test-Path -LiteralPath $Value)) {
        throw "CorePath does not exist: $Value"
    }
    return (Resolve-Path -LiteralPath $Value).Path
}

function Get-VenvPython {
    param([string]$CoreRoot)

    $windowsPython = Join-Path $CoreRoot ".venv\Scripts\python.exe"
    if (Test-Path -LiteralPath $windowsPython) {
        return (Resolve-Path -LiteralPath $windowsPython).Path
    }
    $posixPython = Join-Path $CoreRoot ".venv/bin/python"
    if (Test-Path -LiteralPath $posixPython) {
        return (Resolve-Path -LiteralPath $posixPython).Path
    }
    return ""
}

$CorePath = Resolve-CorePath -Value $CorePath
if ([string]::IsNullOrWhiteSpace($Python)) {
    $Python = Get-VenvPython -CoreRoot $CorePath
}
if ([string]::IsNullOrWhiteSpace($Python)) {
    $Python = "python"
}
if ([string]::IsNullOrWhiteSpace($OutputDir)) {
    $OutputDir = Join-Path $CorePath "dist\theseus-runner"
}

$entrypoint = Join-Path $CorePath "theseus_engine\runner_entry.py"
if (-not (Test-Path -LiteralPath $entrypoint)) {
    throw "Runner entrypoint was not found: $entrypoint"
}

if ($InstallPyInstaller) {
    & $Python -m pip install pyinstaller
}

& $Python -m PyInstaller --version | Out-Null

$modeArg = if ($OneFile) { "--onefile" } else { "--onedir" }
$customToolsDir = Join-Path $CorePath "theseus_engine\custom_tools"
$dataArg = "$customToolsDir;theseus_engine\custom_tools"

New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null

& $Python -m PyInstaller `
    --noconfirm `
    --clean `
    $modeArg `
    --console `
    --name theseus-runner `
    --distpath $OutputDir `
    --workpath (Join-Path $CorePath "build\theseus-runner") `
    --specpath (Join-Path $CorePath "build\theseus-runner") `
    --paths $CorePath `
    --collect-submodules theseus_engine `
    --add-data $dataArg `
    $entrypoint

Write-Host "Theseus runner binary build complete."
Write-Host "OutputDir: $OutputDir"
if ($OneFile) {
    Write-Host "RunnerPath: $(Join-Path $OutputDir 'theseus-runner.exe')"
}
else {
    Write-Host "RunnerPath: $(Join-Path $OutputDir 'theseus-runner\theseus-runner.exe')"
}
