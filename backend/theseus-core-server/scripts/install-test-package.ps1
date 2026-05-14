[CmdletBinding()]
param(
    [string]$PackagePath = "",
    [string]$WorkspacePath = "",
    [ValidateSet("auto", "vscode", "antigravity")]
    [string]$Ide = "auto",
    [string]$Code = "",
    [string]$VsixPath = "",
    [string]$RunnerPath = "",
    [switch]$NoLaunch,
    [switch]$Help
)

$ErrorActionPreference = "Stop"

function Show-Usage {
    Write-Host "Usage: Install-Theseus-TestPackage.cmd [options]"
    Write-Host ""
    Write-Host "Options passed through to this PowerShell installer:"
    Write-Host "  -WorkspacePath PATH   Project/workspace folder to open"
    Write-Host "  -Ide vscode|antigravity|auto"
    Write-Host "  -Code PATH            Explicit IDE CLI path"
    Write-Host "  -VsixPath PATH        Explicit VSIX file"
    Write-Host "  -RunnerPath PATH      Explicit theseus-runner.exe path"
    Write-Host "  -NoLaunch             Install and write settings without opening the IDE"
}

function Resolve-OptionalPath {
    param(
        [string]$Value,
        [string]$Label
    )
    if ([string]::IsNullOrWhiteSpace($Value)) {
        return ""
    }
    if (-not (Test-Path -LiteralPath $Value)) {
        throw "$Label path does not exist: $Value"
    }
    return (Resolve-Path -LiteralPath $Value).Path
}

function Get-FirstExistingFile {
    param([string[]]$Candidates)
    foreach ($candidate in $Candidates) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }
    return ""
}

function Find-Vsix {
    param([string]$Root)
    $candidates = @(
        (Join-Path $Root "theseus-vscode-0.0.1.vsix"),
        (Join-Path $Root "vscode-extension\theseus-vscode-0.0.1.vsix"),
        (Join-Path $Root "backend\theseus-core-server\vscode-extension\theseus-vscode-0.0.1.vsix")
    )
    $found = Get-FirstExistingFile -Candidates $candidates
    if (-not [string]::IsNullOrWhiteSpace($found)) {
        return $found
    }
    $vsix = Get-ChildItem -LiteralPath $Root -Filter "theseus-vscode-*.vsix" -Recurse -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    if ($vsix) {
        return $vsix.FullName
    }
    return ""
}

function Find-Runner {
    param([string]$Root)
    $candidates = @(
        (Join-Path $Root "theseus-runner\theseus-runner.exe"),
        (Join-Path $Root "dist\theseus-runner\theseus-runner\theseus-runner.exe"),
        (Join-Path $Root "backend\theseus-core-server\dist\theseus-runner\theseus-runner\theseus-runner.exe")
    )
    $found = Get-FirstExistingFile -Candidates $candidates
    if (-not [string]::IsNullOrWhiteSpace($found)) {
        return $found
    }
    $runner = Get-ChildItem -LiteralPath $Root -Filter "theseus-runner.exe" -Recurse -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    if ($runner) {
        return $runner.FullName
    }
    return ""
}

function Get-CommandSource {
    param([string[]]$Names)
    foreach ($name in $Names) {
        $command = Get-Command $name -ErrorAction SilentlyContinue
        if ($command) {
            if ($command.Source) {
                return $command.Source
            }
            return $command.Definition
        }
    }
    return ""
}

function Resolve-IdeTarget {
    param([string]$Target)
    if ($Target -ne "auto") {
        return $Target
    }
    $processes = Get-Process -Name Antigravity,Code -ErrorAction SilentlyContinue
    if ($processes) {
        $latest = $processes |
            Sort-Object {
                try { $_.StartTime } catch { [datetime]::MinValue }
            } -Descending |
            Select-Object -First 1
        if ($latest.ProcessName -ieq "Antigravity") {
            return "antigravity"
        }
        if ($latest.ProcessName -ieq "Code") {
            return "vscode"
        }
    }
    if (Get-CommandSource -Names @("antigravity.cmd", "antigravity")) {
        return "antigravity"
    }
    return "vscode"
}

function Resolve-IdeCli {
    param(
        [string]$Target,
        [string]$ExplicitCode
    )
    if (-not [string]::IsNullOrWhiteSpace($ExplicitCode)) {
        return $ExplicitCode
    }
    if ($Target -eq "antigravity") {
        return Get-CommandSource -Names @("antigravity.cmd", "antigravity")
    }
    return Get-CommandSource -Names @("code.cmd", "code")
}

function Get-HomePath {
    if (-not [string]::IsNullOrWhiteSpace($env:USERPROFILE)) {
        return $env:USERPROFILE
    }
    return (Resolve-Path "~").Path
}

function Get-ExtensionsPath {
    param([string]$Target)
    $home = Get-HomePath
    if ($Target -eq "antigravity") {
        return Join-Path $home ".antigravity\extensions"
    }
    return Join-Path $home ".vscode\extensions"
}

function Get-SettingsPath {
    param(
        [string]$Target,
        [string]$Workspace
    )
    if ($Target -eq "antigravity") {
        if ([string]::IsNullOrWhiteSpace($env:APPDATA)) {
            throw "APPDATA is not set; cannot resolve Antigravity settings path."
        }
        return Join-Path $env:APPDATA "Antigravity\User\settings.json"
    }
    return Join-Path (Join-Path $Workspace ".vscode") "settings.json"
}

function ConvertTo-Hashtable {
    param([object]$InputObject)
    $result = [ordered]@{}
    if ($null -eq $InputObject) {
        return $result
    }
    foreach ($property in $InputObject.PSObject.Properties) {
        $result[$property.Name] = $property.Value
    }
    return $result
}

function Read-Settings {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        return [ordered]@{}
    }
    $raw = Get-Content -LiteralPath $Path -Raw -Encoding UTF8
    if ([string]::IsNullOrWhiteSpace($raw)) {
        return [ordered]@{}
    }
    try {
        return ConvertTo-Hashtable ($raw | ConvertFrom-Json)
    }
    catch {
        $stamp = Get-Date -Format "yyyyMMddHHmmss"
        $backupPath = "$Path.bak-$stamp"
        Copy-Item -LiteralPath $Path -Destination $backupPath -Force
        Write-Warning "Existing settings.json is not strict JSON. Backed up to $backupPath."
        return [ordered]@{}
    }
}

if ($Help) {
    Show-Usage
    exit 0
}

if ([string]::IsNullOrWhiteSpace($PackagePath)) {
    $PackagePath = Split-Path -Parent $MyInvocation.MyCommand.Path
}
$PackagePath = (Resolve-Path -LiteralPath $PackagePath).Path

$VsixPath = if ([string]::IsNullOrWhiteSpace($VsixPath)) {
    Find-Vsix -Root $PackagePath
} else {
    Resolve-OptionalPath -Value $VsixPath -Label "VSIX"
}
if ([string]::IsNullOrWhiteSpace($VsixPath)) {
    throw "Theseus VSIX was not found under package path: $PackagePath"
}

$RunnerPath = if ([string]::IsNullOrWhiteSpace($RunnerPath)) {
    Find-Runner -Root $PackagePath
} else {
    Resolve-OptionalPath -Value $RunnerPath -Label "Runner"
}
if ([string]::IsNullOrWhiteSpace($RunnerPath)) {
    throw "theseus-runner.exe was not found. Put the built theseus-runner folder next to this installer."
}

if ([string]::IsNullOrWhiteSpace($WorkspacePath)) {
    $defaultWorkspace = $PackagePath
    $answer = Read-Host "Workspace/project path to open [default: $defaultWorkspace]"
    $WorkspacePath = if ([string]::IsNullOrWhiteSpace($answer)) { $defaultWorkspace } else { $answer }
}
$WorkspacePath = Resolve-OptionalPath -Value $WorkspacePath -Label "Workspace"

$DetectedIde = Resolve-IdeTarget -Target $Ide
$Code = Resolve-IdeCli -Target $DetectedIde -ExplicitCode $Code
if ([string]::IsNullOrWhiteSpace($Code)) {
    throw "IDE CLI was not found for target: $DetectedIde. Use -Code to specify the CLI path."
}

$extensionsPath = Get-ExtensionsPath -Target $DetectedIde
New-Item -ItemType Directory -Path $extensionsPath -Force | Out-Null

Write-Host "Installing Theseus test package..."
Write-Host "IDE: $DetectedIde ($Code)"
Write-Host "VSIX: $VsixPath"
Write-Host "RunnerPath: $RunnerPath"
Write-Host "WorkspacePath: $WorkspacePath"
Write-Host "ExtensionsDir: $extensionsPath"

& $Code --extensions-dir $extensionsPath --install-extension $VsixPath --force
if ($LASTEXITCODE -ne 0) {
    throw "VSIX install failed with exit code $LASTEXITCODE"
}

$settingsPath = Get-SettingsPath -Target $DetectedIde -Workspace $WorkspacePath
$settingsDir = Split-Path -Parent $settingsPath
New-Item -ItemType Directory -Path $settingsDir -Force | Out-Null
$settings = Read-Settings -Path $settingsPath
$settings["theseus.runtimeMode"] = "bundled-runner"
$settings["theseus.runnerPath"] = $RunnerPath
$settings["theseus.workspacePath"] = $WorkspacePath
if (-not $settings.Contains("theseus.serverUrl")) {
    $settings["theseus.serverUrl"] = ""
}
$existingCorePath = ""
if ($settings.Contains("theseus.corePath") -and $null -ne $settings["theseus.corePath"]) {
    $existingCorePath = [string]$settings["theseus.corePath"]
}
if ($existingCorePath -and -not (Test-Path -LiteralPath (Join-Path $existingCorePath "theseus_engine"))) {
    $settings["theseus.corePath"] = ""
}

$settings |
    ConvertTo-Json -Depth 32 |
    Set-Content -LiteralPath $settingsPath -Encoding UTF8

Write-Host "SettingsPath: $settingsPath"

if (-not $NoLaunch) {
    Write-Host "Opening workspace..."
    & $Code $WorkspacePath
}

Write-Host "Done. Open the Theseus sidebar and run 'Theseus: Start Agent'."
