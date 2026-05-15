[CmdletBinding()]
param(
    [string]$CorePath = "",
    [string]$VsixPath = "",
    [string]$RunnerPath = "",
    [string]$OutputDir = "",
    [string]$PackageName = "Theseus-TestPackage",
    [switch]$BuildVsix,
    [switch]$BuildRunner,
    [switch]$InstallPyInstaller,
    [switch]$NoZip,
    [switch]$Help
)

$ErrorActionPreference = "Stop"
$ScriptRoot = if ([string]::IsNullOrWhiteSpace($PSScriptRoot)) {
    Split-Path -Parent $MyInvocation.MyCommand.Path
}
else {
    $PSScriptRoot
}

function Show-Usage {
    Write-Host "Usage:"
    Write-Host "  powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\package-test-distribution.ps1 [options]"
    Write-Host ""
    Write-Host "Options:"
    Write-Host "  -BuildVsix             Run npm compile and npx @vscode/vsce package before staging"
    Write-Host "  -BuildRunner           Run scripts\build-runner-binary.ps1 before staging"
    Write-Host "  -InstallPyInstaller    Pass -InstallPyInstaller to the runner build script"
    Write-Host "  -VsixPath PATH         Explicit VSIX file to include"
    Write-Host "  -RunnerPath PATH       Explicit theseus-runner.exe file to include"
    Write-Host "  -OutputDir PATH        Output directory. Defaults to <core>\dist\test-package"
    Write-Host "  -PackageName NAME      Staged folder and zip basename. Defaults to Theseus-TestPackage"
    Write-Host "  -NoZip                 Create the folder only, without Compress-Archive"
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

function Resolve-ExistingFile {
    param(
        [string]$Path,
        [string]$Label
    )

    if ([string]::IsNullOrWhiteSpace($Path)) {
        return ""
    }
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "$Label does not exist: $Path"
    }
    return (Resolve-Path -LiteralPath $Path).Path
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

function Invoke-Checked {
    param(
        [scriptblock]$Command,
        [string]$Label
    )

    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$Label failed with exit code $LASTEXITCODE"
    }
}

function Find-LatestVsix {
    param([string]$CoreRoot)

    $extensionDir = Join-Path $CoreRoot "vscode-extension"
    if (-not (Test-Path -LiteralPath $extensionDir)) {
        return ""
    }
    $vsix = Get-ChildItem -LiteralPath $extensionDir -Filter "theseus-vscode-*.vsix" -File -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    if ($vsix) {
        return $vsix.FullName
    }
    return ""
}

function Find-RunnerBinary {
    param([string]$CoreRoot)

    $candidates = @(
        (Join-Path $CoreRoot "dist\theseus-runner\theseus-runner\theseus-runner.exe"),
        (Join-Path $CoreRoot "dist\theseus-runner\theseus-runner.exe")
    )
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }

    $runnerRoot = Join-Path $CoreRoot "dist\theseus-runner"
    if (-not (Test-Path -LiteralPath $runnerRoot)) {
        return ""
    }
    $runner = Get-ChildItem -LiteralPath $runnerRoot -Filter "theseus-runner.exe" -File -Recurse -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    if ($runner) {
        return $runner.FullName
    }
    return ""
}

function Assert-WithinPath {
    param(
        [string]$Child,
        [string]$Parent,
        [string]$Label
    )

    $childFull = [System.IO.Path]::GetFullPath($Child).TrimEnd(
        [System.IO.Path]::DirectorySeparatorChar,
        [System.IO.Path]::AltDirectorySeparatorChar
    )
    $parentFull = [System.IO.Path]::GetFullPath($Parent).TrimEnd(
        [System.IO.Path]::DirectorySeparatorChar,
        [System.IO.Path]::AltDirectorySeparatorChar
    )
    $parentPrefix = $parentFull + [System.IO.Path]::DirectorySeparatorChar
    if (-not (
        $childFull.Equals($parentFull, [System.StringComparison]::OrdinalIgnoreCase) -or
        $childFull.StartsWith($parentPrefix, [System.StringComparison]::OrdinalIgnoreCase)
    )) {
        throw "$Label is outside the expected output directory: $childFull"
    }
}

function Resolve-RepoRoot {
    param([string]$CoreRoot)

    $candidate = Join-Path $CoreRoot "..\.."
    $candidate = (Resolve-Path -LiteralPath $candidate).Path
    if (Test-Path -LiteralPath (Join-Path $candidate "Install-Theseus-TestPackage.cmd") -PathType Leaf) {
        return $candidate
    }
    throw "Install-Theseus-TestPackage.cmd was not found above CorePath: $CoreRoot"
}

function Copy-RunnerPayload {
    param(
        [string]$RunnerExe,
        [string]$Destination
    )

    New-Item -ItemType Directory -Path $Destination -Force | Out-Null
    $runnerDir = Split-Path -Parent $RunnerExe
    $internalDir = Join-Path $runnerDir "_internal"
    if (Test-Path -LiteralPath $internalDir -PathType Container) {
        Get-ChildItem -LiteralPath $runnerDir -Force |
            Copy-Item -Destination $Destination -Recurse -Force
        return
    }

    Copy-Item -LiteralPath $RunnerExe -Destination (Join-Path $Destination "theseus-runner.exe") -Force
}

if ($Help) {
    Show-Usage
    exit 0
}

$CorePath = Resolve-CorePath -Value $CorePath
$repoRoot = Resolve-RepoRoot -CoreRoot $CorePath
$extensionDir = Join-Path $CorePath "vscode-extension"

if ([string]::IsNullOrWhiteSpace($OutputDir)) {
    $OutputDir = Join-Path $CorePath "dist\test-package"
}
$OutputDir = [System.IO.Path]::GetFullPath($OutputDir)
New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null

if ($BuildRunner) {
    $runnerBuildScript = Join-Path $CorePath "scripts\build-runner-binary.ps1"
    if (-not (Test-Path -LiteralPath $runnerBuildScript -PathType Leaf)) {
        throw "Runner build script was not found: $runnerBuildScript"
    }
    $runnerBuildArgs = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $runnerBuildScript, "-CorePath", $CorePath)
    if ($InstallPyInstaller) {
        $runnerBuildArgs += "-InstallPyInstaller"
    }
    Write-Host "Building theseus-runner..."
    Invoke-Checked -Label "Runner build" -Command {
        & powershell @runnerBuildArgs
    }
}

if ($BuildVsix) {
    if (-not (Test-Path -LiteralPath $extensionDir -PathType Container)) {
        throw "VSCode extension directory was not found: $extensionDir"
    }
    $npm = Get-CommandSource -Names @("npm.cmd", "npm")
    $npx = Get-CommandSource -Names @("npx.cmd", "npx")
    if ([string]::IsNullOrWhiteSpace($npm)) {
        throw "npm was not found on PATH."
    }
    if ([string]::IsNullOrWhiteSpace($npx)) {
        throw "npx was not found on PATH."
    }
    Push-Location $extensionDir
    try {
        Write-Host "Compiling VSCode extension..."
        Invoke-Checked -Label "npm run compile" -Command {
            & $npm run compile
        }
        Write-Host "Packaging VSIX..."
        Invoke-Checked -Label "npx @vscode/vsce package" -Command {
            & $npx "@vscode/vsce" package
        }
    }
    finally {
        Pop-Location
    }
}

$VsixPath = if ([string]::IsNullOrWhiteSpace($VsixPath)) {
    Find-LatestVsix -CoreRoot $CorePath
} else {
    Resolve-ExistingFile -Path $VsixPath -Label "VSIX"
}
if ([string]::IsNullOrWhiteSpace($VsixPath)) {
    throw "Theseus VSIX was not found. Run with -BuildVsix or pass -VsixPath."
}

$RunnerPath = if ([string]::IsNullOrWhiteSpace($RunnerPath)) {
    Find-RunnerBinary -CoreRoot $CorePath
} else {
    Resolve-ExistingFile -Path $RunnerPath -Label "Runner"
}
if ([string]::IsNullOrWhiteSpace($RunnerPath)) {
    throw "theseus-runner.exe was not found. Run scripts\build-runner-binary.ps1 first, run with -BuildRunner, or pass -RunnerPath."
}

$installerCmd = Join-Path $repoRoot "Install-Theseus-TestPackage.cmd"
$installerScript = Join-Path $CorePath "scripts\install-test-package.ps1"
$packageReadme = Join-Path $CorePath "scripts\test-package-README.md"
if (-not (Test-Path -LiteralPath $installerCmd -PathType Leaf)) {
    throw "Installer wrapper was not found: $installerCmd"
}
if (-not (Test-Path -LiteralPath $installerScript -PathType Leaf)) {
    throw "Installer script was not found: $installerScript"
}
if (-not (Test-Path -LiteralPath $packageReadme -PathType Leaf)) {
    throw "Package README template was not found: $packageReadme"
}

$stagingPath = Join-Path $OutputDir $PackageName
Assert-WithinPath -Child $stagingPath -Parent $OutputDir -Label "Staging path"
if (Test-Path -LiteralPath $stagingPath) {
    Remove-Item -LiteralPath $stagingPath -Recurse -Force
}

New-Item -ItemType Directory -Path $stagingPath -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $stagingPath "scripts") -Force | Out-Null

Copy-Item -LiteralPath $packageReadme -Destination (Join-Path $stagingPath "README.md") -Force
Copy-Item -LiteralPath $installerCmd -Destination (Join-Path $stagingPath "Install-Theseus-TestPackage.cmd") -Force
Copy-Item -LiteralPath $installerScript -Destination (Join-Path $stagingPath "scripts\install-test-package.ps1") -Force
Copy-Item -LiteralPath $VsixPath -Destination (Join-Path $stagingPath (Split-Path -Leaf $VsixPath)) -Force
Copy-RunnerPayload -RunnerExe $RunnerPath -Destination (Join-Path $stagingPath "theseus-runner")

$zipPath = Join-Path $OutputDir "$PackageName.zip"
if (-not $NoZip) {
    Assert-WithinPath -Child $zipPath -Parent $OutputDir -Label "Zip path"
    if (Test-Path -LiteralPath $zipPath) {
        Remove-Item -LiteralPath $zipPath -Force
    }
    Compress-Archive -LiteralPath $stagingPath -DestinationPath $zipPath -Force
}

Write-Host "Theseus test package staged."
Write-Host "PackageDir: $stagingPath"
if (-not $NoZip) {
    Write-Host "ZipPath: $zipPath"
}
Write-Host "VSIX: $VsixPath"
Write-Host "RunnerPath: $RunnerPath"
