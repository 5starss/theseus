[CmdletBinding()]
param(
    [string]$CorePath = "",
    [string]$RepoRoot = "",
    [string]$VsixPath = "",
    [string]$OutputDir = "",
    [string]$PackageName = "Theseus-LocalExtensionSourcePackage",
    [switch]$BuildVsix,
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
    Write-Host "  powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\package-local-extension-source.ps1 [options]"
    Write-Host ""
    Write-Host "Options:"
    Write-Host "  -BuildVsix             Run npm compile and npx @vscode/vsce package before staging"
    Write-Host "  -CorePath PATH         theseus-core-server path. Defaults to this script's parent folder"
    Write-Host "  -RepoRoot PATH         Repository/package root. Defaults to two levels above CorePath"
    Write-Host "  -VsixPath PATH         Explicit VSIX file to include"
    Write-Host "  -OutputDir PATH        Output directory. Defaults to <core>\dist\local-extension-package"
    Write-Host "  -PackageName NAME      Staged folder and zip basename. Defaults to Theseus-LocalExtensionSourcePackage"
    Write-Host "  -NoZip                 Create the folder only, without Compress-Archive"
    Write-Host "  -Help                  Show this help"
}

function Resolve-CorePath {
    param([string]$Value)

    if ([string]::IsNullOrWhiteSpace($Value)) {
        $Value = Join-Path $script:ScriptRoot ".."
    }
    if (-not (Test-Path -LiteralPath $Value -PathType Container)) {
        throw "CorePath does not exist: $Value"
    }
    return (Resolve-Path -LiteralPath $Value).Path
}

function Resolve-RepoRoot {
    param(
        [string]$CoreRoot,
        [string]$Value
    )

    if ([string]::IsNullOrWhiteSpace($Value)) {
        $Value = Join-Path $CoreRoot "..\.."
    }
    if (-not (Test-Path -LiteralPath $Value -PathType Container)) {
        throw "RepoRoot does not exist: $Value"
    }
    $resolved = (Resolve-Path -LiteralPath $Value).Path
    $installer = Join-Path $resolved "Install-Theseus-Extension.cmd"
    if (-not (Test-Path -LiteralPath $installer -PathType Leaf)) {
        throw "Install-Theseus-Extension.cmd was not found in RepoRoot: $resolved"
    }
    return $resolved
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
    if (-not (Test-Path -LiteralPath $extensionDir -PathType Container)) {
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

function Test-ExcludedDirectoryName {
    param([string]$Name)

    foreach ($excluded in @("__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".git", ".venv", "node_modules", "build", "dist", "tests")) {
        if ($Name.Equals($excluded, [System.StringComparison]::OrdinalIgnoreCase)) {
            return $true
        }
    }
    return $false
}

function Test-ExcludedFileName {
    param([System.IO.FileInfo]$File)

    if ($File.Name.Equals(".env", [System.StringComparison]::OrdinalIgnoreCase)) {
        return $true
    }
    foreach ($extension in @(".pyc", ".pyo")) {
        if ($File.Extension.Equals($extension, [System.StringComparison]::OrdinalIgnoreCase)) {
            return $true
        }
    }
    return $false
}

function Copy-DirectoryFiltered {
    param(
        [string]$Source,
        [string]$Destination
    )

    if (-not (Test-Path -LiteralPath $Source -PathType Container)) {
        throw "Source directory does not exist: $Source"
    }
    New-Item -ItemType Directory -Path $Destination -Force | Out-Null

    foreach ($item in Get-ChildItem -LiteralPath $Source -Force) {
        $target = Join-Path $Destination $item.Name
        if ($item.PSIsContainer) {
            if (Test-ExcludedDirectoryName -Name $item.Name) {
                continue
            }
            Copy-DirectoryFiltered -Source $item.FullName -Destination $target
            continue
        }

        if (Test-ExcludedFileName -File $item) {
            continue
        }
        Copy-Item -LiteralPath $item.FullName -Destination $target -Force
    }
}

function Copy-RequiredFile {
    param(
        [string]$Source,
        [string]$Destination
    )

    if (-not (Test-Path -LiteralPath $Source -PathType Leaf)) {
        throw "Required file does not exist: $Source"
    }
    $destinationDir = Split-Path -Parent $Destination
    New-Item -ItemType Directory -Path $destinationDir -Force | Out-Null
    Copy-Item -LiteralPath $Source -Destination $Destination -Force
}

function Copy-OptionalFile {
    param(
        [string]$Source,
        [string]$Destination
    )

    if (-not (Test-Path -LiteralPath $Source -PathType Leaf)) {
        return
    }
    $destinationDir = Split-Path -Parent $Destination
    New-Item -ItemType Directory -Path $destinationDir -Force | Out-Null
    Copy-Item -LiteralPath $Source -Destination $Destination -Force
}

function ConvertTo-AsciiText {
    param([string]$Value)

    $builder = [System.Text.StringBuilder]::new()
    foreach ($character in $Value.ToCharArray()) {
        if ([int][char]$character -le 127) {
            [void]$builder.Append($character)
        }
    }
    return $builder.ToString()
}

function Copy-OptionalRequirementsFileAscii {
    param(
        [string]$Source,
        [string]$Destination
    )

    if (-not (Test-Path -LiteralPath $Source -PathType Leaf)) {
        return
    }

    $destinationDir = Split-Path -Parent $Destination
    New-Item -ItemType Directory -Path $destinationDir -Force | Out-Null

    $asciiLines = @(
        Get-Content -LiteralPath $Source -Encoding UTF8 |
            ForEach-Object { ConvertTo-AsciiText -Value $_ }
    )
    Set-Content -LiteralPath $Destination -Value $asciiLines -Encoding ASCII
}

function Assert-AsciiFile {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return
    }

    $bytes = [System.IO.File]::ReadAllBytes((Resolve-Path -LiteralPath $Path).Path)
    foreach ($byte in $bytes) {
        if ($byte -gt 127) {
            throw "Packaged requirements file contains non-ASCII bytes: $Path"
        }
    }
}

function Write-PackageReadme {
    param([string]$Destination)

    $content = @'
# Theseus Local Extension Source Package

이 패키지는 Theseus VSCode/Antigravity extension을 로컬 환경에서 바로 설치하고
실행하기 위한 최소 소스 런타임 패키지입니다.

## 포함된 내용

- `Install-Theseus-Extension.cmd`: 더블클릭 설치 스크립트
- `Uninstall-Theseus-VSCode.cmd`: VSCode Theseus 설정/extension 정리 스크립트
- `backend/theseus-core-server/theseus_engine`: 로컬 daemon/stdio runner 런타임
- `backend/theseus-core-server/theseus_cli`: 로컬 CLI 보조 코드
- `backend/theseus-core-server/vscode-extension/*.vsix`: 설치할 extension 패키지
- `backend/theseus-core-server/requirements*.txt`: Python 의존성 목록
- `backend/theseus-core-server/usage.md`: 상세 사용 가이드

## 제외된 내용

이 패키지에는 서버 orchestration/API 코드, 프론트엔드, 인프라 설정, 가상환경,
빌드 산출물, 테스트 폴더, 실제 `.env` 파일이 포함되지 않습니다.

## 설치 방법

1. 이 ZIP을 원하는 위치에 압축 해제합니다.
2. `Install-Theseus-Extension.cmd`를 더블클릭합니다.
3. 설치가 끝나면 VSCode 또는 Antigravity를 열고 Theseus 사이드바에서
   `Theseus: Start Agent`를 실행합니다.

설치 대상 IDE를 명시하려면 명령 프롬프트에서 다음처럼 실행합니다.

```cmd
Install-Theseus-Extension.cmd -Ide vscode
Install-Theseus-Extension.cmd -Ide antigravity
```

작업할 프로젝트가 이 패키지 폴더와 다르면 workspace 경로를 지정합니다.

```cmd
Install-Theseus-Extension.cmd -WorkspacePath C:\path\to\your\project
```

## 삭제 방법

VSCode의 Theseus extension, Theseus user settings, workspace `.vscode` 설정,
패키지 내부 `.venv`를 정리하려면 다음 파일을 더블클릭합니다.

```text
Uninstall-Theseus-VSCode.cmd
```

삭제 중 Python executable이 사용 중이라는 메시지가 나오면 VSCode/Antigravity와
실행 중인 Theseus daemon을 종료한 뒤 다시 실행합니다.

## 참고

이 패키지는 소스 런타임 배포용입니다. 핵심 Python 코드를 숨겨서 배포하려면
`theseus-runner.exe` 기반의 source-free 테스트 패키지를 별도로 생성해야 합니다.
'@

    Set-Content -LiteralPath $Destination -Value $content -Encoding UTF8
}

function Assert-PackageDoesNotContainExcludedRoots {
    param([string]$PackageRoot)

    $badPaths = @()
    foreach ($relative in @(
        "backend\theseus-core-server\src",
        "frontend",
        "infra",
        "backend\theseus-api-server",
        "backend\theseus-core-server\.venv",
        "backend\theseus-core-server\build",
        "backend\theseus-core-server\dist",
        "backend\theseus-core-server\tests",
        "backend\theseus-core-server\.env"
    )) {
        $candidate = Join-Path $PackageRoot $relative
        if (Test-Path -LiteralPath $candidate) {
            $badPaths += $candidate
        }
    }

    if ($badPaths.Count -gt 0) {
        throw "Package contains excluded paths: $($badPaths -join ', ')"
    }
}

if ($Help) {
    Show-Usage
    exit 0
}

$CorePath = Resolve-CorePath -Value $CorePath
$RepoRoot = Resolve-RepoRoot -CoreRoot $CorePath -Value $RepoRoot
$extensionDir = Join-Path $CorePath "vscode-extension"

if ([string]::IsNullOrWhiteSpace($OutputDir)) {
    $OutputDir = Join-Path $CorePath "dist\local-extension-package"
}
$OutputDir = [System.IO.Path]::GetFullPath($OutputDir)
New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null

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

$installCmd = Join-Path $RepoRoot "Install-Theseus-Extension.cmd"
$uninstallCmd = Join-Path $RepoRoot "Uninstall-Theseus-VSCode.cmd"
if (-not (Test-Path -LiteralPath $installCmd -PathType Leaf)) {
    throw "Installer wrapper was not found: $installCmd"
}
if (-not (Test-Path -LiteralPath $uninstallCmd -PathType Leaf)) {
    throw "Uninstaller wrapper was not found: $uninstallCmd"
}

$stagingPath = Join-Path $OutputDir $PackageName
Assert-WithinPath -Child $stagingPath -Parent $OutputDir -Label "Staging path"
if (Test-Path -LiteralPath $stagingPath) {
    Remove-Item -LiteralPath $stagingPath -Recurse -Force
}

New-Item -ItemType Directory -Path $stagingPath -Force | Out-Null
$coreDestination = Join-Path $stagingPath "backend\theseus-core-server"
New-Item -ItemType Directory -Path $coreDestination -Force | Out-Null

Write-PackageReadme -Destination (Join-Path $stagingPath "README.md")
Copy-RequiredFile -Source $installCmd -Destination (Join-Path $stagingPath "Install-Theseus-Extension.cmd")
Copy-RequiredFile -Source $uninstallCmd -Destination (Join-Path $stagingPath "Uninstall-Theseus-VSCode.cmd")

foreach ($fileName in @(
    ".env.example",
    "theseus_cli.py",
    "usage.md"
)) {
    Copy-OptionalFile -Source (Join-Path $CorePath $fileName) -Destination (Join-Path $coreDestination $fileName)
}

foreach ($fileName in @(
    "requirements.txt",
    "requirements-browser.txt",
    "requirements-custom-tools.txt",
    "requirements-doc-tools.txt"
)) {
    $destination = Join-Path $coreDestination $fileName
    Copy-OptionalRequirementsFileAscii -Source (Join-Path $CorePath $fileName) -Destination $destination
    Assert-AsciiFile -Path $destination
}

Copy-RequiredFile -Source (Join-Path $CorePath "scripts\install-vscode-extension.ps1") -Destination (Join-Path $coreDestination "scripts\install-vscode-extension.ps1")
Copy-RequiredFile -Source (Join-Path $CorePath "scripts\install-vscode-extension.sh") -Destination (Join-Path $coreDestination "scripts\install-vscode-extension.sh")
Copy-RequiredFile -Source $VsixPath -Destination (Join-Path $coreDestination ("vscode-extension\" + (Split-Path -Leaf $VsixPath)))
Copy-DirectoryFiltered -Source (Join-Path $CorePath "theseus_engine") -Destination (Join-Path $coreDestination "theseus_engine")
Copy-DirectoryFiltered -Source (Join-Path $CorePath "theseus_cli") -Destination (Join-Path $coreDestination "theseus_cli")

Assert-PackageDoesNotContainExcludedRoots -PackageRoot $stagingPath

$zipPath = Join-Path $OutputDir "$PackageName.zip"
if (-not $NoZip) {
    Assert-WithinPath -Child $zipPath -Parent $OutputDir -Label "Zip path"
    if (Test-Path -LiteralPath $zipPath) {
        Remove-Item -LiteralPath $zipPath -Force
    }
    Compress-Archive -LiteralPath $stagingPath -DestinationPath $zipPath -Force
}

Write-Host "Theseus local extension source package staged."
Write-Host "PackageDir: $stagingPath"
if (-not $NoZip) {
    Write-Host "ZipPath: $zipPath"
}
Write-Host "VSIX: $VsixPath"
Write-Host "Excluded: src, frontend, infra, theseus-api-server, .venv, build, dist, tests, .env, caches"
