#!/bin/bash
# Run directly from the user's Terminal session, never through an AI tool.
set -euo pipefail
flower_resources="$(cd -- "$(dirname -- "$0")" && pwd)"
flower_action="${1:-install}"
case "$flower_action" in install|uninstall) ;; *) exit 2 ;; esac
if [[ "$(/usr/bin/uname -m)" != arm64 ]]; then
  echo '这个安装包适用于 Apple 芯片 Mac（M1/M2/M3/M4 等）。'
  exit 1
fi
cd "$flower_resources"
/usr/bin/shasum -a 256 -c SHA256SUMS
flower_support="$HOME/Library/Application Support/RotatingFlower"
flower_runtime="$flower_support/python-3.13.12-20260211"
flower_created=0
# Setup owns service rollback. Keep the shared runtime whenever a service remains.
flower_stage=''
trap 'if [[ -n "$flower_stage" ]]; then /bin/rm -rf -- "$flower_stage"; fi' EXIT
if [[ ! -d "$flower_runtime" ]]; then
  /bin/mkdir -p "$flower_support"
  flower_stage="$(/usr/bin/mktemp -d "$flower_support/.python-stage.XXXXXX")"
  /usr/bin/tar -xzf "$flower_resources/python-arm64.tar.gz" -C "$flower_stage"
  /bin/mv "$flower_stage/python" "$flower_runtime"
  flower_created=1
fi
# Use the bundled interpreter only. Ignore shell Python settings and user packages.
set +e
PYTHONNOUSERSITE=1 PYTHONPATH= PYTHONHOME= "$flower_runtime/bin/python3" -E -s \
  "$flower_resources/integrated_setup.py" "$flower_action" --verify-seconds 12 "${@:2}"
flower_result=$?
set -e
if [[ "$flower_result" != 0 && "$flower_result" != 3 && "$flower_result" != 4 && "$flower_result" != 5 && "$flower_created" == 1 && \
      ! -f "$HOME/Library/LaunchAgents/com.rotatingflower.codex-motor.plist" ]]; then
  /bin/rm -rf -- "$flower_runtime"
elif [[ "$flower_action" == uninstall && "$flower_result" == 0 && \
        ! -f "$HOME/Library/LaunchAgents/com.rotatingflower.codex-motor.plist" ]]; then
  /bin/rm -rf -- "$flower_runtime"
fi
exit "$flower_result"
