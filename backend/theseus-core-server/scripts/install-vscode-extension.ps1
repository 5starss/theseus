[CmdletBinding()]
param(
    [string]$CorePath = "",
    [string]$WorkspacePath = "",
    [string]$Python = "python",
    [string]$Code = "code",
    [string]$VsixPath = "",
    [switch]$SkipRequirements,
    [switch]$SkipExtension,
    [switch]$SkipSettings,
    [switch]$InstallPlaywright
)

$ErrorActionPreference = "Stop"

function Resolve-ExistingPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PathValue,
        [Parameter(Mandatory = $true)]
        [string]$Label
    )

    if (-not (Test-Path -LiteralPath $PathValue)) {
        throw "$Label path does not exist: $PathValue"
    }

    return (Resolve-Path -LiteralPath $PathValue).Path
}

function ConvertTo-Hashtable {
    param([object]$InputObject)

    $result = [ordered]@{}
    if ($null -eq $InputObject) {
        return $result
    }

    if ($InputObject -is [System.Collections.IDictionary]) {
        foreach ($key in $InputObject.Keys) {
            $result[$key] = $InputObject[$key]
        }
        return $result
    }

    foreach ($property in $InputObject.PSObject.Properties) {
        $result[$property.Name] = $property.Value
    }
    return $result
}

function Read-VSCodeSettings {
    param([string]$SettingsPath)

    if (-not (Test-Path -LiteralPath $SettingsPath)) {
        return [ordered]@{}
    }

    $raw = Get-Content -LiteralPath $SettingsPath -Raw -Encoding UTF8
    if ([string]::IsNullOrWhiteSpace($raw)) {
        return [ordered]@{}
    }

    try {
        return ConvertTo-Hashtable ($raw | ConvertFrom-Json)
    }
    catch {
        $stamp = Get-Date -Format "yyyyMMddHHmmss"
        $backupPath = "$SettingsPath.bak-$stamp"
        Copy-Item -LiteralPath $SettingsPath -Destination $backupPath -Force
        Write-Warning "Existing settings.json is not strict JSON. Backed up to $backupPath and writing fresh settings."
        return [ordered]@{}
    }
}

function Get-VenvPython {
    param([string]$VenvPath)

    $windowsPython = Join-Path $VenvPath "Scripts\python.exe"
    if (Test-Path -LiteralPath $windowsPython) {
        return $windowsPython
    }

    $posixPython = Join-Path $VenvPath "bin/python"
    if (Test-Path -LiteralPath $posixPython) {
        return $posixPython
    }

    throw "Python executable was not found in venv: $VenvPath"
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$defaultCorePath = Join-Path $scriptDir ".."

if ([string]::IsNullOrWhiteSpace($CorePath)) {
    $CorePath = $defaultCorePath
}
$CorePath = Resolve-ExistingPath -PathValue $CorePath -Label "Core"

if ([string]::IsNullOrWhiteSpace($WorkspacePath)) {
    $WorkspacePath = Join-Path $CorePath "..\.."
}
$WorkspacePath = Resolve-ExistingPath -PathValue $WorkspacePath -Label "Workspace"

$requirementsPath = Join-Path $CorePath "requirements.txt"
if (-not (Test-Path -LiteralPath $requirementsPath)) {
    throw "requirements.txt was not found: $requirementsPath"
}

$venvPath = Join-Path $CorePath ".venv"
if (-not (Test-Path -LiteralPath $venvPath)) {
    $uv = Get-Command uv -ErrorAction SilentlyContinue
    if ($uv) {
        & $uv.Source venv --python 3.11 $venvPath
    }
    else {
        & $Python -m venv $venvPath
    }
}

$venvPython = Get-VenvPython -VenvPath $venvPath

if (-not $SkipRequirements) {
    $uv = Get-Command uv -ErrorAction SilentlyContinue
    if ($uv) {
        & $uv.Source pip install -r $requirementsPath --python $venvPython
    }
    else {
        & $venvPython -m pip install --upgrade pip
        & $venvPython -m pip install -r $requirementsPath
    }
}

if ($InstallPlaywright) {
    & $venvPython -m playwright install chromium
}

if (-not $SkipExtension) {
    if ([string]::IsNullOrWhiteSpace($VsixPath)) {
        $extensionDir = Join-Path $CorePath "vscode-extension"
        $vsix = Get-ChildItem -LiteralPath $extensionDir -Filter "*.vsix" |
            Sort-Object LastWriteTime -Descending |
            Select-Object -First 1
        if (-not $vsix) {
            throw "VSIX package was not found in $extensionDir"
        }
        $VsixPath = $vsix.FullName
    }
    else {
        $VsixPath = Resolve-ExistingPath -PathValue $VsixPath -Label "VSIX"
    }

    if (-not (Get-Command $Code -ErrorAction SilentlyContinue)) {
        throw "VSCode CLI was not found: $Code"
    }
    & $Code --install-extension $VsixPath --force
}

if (-not $SkipSettings) {
    $vscodeDir = Join-Path $WorkspacePath ".vscode"
    New-Item -ItemType Directory -Path $vscodeDir -Force | Out-Null

    $settingsPath = Join-Path $vscodeDir "settings.json"
    $settings = Read-VSCodeSettings -SettingsPath $settingsPath
    $settings["theseus.corePath"] = $CorePath
    $settings["theseus.pythonPath"] = (Resolve-Path -LiteralPath $venvPython).Path
    $settings["theseus.workspacePath"] = $WorkspacePath
    if (-not $settings.Contains("theseus.serverUrl")) {
        $settings["theseus.serverUrl"] = ""
    }

    $settings |
        ConvertTo-Json -Depth 32 |
        Set-Content -LiteralPath $settingsPath -Encoding UTF8
}

Write-Host "Theseus VSCode extension setup complete."
Write-Host "CorePath: $CorePath"
Write-Host "PythonPath: $venvPython"
Write-Host "WorkspacePath: $WorkspacePath"
