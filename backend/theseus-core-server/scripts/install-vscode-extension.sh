#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
CORE_PATH="$(cd "$SCRIPT_DIR/.." && pwd)"
WORKSPACE_PATH="$(cd "$CORE_PATH/../.." && pwd)"
PYTHON_BIN="${PYTHON:-python3}"
CODE_BIN="${CODE:-code}"
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
  --code PATH             VSCode CLI executable
  --vsix PATH             VSIX package path
  --skip-requirements     Do not install requirements.txt
  --skip-extension        Do not install the VSIX package
  --skip-settings         Do not write .vscode/settings.json
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
    --code)
      CODE_BIN="$2"
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

to_vscode_path() {
  local path_value="$1"
  if command -v cygpath >/dev/null 2>&1; then
    cygpath -w "$path_value"
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
  if [[ -z "$VSIX_PATH" ]]; then
    VSIX_PATH="$(find "$CORE_PATH/vscode-extension" -maxdepth 1 -name '*.vsix' -print | sort | tail -n 1)"
  fi
  if [[ -z "$VSIX_PATH" || ! -f "$VSIX_PATH" ]]; then
    echo "VSIX package was not found: $VSIX_PATH" >&2
    exit 1
  fi
  if ! command -v "$CODE_BIN" >/dev/null 2>&1; then
    echo "VSCode CLI was not found: $CODE_BIN" >&2
    exit 1
  fi
  "$CODE_BIN" --install-extension "$VSIX_PATH" --force
fi

if [[ "$SKIP_SETTINGS" -eq 0 ]]; then
  SETTINGS_DIR="$WORKSPACE_PATH/.vscode"
  SETTINGS_PATH="$SETTINGS_DIR/settings.json"
  mkdir -p "$SETTINGS_DIR"

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

echo "Theseus VSCode extension setup complete."
echo "CorePath: $(to_vscode_path "$CORE_PATH")"
echo "PythonPath: $(to_vscode_path "$VENV_PYTHON")"
echo "WorkspacePath: $(to_vscode_path "$WORKSPACE_PATH")"
