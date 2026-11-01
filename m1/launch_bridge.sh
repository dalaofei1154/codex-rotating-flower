#!/bin/bash
# Keep the service usable if WorkBuddy replaces its bundled Python version.
shopt -s nullglob
preferred_python="$1"
shift
python_candidates=(
  "$preferred_python"
  "$HOME"/.workbuddy/binaries/python/versions/*/bin/python3
  "$HOME"/.workbuddy-ai/binaries/python/versions/*/bin/python3
  /opt/homebrew/bin/python3 /usr/local/bin/python3 /usr/bin/python3
)
for flower_python in "${python_candidates[@]}"; do
  # On a clean Mac the system Python can be a developer-tools stub. Probing it
  # may open an Xcode installation dialog; WorkBuddy users do not need Xcode.
  if [[ "$flower_python" == /usr/bin/python3 ]] && ! /usr/bin/xcode-select -p >/dev/null 2>&1; then
    continue
  fi
  if [[ -x "$flower_python" ]] && "$flower_python" -c 'import sys, sqlite3, fcntl; assert sys.version_info >= (3, 9)' >/dev/null 2>&1; then
    exec "$flower_python" "$@"
  fi
done
echo 'Python 3.9+ not found. Open WorkBuddy, run a Python task, and reinstall the flower bridge.' >&2
exit 1
