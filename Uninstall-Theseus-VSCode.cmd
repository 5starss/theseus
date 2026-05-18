@echo off
setlocal
set "THESEUS_UNINSTALL_SCRIPT=%~f0"
set "THESEUS_NO_PAUSE=0"
set "THESEUS_UNINSTALL_DRY_RUN=0"
set "THESEUS_UNINSTALL_HELP=0"
set "THESEUS_UNINSTALL_WORKSPACE="
set "THESEUS_UNINSTALL_KEEP_VENV=0"
set "THESEUS_UNINSTALL_KEEP_WORKSPACE_VSCODE=0"

:parse_args
if "%~1"=="" goto run_script
if /I "%~1"=="-DryRun" (
  set "THESEUS_UNINSTALL_DRY_RUN=1"
  shift
  goto parse_args
)
if /I "%~1"=="--dry-run" (
  set "THESEUS_UNINSTALL_DRY_RUN=1"
  shift
  goto parse_args
)
if /I "%~1"=="-NoPause" (
  set "THESEUS_NO_PAUSE=1"
  shift
  goto parse_args
)
if /I "%~1"=="--no-pause" (
  set "THESEUS_NO_PAUSE=1"
  shift
  goto parse_args
)
if /I "%~1"=="-Help" (
  set "THESEUS_UNINSTALL_HELP=1"
  set "THESEUS_NO_PAUSE=1"
  shift
  goto parse_args
)
if /I "%~1"=="--help" (
  set "THESEUS_UNINSTALL_HELP=1"
  set "THESEUS_NO_PAUSE=1"
  shift
  goto parse_args
)
if /I "%~1"=="/?" (
  set "THESEUS_UNINSTALL_HELP=1"
  set "THESEUS_NO_PAUSE=1"
  shift
  goto parse_args
)
if /I "%~1"=="-KeepVenv" (
  set "THESEUS_UNINSTALL_KEEP_VENV=1"
  shift
  goto parse_args
)
if /I "%~1"=="--keep-venv" (
  set "THESEUS_UNINSTALL_KEEP_VENV=1"
  shift
  goto parse_args
)
if /I "%~1"=="-KeepWorkspaceVscode" (
  set "THESEUS_UNINSTALL_KEEP_WORKSPACE_VSCODE=1"
  shift
  goto parse_args
)
if /I "%~1"=="--keep-workspace-vscode" (
  set "THESEUS_UNINSTALL_KEEP_WORKSPACE_VSCODE=1"
  shift
  goto parse_args
)
if /I "%~1"=="-WorkspacePath" (
  if "%~2"=="" (
    echo Missing value for -WorkspacePath
    exit /b 2
  )
  set "THESEUS_UNINSTALL_WORKSPACE=%~2"
  shift
  shift
  goto parse_args
)
echo Unknown option: %~1
exit /b 2

:run_script
powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$raw = Get-Content -LiteralPath $env:THESEUS_UNINSTALL_SCRIPT -Raw -Encoding UTF8; $marker = '### THESEUS_' + 'POWERSHELL_BODY ###'; $index = $raw.IndexOf($marker); if ($index -lt 0) { throw 'PowerShell body marker was not found.' }; $code = $raw.Substring($index + $marker.Length); & ([scriptblock]::Create($code))"
set "THESEUS_EXIT_CODE=%ERRORLEVEL%"
if not "%THESEUS_NO_PAUSE%"=="1" pause
exit /b %THESEUS_EXIT_CODE%

### THESEUS_POWERSHELL_BODY ###

[CmdletBinding()]
param(
    [switch]$DryRun,
    [switch]$NoPause,
    [switch]$Help,
    [switch]$KeepVenv,
    [switch]$KeepWorkspaceVscode,
    [string]$WorkspacePath = ""
)

$ErrorActionPreference = "Stop"

function Show-Usage {
    Write-Host "Usage: Uninstall-Theseus-VSCode.cmd [options]"
    Write-Host ""
    Write-Host "Options:"
    Write-Host "  -DryRun              Show what would be deleted without changing files"
    Write-Host "  -WorkspacePath PATH  Workspace whose .vscode and .theseus/runner.json should be cleaned"
    Write-Host "  -KeepVenv            Keep backend/theseus-core-server/.venv"
    Write-Host "  -KeepWorkspaceVscode Keep workspace .vscode and only remove theseus.* settings"
    Write-Host "  -NoPause             Do not pause when launched from cmd"
    Write-Host "  -Help, --help, /?    Show this help"
}

if ($env:THESEUS_UNINSTALL_DRY_RUN -eq "1") {
    $DryRun = $true
}
if ($env:THESEUS_UNINSTALL_HELP -eq "1") {
    $Help = $true
}
if (-not [string]::IsNullOrWhiteSpace($env:THESEUS_UNINSTALL_WORKSPACE)) {
    $WorkspacePath = $env:THESEUS_UNINSTALL_WORKSPACE
}
if ($env:THESEUS_UNINSTALL_KEEP_VENV -eq "1") {
    $KeepVenv = $true
}
if ($env:THESEUS_UNINSTALL_KEEP_WORKSPACE_VSCODE -eq "1") {
    $KeepWorkspaceVscode = $true
}

if ($Help) {
    Show-Usage
    exit 0
}

$scriptPath = $env:THESEUS_UNINSTALL_SCRIPT
if ([string]::IsNullOrWhiteSpace($scriptPath)) {
    throw "THESEUS_UNINSTALL_SCRIPT is not set."
}
$repoRoot = Split-Path -Parent $scriptPath
if ([string]::IsNullOrWhiteSpace($WorkspacePath)) {
    $WorkspacePath = $repoRoot
}
$WorkspacePath = (Resolve-Path -LiteralPath $WorkspacePath).Path

function Write-Step {
    param([string]$Message)
    Write-Host "[Theseus uninstall] $Message"
}

function Remove-SafePath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [Parameter(Mandatory = $true)]
        [string]$AllowedRoot
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        return
    }

    $resolvedPath = (Resolve-Path -LiteralPath $Path).Path
    $resolvedRoot = (Resolve-Path -LiteralPath $AllowedRoot).Path
    if (-not $resolvedPath.StartsWith($resolvedRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to remove outside allowed root: $resolvedPath"
    }

    if ($DryRun) {
        Write-Step "Would remove: $resolvedPath"
        return
    }

    Remove-Item -LiteralPath $resolvedPath -Recurse -Force
    Write-Step "Removed: $resolvedPath"
}

function Remove-TheseusSettings {
    param([string]$SettingsPath)

    if (-not (Test-Path -LiteralPath $SettingsPath)) {
        return
    }

    $rawSettings = Get-Content -LiteralPath $SettingsPath -Raw -Encoding UTF8
    try {
        $settings = $rawSettings | ConvertFrom-Json
    }
    catch {
        $lines = @($rawSettings -split "\r?\n")
        $keptLines = @(
            $lines | Where-Object {
                $_ -notmatch '^\s*"theseus\.[^"]+"\s*:'
            }
        )
        $removedCount = $lines.Count - $keptLines.Count
        if (-not $removedCount) {
            Write-Warning "Skipping non-JSON settings file without Theseus keys: $SettingsPath"
            return
        }
        if ($DryRun) {
            Write-Step "Would remove $removedCount Theseus settings line(s) from JSONC file: $SettingsPath"
            return
        }
        Set-Content -LiteralPath $SettingsPath -Value ($keptLines -join [Environment]::NewLine) -Encoding UTF8
        Write-Step "Removed $removedCount Theseus settings line(s) from JSONC file: $SettingsPath"
        return
    }

    $removed = @()
    foreach ($property in @($settings.PSObject.Properties.Name)) {
        if ($property -like "theseus.*") {
            $removed += $property
            if (-not $DryRun) {
                $settings.PSObject.Properties.Remove($property)
            }
        }
    }

    if (-not $removed.Count) {
        return
    }

    if ($DryRun) {
        Write-Step "Would remove workspace settings keys from ${SettingsPath}: $($removed -join ', ')"
        return
    }

    $settings | ConvertTo-Json -Depth 32 | Set-Content -LiteralPath $SettingsPath -Encoding UTF8
    Write-Step "Removed workspace settings keys: $($removed -join ', ')"
}

function Get-TheseusCorePathFromSettings {
    param([string]$SettingsPath)

    if (-not (Test-Path -LiteralPath $SettingsPath)) {
        return ""
    }

    try {
        $settings = Get-Content -LiteralPath $SettingsPath -Raw -Encoding UTF8 | ConvertFrom-Json
    }
    catch {
        Write-Warning "Could not read workspace settings for corePath detection: $SettingsPath"
        return ""
    }

    $property = $settings.PSObject.Properties["theseus.corePath"]
    if ($null -eq $property -or [string]::IsNullOrWhiteSpace([string]$property.Value)) {
        return ""
    }

    $path = [string]$property.Value
    if (-not (Test-Path -LiteralPath $path)) {
        Write-Warning "Configured theseus.corePath does not exist, skipping venv candidate: $path"
        return ""
    }

    return (Resolve-Path -LiteralPath $path).Path
}

function Resolve-CoreRootCandidates {
    param(
        [string]$ConfiguredCorePath,
        [string]$WorkspaceRoot,
        [string]$ScriptRoot
    )

    $candidates = @(
        $ConfiguredCorePath,
        (Join-Path $WorkspaceRoot "backend\theseus-core-server"),
        (Join-Path $ScriptRoot "backend\theseus-core-server")
    )

    $resolved = @()
    foreach ($candidate in $candidates) {
        if ([string]::IsNullOrWhiteSpace($candidate)) {
            continue
        }
        if (-not (Test-Path -LiteralPath $candidate)) {
            continue
        }
        $path = (Resolve-Path -LiteralPath $candidate).Path
        if ($resolved -notcontains $path) {
            $resolved += $path
        }
    }

    return $resolved
}

function Remove-TheseusVenvs {
    param([string[]]$CoreRoots)

    foreach ($coreRoot in $CoreRoots) {
        $venvPath = Join-Path $coreRoot ".venv"
        if (Test-Path -LiteralPath $venvPath) {
            Remove-SafePath -Path $venvPath -AllowedRoot $coreRoot
        }
    }
}

function Remove-TheseusExtensionMetadata {
    param([string]$ExtensionsJson)

    if (-not (Test-Path -LiteralPath $ExtensionsJson)) {
        return
    }

    try {
        $items = @(Get-Content -LiteralPath $ExtensionsJson -Raw -Encoding UTF8 | ConvertFrom-Json)
    }
    catch {
        Write-Warning "Skipping unreadable extensions.json: $ExtensionsJson"
        return
    }

    $kept = @(
        $items | Where-Object {
            $identifier = $_.identifier.id
            $relativeLocation = $_.relativeLocation
            $locationPath = $_.location.path
            $locationFsPath = $_.location.fsPath
            $locationExternal = $_.location.external
            $text = "$identifier $relativeLocation $locationPath $locationFsPath $locationExternal"
            $text -notlike "*theseus.theseus-vscode*"
        }
    )

    if ($kept.Count -eq $items.Count) {
        return
    }

    if ($DryRun) {
        Write-Step "Would remove Theseus entry from: $ExtensionsJson"
        return
    }

    ConvertTo-Json -InputObject $kept -Depth 100 -Compress | Set-Content -LiteralPath $ExtensionsJson -Encoding UTF8
    Write-Step "Removed theseus.theseus-vscode from VSCode extensions.json"
}

function Remove-TheseusObsoleteEntry {
    param([string]$ObsoletePath)

    if (-not (Test-Path -LiteralPath $ObsoletePath)) {
        return
    }

    try {
        $obsolete = Get-Content -LiteralPath $ObsoletePath -Raw -Encoding UTF8 | ConvertFrom-Json
    }
    catch {
        Write-Warning "Skipping unreadable .obsolete file: $ObsoletePath"
        return
    }

    $removed = @()
    foreach ($property in @($obsolete.PSObject.Properties.Name)) {
        if ($property -like "theseus.theseus-vscode*") {
            $removed += $property
            if (-not $DryRun) {
                $obsolete.PSObject.Properties.Remove($property)
            }
        }
    }

    if (-not $removed.Count) {
        return
    }

    if ($DryRun) {
        Write-Step "Would remove Theseus .obsolete entries: $($removed -join ', ')"
        return
    }

    $obsolete | ConvertTo-Json -Depth 32 -Compress | Set-Content -LiteralPath $ObsoletePath -Encoding UTF8
    Write-Step "Removed Theseus .obsolete entries: $($removed -join ', ')"
}

function Find-Python {
    $candidates = @(
        (Join-Path $WorkspacePath "backend\theseus-core-server\.venv\Scripts\python.exe"),
        (Join-Path $repoRoot "backend\theseus-core-server\.venv\Scripts\python.exe")
    )

    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }

    foreach ($name in @("python", "py")) {
        $command = Get-Command $name -ErrorAction SilentlyContinue
        if ($command) {
            return $command.Source
        }
    }

    return ""
}

function Clear-WorkspaceStorage {
    $workspaceStorageRoot = Join-Path $env:APPDATA "Code\User\workspaceStorage"
    if (-not (Test-Path -LiteralPath $workspaceStorageRoot)) {
        return
    }

    $python = Find-Python
    if ([string]::IsNullOrWhiteSpace($python)) {
        Write-Warning "Python was not found; skipping VSCode workspaceStorage cleanup."
        return
    }

    $dbs = @(
        Get-ChildItem -LiteralPath $workspaceStorageRoot -Directory -ErrorAction SilentlyContinue |
            ForEach-Object {
                $db = Join-Path $_.FullName "state.vscdb"
                if (Test-Path -LiteralPath $db) {
                    $db
                }
            }
    )

    if (-not $dbs.Count) {
        return
    }

    $pythonCode = @"
import sqlite3
import sys

dry_run = sys.argv[1] == "1"
for db in sys.argv[2:]:
    try:
        con = sqlite3.connect(db)
        cur = con.cursor()
        if dry_run:
            rows = cur.execute(
                "select key from ItemTable where key like ?",
                ("%theseus%",),
            ).fetchall()
            if rows:
                print(f"Would clear VSCode workspaceState Theseus keys: {db} rows={len(rows)}")
        else:
            cur.execute(
                "delete from ItemTable where key like ?",
                ("%theseus%",),
            )
            rows = cur.rowcount
            con.commit()
            if rows:
                print(f"Cleared VSCode workspaceState Theseus keys: {db} rows={rows}")
        con.close()
    except Exception as exc:
        print(f"Skipping workspaceState DB {db}: {exc}", file=sys.stderr)
"@

    $dryRunFlag = if ($DryRun) { "1" } else { "0" }
    $encodedPythonCode = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($pythonCode))
    & $python -c "import base64, sys; code = base64.b64decode(sys.argv[1]).decode('utf-8'); sys.argv = [sys.argv[0]] + sys.argv[2:]; exec(code)" $encodedPythonCode $dryRunFlag @dbs
}

Write-Step "Workspace: $WorkspacePath"
if ($DryRun) {
    Write-Step "Dry-run mode: no files will be changed."
}

$workspaceVscodePath = Join-Path $WorkspacePath ".vscode"
$workspaceSettingsPath = Join-Path $workspaceVscodePath "settings.json"
$configuredCorePath = Get-TheseusCorePathFromSettings -SettingsPath $workspaceSettingsPath
$coreRootCandidates = Resolve-CoreRootCandidates `
    -ConfiguredCorePath $configuredCorePath `
    -WorkspaceRoot $WorkspacePath `
    -ScriptRoot $repoRoot

if (Get-Process -Name Code -ErrorAction SilentlyContinue) {
    Write-Warning "VS Code is currently running. Close and reopen VS Code after uninstall cleanup."
}

$extensionsRoot = Join-Path $env:USERPROFILE ".vscode\extensions"
if (Test-Path -LiteralPath $extensionsRoot) {
    Get-ChildItem -LiteralPath $extensionsRoot -Directory -Filter "theseus.theseus-vscode*" -ErrorAction SilentlyContinue |
        ForEach-Object {
            Remove-SafePath -Path $_.FullName -AllowedRoot $extensionsRoot
        }
    Remove-TheseusExtensionMetadata -ExtensionsJson (Join-Path $extensionsRoot "extensions.json")
    Remove-TheseusObsoleteEntry -ObsoletePath (Join-Path $extensionsRoot ".obsolete")
}

$globalStorageRoot = Join-Path $env:APPDATA "Code\User\globalStorage"
$globalStoragePath = Join-Path $globalStorageRoot "theseus.theseus-vscode"
if (Test-Path -LiteralPath $globalStoragePath) {
    Remove-SafePath -Path $globalStoragePath -AllowedRoot $globalStorageRoot
}

$userSettingsPath = Join-Path $env:APPDATA "Code\User\settings.json"
Remove-TheseusSettings -SettingsPath $userSettingsPath

if ($KeepWorkspaceVscode) {
    Remove-TheseusSettings -SettingsPath $workspaceSettingsPath
}
else {
    Remove-SafePath -Path $workspaceVscodePath -AllowedRoot $WorkspacePath
}

$runnerStatePath = Join-Path $WorkspacePath ".theseus\runner.json"
if (Test-Path -LiteralPath $runnerStatePath) {
    Remove-SafePath -Path $runnerStatePath -AllowedRoot (Join-Path $WorkspacePath ".theseus")
}

Clear-WorkspaceStorage

if ($KeepVenv) {
    Write-Step "Keeping Theseus venv because -KeepVenv was specified."
}
else {
    Remove-TheseusVenvs -CoreRoots $coreRootCandidates
}

$remainingDirs = @()
if (Test-Path -LiteralPath $extensionsRoot) {
    $remainingDirs = @(
        Get-ChildItem -LiteralPath $extensionsRoot -Directory -Filter "theseus.theseus-vscode*" -ErrorAction SilentlyContinue
    )
}

Write-Step "Remaining VSCode Theseus extension dirs: $($remainingDirs.Count)"
Write-Step "Done."
