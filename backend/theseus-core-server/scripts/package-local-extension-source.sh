#!/usr/bin/env bash
set -euo pipefail

script_path="${BASH_SOURCE[0]}"
case "$script_path" in
  */*) script_dir_raw="${script_path%/*}" ;;
  *) script_dir_raw="." ;;
esac
script_dir="$(cd -- "$script_dir_raw" && pwd)"
ps_script="$script_dir/package-local-extension-source.ps1"

usage() {
  printf '%s\n' \
    "Usage:" \
    "  bash scripts/package-local-extension-source.sh [options]" \
    "" \
    "Options:" \
    "  --core-path PATH          theseus-core-server path" \
    "  --repo-root PATH          repository/package root" \
    "  --vsix-path PATH          explicit VSIX file to include" \
    "  --output-dir PATH         output directory. Defaults to <core>/dist/local-extension-package" \
    "  --package-name NAME       staged folder and zip basename. Defaults to Theseus-LocalExtensionSourcePackage" \
    "  --build-vsix              run npm compile and npx @vscode/vsce package before staging" \
    "  --no-zip                  create the folder only, without Compress-Archive" \
    "  -h, --help                show this help" \
    "" \
    "Examples:" \
    "  bash Package-Theseus-LocalExtension.sh" \
    "  bash backend/theseus-core-server/scripts/package-local-extension-source.sh --build-vsix"
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
    --repo-root)
      ps_args+=("-RepoRoot" "$(to_windows_path "$2")")
      shift 2
      ;;
    --vsix-path|--vsix)
      ps_args+=("-VsixPath" "$(to_windows_path "$2")")
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
