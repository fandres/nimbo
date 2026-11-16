#!/bin/bash
# Run Windows Python in the dedicated, already prepared Nimbo build prefix.
set -euo pipefail
project_dir="$(cd -- "$(dirname -- "$0")/.." && pwd)"
export WINEPREFIX="$project_dir/build/windows/prefix"
export WINEDEBUG=-all
if [[ ! -f "$WINEPREFIX/drive_c/Python313/python.exe" ]]; then
  echo 'Falta instalar Python 3.13 para Windows en el prefijo build/windows/prefix.' >&2
  exit 1
fi
cd "$project_dir"
exec wine 'C:\Python313\python.exe' "$@"
