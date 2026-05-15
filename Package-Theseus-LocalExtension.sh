#!/usr/bin/env bash
set -euo pipefail

script_path="${BASH_SOURCE[0]}"
case "$script_path" in
  */*) script_dir="${script_path%/*}" ;;
  *) script_dir="." ;;
esac
repo_dir="$(cd -- "$script_dir" && pwd)"
packager="$repo_dir/backend/theseus-core-server/scripts/package-local-extension-source.sh"

if [[ ! -f "$packager" ]]; then
  echo "Theseus local extension source package builder was not found." >&2
  echo "" >&2
  echo "Expected:" >&2
  echo "  $packager" >&2
  exit 1
fi

case "${1:-}" in
  -h|--help)
    "$BASH" "$packager" --help
    exit $?
    ;;
esac

echo "Theseus local extension source package build"
echo "Repository: $repo_dir"
echo "Packager  : $packager"
echo ""

"$BASH" "$packager" --build-vsix "$@"

echo ""
echo "Theseus local extension source package build complete."
