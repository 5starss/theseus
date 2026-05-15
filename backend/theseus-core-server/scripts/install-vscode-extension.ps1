[CmdletBinding()]
param(
    [string]$CorePath = "",
    [string]$WorkspacePath = "",
    [string]$Python = "python",
    [ValidateSet("auto", "vscode", "code", "antigravity")]
    [string]$Ide = "auto",
    [string]$Code = "",
    [string]$SettingsDir = "",
    [string]$ExtensionsDir = "",
    [string]$VsixPath = "",
    [string]$RunnerPath = "",
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

function ConvertTo-AbsoluteSettingPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$PathValue,
        [Parameter(Mandatory = $true)]
        [string]$WorkspaceRoot
    )

    return (Resolve-Path -LiteralPath $PathValue).Path
}

function ConvertTo-JsonLiteral {
    param([object]$Value)
    return ConvertTo-Json -InputObject $Value -Compress
}

function Set-TheseusSettings {
    param(
        [Parameter(Mandatory = $true)]
        [string]$SettingsPath,
        [Parameter(Mandatory = $true)]
        [System.Collections.IDictionary]$Values
    )

    $settingsDirPath = Split-Path -Parent $SettingsPath
    New-Item -ItemType Directory -Path $settingsDirPath -Force | Out-Null

    if (Test-Path -LiteralPath $SettingsPath) {
        $raw = Get-Content -LiteralPath $SettingsPath -Raw -Encoding UTF8
    }
    else {
        $raw = "{`n}`n"
    }

    if ([string]::IsNullOrWhiteSpace($raw) -or -not $raw.TrimStart().StartsWith("{")) {
        if (Test-Path -LiteralPath $SettingsPath) {
            $stamp = Get-Date -Format "yyyyMMddHHmmss"
            Copy-Item -LiteralPath $SettingsPath -Destination "$SettingsPath.bak-$stamp" -Force
            Write-Warning "Existing settings file was not JSON/JSONC-like. Backed up and writing fresh settings."
        }
        $raw = "{`n}`n"
    }

    $lines = @($raw -split "\r?\n")
    $lines = @(
        $lines | Where-Object {
            $_ -notmatch '^\s*"theseus\.[^"]+"\s*:'
        }
    )

    if (-not $lines.Count) {
        $lines = @("{", "}")
    }

    $closingIndex = -1
    for ($i = $lines.Count - 1; $i -ge 0; $i--) {
        if ($lines[$i] -match '^\s*}\s*,?\s*$') {
            $closingIndex = $i
            break
        }
    }
    if ($closingIndex -lt 0) {
        $lines += "}"
        $closingIndex = $lines.Count - 1
    }

    $previousIndex = $closingIndex - 1
    while ($previousIndex -ge 0) {
        $trimmed = $lines[$previousIndex].Trim()
        if ($trimmed -and -not $trimmed.StartsWith("//")) {
            break
        }
        $previousIndex--
    }
    if ($previousIndex -ge 0) {
        $previous = $lines[$previousIndex].Trim()
        if ($previous -and $previous -ne "{" -and -not $previous.EndsWith(",")) {
            $lines[$previousIndex] = $lines[$previousIndex] + ","
        }
    }

    $insertLines = @()
    foreach ($entry in $Values.GetEnumerator()) {
        $insertLines += "    `"$($entry.Key)`": $(ConvertTo-JsonLiteral -Value $entry.Value),"
    }

    $before = @()
    if ($closingIndex -gt 0) {
        $before = @($lines[0..($closingIndex - 1)])
    }
    $after = @($lines[$closingIndex..($lines.Count - 1)])
    $updated = @()
    $updated += $before
    $updated += $insertLines
    $updated += $after
    $newline = [Environment]::NewLine
    Set-Content -LiteralPath $SettingsPath -Value ($updated -join $newline) -Encoding UTF8
}

function Clear-TheseusSettings {
    param([string]$SettingsPath)

    if (-not (Test-Path -LiteralPath $SettingsPath)) {
        return
    }

    $raw = Get-Content -LiteralPath $SettingsPath -Raw -Encoding UTF8
    $lines = @($raw -split "\r?\n")
    $kept = @(
        $lines | Where-Object {
            $_ -notmatch '^\s*"theseus\.[^"]+"\s*:'
        }
    )
    if ($kept.Count -eq $lines.Count) {
        return
    }

    $newline = [Environment]::NewLine
    Set-Content -LiteralPath $SettingsPath -Value ($kept -join $newline) -Encoding UTF8
    Write-Host "Removed stale workspace Theseus settings: $SettingsPath"
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

function Remove-SafeChildPath {
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
        throw "Refusing to remove outside extension directory: $resolvedPath"
    }

    Remove-Item -LiteralPath $resolvedPath -Recurse -Force
    Write-Host "Removed stale Theseus extension path: $resolvedPath"
}

function Clear-TheseusExtensionInstallState {
    param([string]$ExtensionsRoot)

    if ([string]::IsNullOrWhiteSpace($ExtensionsRoot)) {
        return
    }

    New-Item -ItemType Directory -Path $ExtensionsRoot -Force | Out-Null
    $resolvedRoot = (Resolve-Path -LiteralPath $ExtensionsRoot).Path

    Get-ChildItem -LiteralPath $resolvedRoot -Filter "theseus.theseus-vscode*" -Force -ErrorAction SilentlyContinue |
        ForEach-Object {
            Remove-SafeChildPath -Path $_.FullName -AllowedRoot $resolvedRoot
        }

    $extensionsJson = Join-Path $resolvedRoot "extensions.json"
    if (Test-Path -LiteralPath $extensionsJson) {
        try {
            $items = @(Get-Content -LiteralPath $extensionsJson -Raw -Encoding UTF8 | ConvertFrom-Json)
        }
        catch {
            Write-Warning "Skipping unreadable extensions.json: $extensionsJson"
            $items = $null
        }

        if ($null -ne $items) {
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

            if ($kept.Count -ne $items.Count) {
                ConvertTo-Json -InputObject $kept -Depth 100 -Compress |
                    Set-Content -LiteralPath $extensionsJson -Encoding UTF8
                Write-Host "Removed stale Theseus entry from extensions.json: $($items.Count - $kept.Count)"
            }
        }
    }

    $obsoletePath = Join-Path $resolvedRoot ".obsolete"
    if (Test-Path -LiteralPath $obsoletePath) {
        try {
            $obsolete = Get-Content -LiteralPath $obsoletePath -Raw -Encoding UTF8 | ConvertFrom-Json
        }
        catch {
            Write-Warning "Skipping unreadable .obsolete: $obsoletePath"
            $obsolete = $null
        }

        if ($null -ne $obsolete) {
            $removed = @()
            foreach ($property in @($obsolete.PSObject.Properties.Name)) {
                if ($property -like "theseus.theseus-vscode*") {
                    $removed += $property
                    $obsolete.PSObject.Properties.Remove($property)
                }
            }

            if ($removed.Count) {
                $obsolete | ConvertTo-Json -Depth 32 -Compress |
                    Set-Content -LiteralPath $obsoletePath -Encoding UTF8
                Write-Host "Removed stale Theseus .obsolete entries: $($removed.Count)"
            }
        }
    }
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

    return $null
}

function Get-IdeFromEnvironment {
    $hints = @(
        $env:TERM_PROGRAM,
        $env:VSCODE_CWD,
        $env:VSCODE_GIT_ASKPASS_NODE,
        $env:VSCODE_GIT_ASKPASS_MAIN,
        $env:VSCODE_IPC_HOOK_CLI,
        $env:ANTIGRAVITY_BIN
    ) -join " "
    $hints = $hints.ToLowerInvariant()

    if ($hints.Contains("antigravity")) {
        return "antigravity"
    }
    if ($hints.Contains("microsoft vs code") -or $hints.Contains("code.exe")) {
        return "vscode"
    }
    if ($env:TERM_PROGRAM -and $env:TERM_PROGRAM.ToLowerInvariant() -eq "vscode") {
        return "vscode"
    }

    return $null
}

function Get-IdeFromProcesses {
    $processes = Get-Process -Name Antigravity,Code -ErrorAction SilentlyContinue
    if (-not $processes) {
        return $null
    }

    $latest = $processes |
        Sort-Object {
            try {
                $_.StartTime
            }
            catch {
                [datetime]::MinValue
            }
        } -Descending |
        Select-Object -First 1

    if (-not $latest) {
        return $null
    }
    if ($latest.ProcessName -ieq "Antigravity") {
        return "antigravity"
    }
    if ($latest.ProcessName -ieq "Code") {
        return "vscode"
    }

    return $null
}

function Get-IdeFromCode {
    param([string]$CodeValue)

    $normalized = $CodeValue.ToLowerInvariant()
    if ($normalized.Contains("antigravity")) {
        return "antigravity"
    }
    if ($normalized.Contains("code")) {
        return "vscode"
    }

    return "custom"
}

function Resolve-IdeTarget {
    param(
        [string]$IdeTarget,
        [string]$ExplicitCode
    )

    if (-not [string]::IsNullOrWhiteSpace($ExplicitCode)) {
        return Get-IdeFromCode -CodeValue $ExplicitCode
    }

    $target = $IdeTarget.ToLowerInvariant()
    if ($target -eq "auto") {
        $target = Get-IdeFromEnvironment
        if ([string]::IsNullOrWhiteSpace($target)) {
            $target = Get-IdeFromProcesses
        }
        if ([string]::IsNullOrWhiteSpace($target)) {
            $target = "vscode"
        }
    }
    elseif ($target -eq "code") {
        $target = "vscode"
    }

    return $target
}

function Get-SettingsDirectoryName {
    param(
        [string]$IdeTarget,
        [string]$Override
    )

    if (-not [string]::IsNullOrWhiteSpace($Override)) {
        return $Override
    }

    if ($IdeTarget -eq "antigravity") {
        return ".antigravity"
    }

    return ".vscode"
}

function Get-UserSettingsPath {
    param([string]$IdeTarget)

    if ($IdeTarget -eq "antigravity") {
        if ([string]::IsNullOrWhiteSpace($env:APPDATA)) {
            throw "APPDATA is not set; cannot resolve Antigravity user settings path."
        }
        return Join-Path $env:APPDATA "Antigravity\User\settings.json"
    }
    if ($IdeTarget -eq "vscode") {
        if ([string]::IsNullOrWhiteSpace($env:APPDATA)) {
            throw "APPDATA is not set; cannot resolve VSCode user settings path."
        }
        return Join-Path $env:APPDATA "Code\User\settings.json"
    }

    return $null
}

function Get-HomePath {
    if (-not [string]::IsNullOrWhiteSpace($env:USERPROFILE)) {
        return $env:USERPROFILE
    }
    if (-not [string]::IsNullOrWhiteSpace($HOME)) {
        return $HOME
    }

    return (Resolve-Path "~").Path
}

function Get-DefaultExtensionsPath {
    param([string]$IdeTarget)

    $homePath = Get-HomePath
    if ($IdeTarget -eq "antigravity") {
        return Join-Path $homePath ".antigravity\extensions"
    }
    if ($IdeTarget -eq "vscode") {
        return Join-Path $homePath ".vscode\extensions"
    }

    return $null
}

function Get-ExtensionsPath {
    param(
        [string]$IdeTarget,
        [string]$Override
    )

    if (-not [string]::IsNullOrWhiteSpace($Override)) {
        if ([System.IO.Path]::IsPathRooted($Override)) {
            return $Override
        }
        return Join-Path (Get-Location).Path $Override
    }

    return Get-DefaultExtensionsPath -IdeTarget $IdeTarget
}

function Get-SettingsPath {
    param(
        [string]$IdeTarget,
        [string]$WorkspaceRoot,
        [string]$SettingsDirOverride
    )

    if (-not [string]::IsNullOrWhiteSpace($SettingsDirOverride)) {
        $settingsDirPath = Join-Path $WorkspaceRoot $SettingsDirOverride
        return Join-Path $settingsDirPath "settings.json"
    }

    $userSettings = Get-UserSettingsPath -IdeTarget $IdeTarget
    if (-not [string]::IsNullOrWhiteSpace($userSettings)) {
        return $userSettings
    }

    $settingsDirName = Get-SettingsDirectoryName -IdeTarget $IdeTarget -Override $SettingsDirOverride
    $settingsDirPath = Join-Path $WorkspaceRoot $settingsDirName
    return Join-Path $settingsDirPath "settings.json"
}

function Resolve-IdeCli {
    param(
        [string]$IdeTarget,
        [string]$ExplicitCode
    )

    if (-not [string]::IsNullOrWhiteSpace($ExplicitCode)) {
        $script:DetectedIde = Get-IdeFromCode -CodeValue $ExplicitCode
        return $ExplicitCode
    }

    $target = Resolve-IdeTarget -IdeTarget $IdeTarget -ExplicitCode $ExplicitCode

    if ($target -eq "antigravity") {
        $cli = Get-CommandSource -Names @("antigravity.cmd", "antigravity")
    }
    elseif ($target -eq "vscode") {
        $cli = Get-CommandSource -Names @("code.cmd", "code")
    }
    else {
        throw "Unsupported IDE target: $IdeTarget"
    }

    if ([string]::IsNullOrWhiteSpace($cli)) {
        throw "IDE CLI was not found for target: $target. Use -Code to specify the editor CLI explicitly."
    }

    $script:DetectedIde = $target
    return $cli
}

function Invoke-IdeInstallExtension {
    param(
        [Parameter(Mandatory = $true)]
        [string]$CodePath,
        [Parameter(Mandatory = $true)]
        [string]$VsixFile,
        [string]$ExtensionDirectory = ""
    )

    $installArgs = @()
    if (-not [string]::IsNullOrWhiteSpace($ExtensionDirectory)) {
        $installArgs += "--extensions-dir"
        $installArgs += $ExtensionDirectory
    }
    $installArgs += "--install-extension"
    $installArgs += $VsixFile
    $installArgs += "--force"

    & $CodePath @installArgs
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) {
        throw (
            "VSIX install failed (exit code $exitCode). " +
            "Close all VS Code windows, run Uninstall-Theseus-VSCode.cmd if stale metadata remains, then retry."
        )
    }
}

$DetectedIde = ""
$extensionInstallDir = ""
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
$browserRequirementsPath = Join-Path $CorePath "requirements-browser.txt"

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

if (-not $SkipSettings -or -not $SkipExtension) {
    $DetectedIde = Resolve-IdeTarget -IdeTarget $Ide -ExplicitCode $Code
}

if (-not $SkipSettings) {
    $resolvedRunnerPath = ""
    if (-not [string]::IsNullOrWhiteSpace($RunnerPath)) {
        $resolvedRunnerPath = Resolve-ExistingPath -PathValue $RunnerPath -Label "Runner"
    }

    $settingsPath = Get-SettingsPath `
        -IdeTarget $DetectedIde `
        -WorkspaceRoot $WorkspacePath `
        -SettingsDirOverride $SettingsDir

    $settings = [ordered]@{}
    $settings["theseus.corePath"] = ConvertTo-AbsoluteSettingPath -PathValue $CorePath -WorkspaceRoot $WorkspacePath
    $settings["theseus.pythonPath"] = ConvertTo-AbsoluteSettingPath -PathValue (Resolve-Path -LiteralPath $venvPython).Path -WorkspaceRoot $WorkspacePath
    $settings["theseus.workspacePath"] = ConvertTo-AbsoluteSettingPath -PathValue $WorkspacePath -WorkspaceRoot $WorkspacePath
    if (-not [string]::IsNullOrWhiteSpace($resolvedRunnerPath)) {
        $settings["theseus.runnerPath"] = ConvertTo-AbsoluteSettingPath -PathValue $resolvedRunnerPath -WorkspaceRoot $WorkspacePath
        $settings["theseus.runtimeMode"] = "bundled-runner"
    }
    if (-not $settings.Contains("theseus.serverUrl")) {
        $settings["theseus.serverUrl"] = ""
    }
    Set-TheseusSettings -SettingsPath $settingsPath -Values $settings

    if ([string]::IsNullOrWhiteSpace($SettingsDir)) {
        $workspaceSettingsPath = Join-Path (Join-Path $WorkspacePath ".vscode") "settings.json"
        if ($workspaceSettingsPath -ne $settingsPath) {
            Clear-TheseusSettings -SettingsPath $workspaceSettingsPath
        }
    }
}

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
    if (Test-Path -LiteralPath $browserRequirementsPath) {
        & $venvPython -m pip install -r $browserRequirementsPath
    }
    else {
        & $venvPython -m pip install playwright
    }
    & $venvPython -m playwright install chromium
}

if (-not $SkipExtension) {
    $Code = Resolve-IdeCli -IdeTarget $Ide -ExplicitCode $Code

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

    if (
        -not (Get-Command $Code -ErrorAction SilentlyContinue) -and
        -not (Test-Path -LiteralPath $Code)
    ) {
        throw "IDE CLI was not found: $Code"
    }

    $extensionInstallDir = Get-ExtensionsPath -IdeTarget $DetectedIde -Override $ExtensionsDir
    if (-not [string]::IsNullOrWhiteSpace($extensionInstallDir)) {
        New-Item -ItemType Directory -Path $extensionInstallDir -Force | Out-Null
        Clear-TheseusExtensionInstallState -ExtensionsRoot $extensionInstallDir
        Write-Host "Installing VSIX into IDE target: $DetectedIde ($Code)"
        Write-Host "ExtensionsDir: $extensionInstallDir"
        Invoke-IdeInstallExtension `
            -CodePath $Code `
            -VsixFile $VsixPath `
            -ExtensionDirectory $extensionInstallDir
    }
    else {
        Write-Host "Installing VSIX into IDE target: $DetectedIde ($Code)"
        Invoke-IdeInstallExtension `
            -CodePath $Code `
            -VsixFile $VsixPath
    }
}

Write-Host "Theseus VSCode extension setup complete."
if (-not [string]::IsNullOrWhiteSpace($DetectedIde)) {
    Write-Host "IDE: $DetectedIde ($Code)"
}
if (-not $SkipSettings) {
    Write-Host "SettingsPath: $settingsPath"
}
if (-not [string]::IsNullOrWhiteSpace($extensionInstallDir)) {
    Write-Host "ExtensionsDir: $extensionInstallDir"
}
Write-Host "CorePath: $CorePath"
Write-Host "PythonPath: $venvPython"
if (-not [string]::IsNullOrWhiteSpace($resolvedRunnerPath)) {
    Write-Host "RunnerPath: $resolvedRunnerPath"
}
Write-Host "WorkspacePath: $WorkspacePath"
