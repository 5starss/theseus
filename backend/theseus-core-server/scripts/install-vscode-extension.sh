#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
CORE_PATH="$(cd "$SCRIPT_DIR/.." && pwd)"
WORKSPACE_PATH="$(cd "$CORE_PATH/../.." && pwd)"
PYTHON_BIN="${PYTHON:-python3}"
CODE_BIN="${CODE:-}"
IDE_TARGET="${THESEUS_IDE:-auto}"
SETTINGS_DIR_NAME="${THESEUS_SETTINGS_DIR:-}"
EXTENSIONS_DIR_PATH="${THESEUS_EXTENSIONS_DIR:-}"
VSIX_PATH="${VSIX_PATH:-}"
SKIP_REQUIREMENTS=0
SKIP_EXTENSION=0
SKIP_SETTINGS=0
INSTALL_PLAYWRIGHT=0

usage() {
  cat <<'EOF'
Usage: scripts/install-vscode-extension.sh [options]

Options:
  --core-path PATH        theseus-core-server path
  --workspace-path PATH   VSCode workspace path
  --python PATH           Python executable for venv creation
  --ide NAME              IDE target: auto, vscode, antigravity
  --code PATH             IDE CLI executable (overrides --ide)
  --settings-dir NAME     Workspace settings folder name
  --extensions-dir PATH   IDE extension storage directory
  --vsix PATH             VSIX package path
  --skip-requirements     Do not install requirements.txt
  --skip-extension        Do not install the VSIX package
  --skip-settings         Do not write IDE settings.json
  --install-playwright    Install Chromium browser binaries for Playwright tools
  -h, --help              Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --core-path)
      CORE_PATH="$(cd "$2" && pwd)"
      shift 2
      ;;
    --workspace-path)
      WORKSPACE_PATH="$(cd "$2" && pwd)"
      shift 2
      ;;
    --python)
      PYTHON_BIN="$2"
      shift 2
      ;;
    --ide)
      IDE_TARGET="$2"
      shift 2
      ;;
    --code)
      CODE_BIN="$2"
      shift 2
      ;;
    --settings-dir)
      SETTINGS_DIR_NAME="$2"
      shift 2
      ;;
    --extensions-dir)
      EXTENSIONS_DIR_PATH="$2"
      shift 2
      ;;
    --vsix)
      VSIX_PATH="$2"
      shift 2
      ;;
    --skip-requirements)
      SKIP_REQUIREMENTS=1
      shift
      ;;
    --skip-extension)
      SKIP_EXTENSION=1
      shift
      ;;
    --skip-settings)
      SKIP_SETTINGS=1
      shift
      ;;
    --install-playwright)
      INSTALL_PLAYWRIGHT=1
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

lowercase() {
  printf '%s\n' "$1" | tr '[:upper:]' '[:lower:]'
}

command_path() {
  command -v "$1" 2>/dev/null
}

cli_for_ide() {
  local target
  target="$(lowercase "$1")"
  case "$target" in
    antigravity)
      command_path antigravity.cmd || command_path antigravity
      ;;
    vscode|code)
      command_path code.cmd || command_path code
      ;;
    *)
      return 1
      ;;
  esac
}

detect_ide_from_code_bin() {
  local value
  value="$(lowercase "$1")"
  if [[ "$value" == *antigravity* ]]; then
    printf 'antigravity\n'
  elif [[ "$value" == *code* ]]; then
    printf 'vscode\n'
  else
    printf 'custom\n'
  fi
}

detect_ide_from_env() {
  local hints
  hints="$(
    printf '%s ' \
      "${TERM_PROGRAM:-}" \
      "${VSCODE_CWD:-}" \
      "${VSCODE_GIT_ASKPASS_NODE:-}" \
      "${VSCODE_GIT_ASKPASS_MAIN:-}" \
      "${VSCODE_IPC_HOOK_CLI:-}" \
      "${ANTIGRAVITY_BIN:-}"
  )"
  hints="$(lowercase "$hints")"
  if [[ "$hints" == *antigravity* ]]; then
    printf 'antigravity\n'
    return 0
  fi
  if [[ "$hints" == *"microsoft vs code"* || "$hints" == *code.exe* ]]; then
    printf 'vscode\n'
    return 0
  fi
  if [[ "$(lowercase "${TERM_PROGRAM:-}")" == "vscode" ]]; then
    printf 'vscode\n'
    return 0
  fi
  return 1
}

detect_ide_from_processes() {
  if ! command -v powershell.exe >/dev/null 2>&1; then
    return 1
  fi
  local process_name
  process_name="$(
    powershell.exe -NoProfile -Command \
      "\$p = Get-Process Antigravity,Code -ErrorAction SilentlyContinue | Sort-Object StartTime -Descending | Select-Object -First 1 -ExpandProperty ProcessName; if (\$p) { \$p.ToLowerInvariant() }" \
      2>/dev/null | tr -d '\r' | head -n 1
  )"
  case "$process_name" in
    antigravity)
      printf 'antigravity\n'
      ;;
    code)
      printf 'vscode\n'
      ;;
    *)
      return 1
      ;;
  esac
}

resolve_ide_target() {
  if [[ -n "$CODE_BIN" ]]; then
    detect_ide_from_code_bin "$CODE_BIN"
    return 0
  fi

  local target
  target="$(lowercase "$IDE_TARGET")"
  case "$target" in
    auto)
      target="$(detect_ide_from_env || true)"
      if [[ -z "$target" ]]; then
        target="$(detect_ide_from_processes || true)"
      fi
      if [[ -z "$target" ]]; then
        target="vscode"
      fi
      ;;
    vscode|code)
      target="vscode"
      ;;
    antigravity)
      target="antigravity"
      ;;
    *)
      echo "Unsupported IDE target: $IDE_TARGET" >&2
      echo "Use --ide auto, --ide vscode, --ide antigravity, or --code PATH." >&2
      exit 2
      ;;
  esac

  printf '%s\n' "$target"
}

settings_dir_for_ide() {
  if [[ -n "$SETTINGS_DIR_NAME" ]]; then
    printf '%s\n' "$SETTINGS_DIR_NAME"
    return 0
  fi

  case "$(lowercase "$1")" in
    antigravity)
      printf '.antigravity\n'
      ;;
    *)
      printf '.vscode\n'
      ;;
  esac
}

user_settings_path_for_ide() {
  local target
  target="$(lowercase "$1")"
  case "$target" in
    antigravity)
      if [[ -n "${APPDATA:-}" ]]; then
        printf '%s\\Antigravity\\User\\settings.json\n' "$APPDATA"
      elif [[ -n "${USERPROFILE:-}" ]]; then
        printf '%s\\AppData\\Roaming\\Antigravity\\User\\settings.json\n' "$USERPROFILE"
      else
        return 1
      fi
      ;;
    *)
      return 1
      ;;
  esac
}

is_windows_path() {
  [[ "$1" =~ ^[A-Za-z]:[\\/] || "$1" == \\\\* ]]
}

home_path() {
  if [[ -n "${USERPROFILE:-}" ]]; then
    printf '%s\n' "$USERPROFILE"
  elif [[ -n "${HOME:-}" ]]; then
    printf '%s\n' "$HOME"
  else
    return 1
  fi
}

home_child_path() {
  local home="$1"
  local windows_child="$2"
  local posix_child
  posix_child="${windows_child//\\//}"

  if is_windows_path "$home"; then
    printf '%s\\%s\n' "$home" "$windows_child"
  else
    printf '%s/%s\n' "$home" "$posix_child"
  fi
}

extensions_dir_for_ide() {
  local target
  target="$(lowercase "$1")"

  if [[ -n "$EXTENSIONS_DIR_PATH" ]]; then
    printf '%s\n' "$EXTENSIONS_DIR_PATH"
    return 0
  fi

  local home
  home="$(home_path)" || return 1
  case "$target" in
    antigravity)
      home_child_path "$home" '.antigravity\extensions'
      ;;
    vscode|code)
      home_child_path "$home" '.vscode\extensions'
      ;;
    *)
      return 1
      ;;
  esac
}

settings_path_for_ide() {
  local target
  target="$(lowercase "$1")"

  if [[ -n "$SETTINGS_DIR_NAME" ]]; then
    printf '%s/%s/settings.json\n' "$WORKSPACE_PATH" "$(settings_dir_for_ide "$target")"
    return 0
  fi

  if [[ "$target" == "antigravity" ]]; then
    user_settings_path_for_ide "$target"
    return 0
  fi

  printf '%s/%s/settings.json\n' "$WORKSPACE_PATH" "$(settings_dir_for_ide "$target")"
}

resolve_ide_cli() {
  if [[ -n "$CODE_BIN" ]]; then
    DETECTED_IDE="$(detect_ide_from_code_bin "$CODE_BIN")"
    return 0
  fi

  local target
  target="$(resolve_ide_target)"
  CODE_BIN="$(cli_for_ide "$target" || true)"
  if [[ -z "$CODE_BIN" ]]; then
    echo "IDE CLI was not found for target: $target" >&2
    echo "Use --code PATH to specify the editor CLI explicitly." >&2
    exit 1
  fi
  DETECTED_IDE="$target"
}

to_vscode_path() {
  local path_value="$1"
  if is_windows_path "$path_value"; then
    printf '%s\n' "$path_value"
  elif command -v cygpath >/dev/null 2>&1; then
    cygpath -w "$path_value"
  elif command -v wslpath >/dev/null 2>&1; then
    wslpath -w "$path_value"
  else
    printf '%s\n' "$path_value"
  fi
}

if [[ ! -f "$CORE_PATH/requirements.txt" ]]; then
  echo "requirements.txt was not found: $CORE_PATH/requirements.txt" >&2
  exit 1
fi

VENV_PATH="$CORE_PATH/.venv"
if [[ ! -d "$VENV_PATH" ]]; then
  if command -v uv >/dev/null 2>&1; then
    uv venv --python 3.11 "$VENV_PATH"
  else
    "$PYTHON_BIN" -m venv "$VENV_PATH"
  fi
fi

if [[ -x "$VENV_PATH/Scripts/python.exe" ]]; then
  VENV_PYTHON="$VENV_PATH/Scripts/python.exe"
elif [[ -x "$VENV_PATH/bin/python" ]]; then
  VENV_PYTHON="$VENV_PATH/bin/python"
else
  echo "Python executable was not found in venv: $VENV_PATH" >&2
  exit 1
fi

if [[ "$SKIP_SETTINGS" -eq 0 || "$SKIP_EXTENSION" -eq 0 ]]; then
  DETECTED_IDE="$(resolve_ide_target)"
fi

if [[ "$SKIP_SETTINGS" -eq 0 ]]; then
  SETTINGS_PATH="$(settings_path_for_ide "$DETECTED_IDE")"

  SETTINGS_PATH="$SETTINGS_PATH" \
  CORE_SETTING="$(to_vscode_path "$CORE_PATH")" \
  PYTHON_SETTING="$(to_vscode_path "$VENV_PYTHON")" \
  WORKSPACE_SETTING="$(to_vscode_path "$WORKSPACE_PATH")" \
  "$VENV_PYTHON" - <<'PY'
import json
import os
import shutil
import time
from pathlib import Path

settings_path = Path(os.environ["SETTINGS_PATH"])
settings_path.parent.mkdir(parents=True, exist_ok=True)
data = {}
if settings_path.exists():
    raw = settings_path.read_text(encoding="utf-8-sig")
    if raw.strip():
        try:
            loaded = json.loads(raw)
            if isinstance(loaded, dict):
                data = loaded
        except json.JSONDecodeError:
            backup_path = settings_path.with_name(
                f"{settings_path.name}.bak-{time.strftime('%Y%m%d%H%M%S')}"
            )
            shutil.copy2(settings_path, backup_path)
            print(
                "Existing settings.json is not strict JSON. "
                f"Backed up to {backup_path} and writing fresh settings."
            )

data["theseus.corePath"] = os.environ["CORE_SETTING"]
data["theseus.pythonPath"] = os.environ["PYTHON_SETTING"]
data["theseus.workspacePath"] = os.environ["WORKSPACE_SETTING"]
data.setdefault("theseus.serverUrl", "")

settings_path.write_text(
    json.dumps(data, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
PY
fi

if [[ "$SKIP_REQUIREMENTS" -eq 0 ]]; then
  if command -v uv >/dev/null 2>&1; then
    uv pip install -r "$CORE_PATH/requirements.txt" --python "$VENV_PYTHON"
  else
    "$VENV_PYTHON" -m pip install --upgrade pip
    "$VENV_PYTHON" -m pip install -r "$CORE_PATH/requirements.txt"
  fi
fi

if [[ "$INSTALL_PLAYWRIGHT" -eq 1 ]]; then
  "$VENV_PYTHON" -m playwright install chromium
fi

if [[ "$SKIP_EXTENSION" -eq 0 ]]; then
  resolve_ide_cli
  if [[ -z "$VSIX_PATH" ]]; then
    VSIX_PATH="$(find "$CORE_PATH/vscode-extension" -maxdepth 1 -name '*.vsix' -print | sort | tail -n 1)"
  fi
  if [[ -z "$VSIX_PATH" || ! -f "$VSIX_PATH" ]]; then
    echo "VSIX package was not found: $VSIX_PATH" >&2
    exit 1
  fi
  if ! command -v "$CODE_BIN" >/dev/null 2>&1; then
    echo "IDE CLI was not found: $CODE_BIN" >&2
    exit 1
  fi
  EXTENSIONS_DIR="$(extensions_dir_for_ide "$DETECTED_IDE" || true)"
  if [[ -n "$EXTENSIONS_DIR" ]]; then
    CLI_EXTENSIONS_DIR="$(to_vscode_path "$EXTENSIONS_DIR")"
    echo "Installing VSIX into IDE target: $DETECTED_IDE ($CODE_BIN)"
    echo "ExtensionsDir: $CLI_EXTENSIONS_DIR"
    "$CODE_BIN" --extensions-dir "$CLI_EXTENSIONS_DIR" --install-extension "$VSIX_PATH" --force
  else
    echo "Installing VSIX into IDE target: $DETECTED_IDE ($CODE_BIN)"
    "$CODE_BIN" --install-extension "$VSIX_PATH" --force
  fi
fi

echo "Theseus VSCode extension setup complete."
if [[ "${DETECTED_IDE:-}" ]]; then
  echo "IDE: $DETECTED_IDE ($CODE_BIN)"
fi
if [[ "$SKIP_SETTINGS" -eq 0 ]]; then
  echo "SettingsPath: $(to_vscode_path "$SETTINGS_PATH")"
fi
if [[ "${CLI_EXTENSIONS_DIR:-}" ]]; then
  echo "ExtensionsDir: $CLI_EXTENSIONS_DIR"
fi
echo "CorePath: $(to_vscode_path "$CORE_PATH")"
echo "PythonPath: $(to_vscode_path "$VENV_PYTHON")"
echo "WorkspacePath: $(to_vscode_path "$WORKSPACE_PATH")"
