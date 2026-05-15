#!/usr/bin/env bash
set -euo pipefail

script_path="${BASH_SOURCE[0]}"
case "$script_path" in
  */*) script_dir_raw="${script_path%/*}" ;;
  *) script_dir_raw="." ;;
esac
script_dir="$(cd -- "$script_dir_raw" && pwd)"
core_path="$(cd "$script_dir/.." && pwd)"
ps_script="$script_dir/package-test-distribution.ps1"

usage() {
  printf '%s\n' \
    "Usage:" \
    "  bash scripts/package-test-distribution.sh [options]" \
    "" \
    "Options:" \
    "  --core-path PATH          theseus-core-server path" \
    "  --vsix-path PATH          Explicit VSIX file to include" \
    "  --runner-path PATH        Explicit theseus-runner.exe file to include" \
    "  --output-dir PATH         Output directory. Defaults to <core>/dist/test-package" \
    "  --package-name NAME       Staged folder and zip basename. Defaults to Theseus-TestPackage" \
    "  --build-vsix              Run npm compile and npx @vscode/vsce package before staging" \
    "  --build-runner            Run scripts/build-runner-binary.ps1 before staging" \
    "  --install-pyinstaller     Install PyInstaller before runner build" \
    "  --no-zip                  Create the folder only, without Compress-Archive" \
    "  -h, --help                Show this help" \
    "" \
    "Examples:" \
    "  bash Package-Theseus-TestPackage.sh" \
    "  bash Package-Theseus-TestPackage.sh --build-runner --install-pyinstaller" \
    "  bash backend/theseus-core-server/scripts/package-test-distribution.sh --build-vsix --runner-path /c/path/to/theseus-runner.exe"
}

to_windows_path() {
  local value="$1"
  if [[ "$value" != /* && "$value" != [A-Za-z]:* && "$value" != \\\\* ]]; then
    value="$PWD/$value"
  fi
  if command -v cygpath >/dev/null 2>&1; then
    cygpath -w "$value"
  else
    case "$value" in
      /[A-Za-z]/*)
        local drive="${value:1:1}"
        local rest="${value:3}"
        rest="${rest//\//\\}"
        printf '%s:\\%s\n' "${drive^^}" "$rest"
        ;;
      *)
        printf '%s\n' "$value"
        ;;
    esac
  fi
}

find_powershell() {
  command -v powershell.exe 2>/dev/null ||
    command -v powershell 2>/dev/null ||
    command -v pwsh 2>/dev/null
}

if [[ ! -f "$ps_script" ]]; then
  echo "PowerShell packager was not found: $ps_script" >&2
  exit 1
fi

ps_args=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --core-path)
      ps_args+=("-CorePath" "$(to_windows_path "$2")")
      shift 2
      ;;
    --vsix-path|--vsix)
      ps_args+=("-VsixPath" "$(to_windows_path "$2")")
      shift 2
      ;;
    --runner-path)
      ps_args+=("-RunnerPath" "$(to_windows_path "$2")")
      shift 2
      ;;
    --output-dir)
      ps_args+=("-OutputDir" "$(to_windows_path "$2")")
      shift 2
      ;;
    --package-name)
      ps_args+=("-PackageName" "$2")
      shift 2
      ;;
    --build-vsix)
      ps_args+=("-BuildVsix")
      shift
      ;;
    --build-runner)
      ps_args+=("-BuildRunner")
      shift
      ;;
    --install-pyinstaller)
      ps_args+=("-InstallPyInstaller")
      shift
      ;;
    --no-zip)
      ps_args+=("-NoZip")
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

powershell_bin="$(find_powershell || true)"
if [[ -z "$powershell_bin" ]]; then
  echo "PowerShell was not found. On Windows Git Bash, make sure powershell.exe is on PATH." >&2
  exit 1
fi

ps_args=(
  -NoProfile
  -ExecutionPolicy Bypass
  -File "$(to_windows_path "$ps_script")"
  "${ps_args[@]}"
)

"$powershell_bin" "${ps_args[@]}"
