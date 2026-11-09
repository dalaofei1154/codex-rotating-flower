#!/bin/bash
# Download a pinned release to disk and verify it before executing any package code.
set -euo pipefail

if [[ $# == 1 && ( "$1" == --help || "$1" == -h ) ]]; then
  echo '用法：/bin/bash install_unified_release.sh'
  echo '安装小花 v0.7.0（Apple 芯片 Mac）；自动识别已安装的 Codex / WorkBuddy / DeepSeek Harness。'
  echo '退出码：0 已就绪；5 已安装、等待应用；3 自检未通过；4 控制板缺少提醒灯能力；其他值为未完成。'
  exit 0
fi
if [[ $# != 0 ]]; then
  echo '此入口只安装固定版本 v0.7.0，不接受额外参数。使用 --help 查看说明。' >&2
  exit 2
fi
if [[ "$(/usr/bin/uname -s)" != Darwin || "$(/usr/bin/uname -m)" != arm64 ]]; then
  echo '此安装包仅适用于 Apple 芯片 Mac（M1/M2/M3/M4 等）。' >&2
  exit 1
fi
if [[ "$(/usr/bin/id -u)" == 0 ]]; then
  echo '请以当前登录用户运行，不要使用 sudo；小花安装到用户目录。' >&2
  exit 1
fi

flower_version='0.7.0'
flower_name="RotatingFlower-Mac-v$flower_version"
flower_url="https://github.com/dalaofei1154/rotating-flower/releases/download/v$flower_version/$flower_name.zip"
flower_expected_sha='ede5370522558ab2a2bc49f4c9c4afded89d20d04c55a48263457e13923dbf3b'
flower_work=''
flower_cleanup() {
  if [[ -n "$flower_work" ]]; then /bin/rm -rf -- "$flower_work"; fi
}
trap flower_cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
flower_work="$(/usr/bin/mktemp -d "${TMPDIR:-/tmp}/rotating-flower-release.XXXXXX")"
flower_archive="$flower_work/$flower_name.zip"

# Accept only a host, never a URL, credentials, options or shell syntax.
flower_proxy_host_for_url() {
  local flower_host="$1" flower_part flower_left flower_right flower_count
  local flower_parts=()
  if [[ "$flower_host" == \[*\] ]]; then
    flower_host="${flower_host:1:${#flower_host}-2}"
    [[ "$flower_host" == *:* ]] || return 1
  fi
  if [[ "$flower_host" == *:* ]]; then
    if [[ "$flower_host" == *::* ]]; then
      flower_left="${flower_host%%::*}"
      flower_right="${flower_host#*::}"
      [[ "$flower_right" != *::* ]] || return 1
      flower_count=0
      for flower_part in "$flower_left" "$flower_right"; do
        [[ -z "$flower_part" ]] && continue
        [[ "$flower_part" =~ ^([0-9A-Fa-f]{1,4}:)*[0-9A-Fa-f]{1,4}$ ]] || return 1
        IFS=: read -r -a flower_parts <<< "$flower_part"
        flower_count=$((flower_count + ${#flower_parts[@]}))
      done
      [[ "$flower_count" -lt 8 ]] || return 1
    else
      [[ "$flower_host" =~ ^([0-9A-Fa-f]{1,4}:){7}[0-9A-Fa-f]{1,4}$ ]] || return 1
    fi
    printf '[%s]' "$flower_host"
    return 0
  fi
  [[ ${#flower_host} -le 253 && "$flower_host" =~ ^[A-Za-z0-9]([A-Za-z0-9.-]*[A-Za-z0-9])?$ ]] || return 1
  IFS=. read -r -a flower_parts <<< "$flower_host"
  for flower_part in "${flower_parts[@]}"; do
    [[ ${#flower_part} -le 63 && "$flower_part" =~ ^[A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?$ ]] || return 1
  done
  if [[ "$flower_host" =~ ^[0-9.]+$ ]]; then
    [[ ${#flower_parts[@]} == 4 ]] || return 1
    for flower_part in "${flower_parts[@]}"; do
      [[ "$flower_part" =~ ^(0|[1-9][0-9]{0,2})$ ]] && ((10#$flower_part <= 255)) || return 1
    done
  fi
  printf '%s' "$flower_host"
}

flower_curl_options=(--fail --show-error --silent --location
  --proto '=https' --proto-redir '=https' --tlsv1.2 --connect-timeout 30 --max-time 600)
# Explicit environment settings, including empty values, take priority.
# scutil is read-only; PAC and proxy authentication are intentionally not used.
if [[ -z "${HTTPS_PROXY+x}${https_proxy+x}${ALL_PROXY+x}${all_proxy+x}" ]]; then
  if flower_proxy_settings="$(/usr/sbin/scutil --proxy 2>/dev/null)"; then
    flower_proxy_enabled='' flower_proxy_host='' flower_proxy_port='' flower_proxy_fields=0
    flower_proxy_pattern='^[[:space:]]*(HTTPSEnable|HTTPSProxy|HTTPSPort)[[:space:]]*:[[:space:]]*([^[:space:]]+)[[:space:]]*$'
    while IFS= read -r flower_line; do
      if [[ "$flower_line" =~ $flower_proxy_pattern ]]; then
        flower_proxy_fields=$((flower_proxy_fields + 1))
        case "${BASH_REMATCH[1]}" in
          HTTPSEnable) flower_proxy_enabled="${BASH_REMATCH[2]}" ;;
          HTTPSProxy) flower_proxy_host="${BASH_REMATCH[2]}" ;;
          HTTPSPort) flower_proxy_port="${BASH_REMATCH[2]}" ;;
        esac
      fi
    done <<< "$flower_proxy_settings"
    if [[ "$flower_proxy_enabled" == 1 ]]; then
      if [[ "$flower_proxy_fields" != 3 || ! "$flower_proxy_port" =~ ^[0-9]{1,5}$ ]] ||
          ! ((10#$flower_proxy_port >= 1 && 10#$flower_proxy_port <= 65535)) ||
          ! flower_proxy_address="$(flower_proxy_host_for_url "$flower_proxy_host")"; then
        echo '系统 HTTPS 静态代理的地址或端口格式不受支持，已停止下载；请检查现有代理设置或显式设置 HTTPS_PROXY。' >&2
        exit 1
      fi
      flower_curl_options+=(--proxy "http://${flower_proxy_address}:$((10#$flower_proxy_port))")
      echo '下载将沿用 macOS 已配置的 HTTPS 静态代理。'
    fi
  fi
fi

echo "正在下载小花 v$flower_version 安装包…"
if ! /usr/bin/curl "${flower_curl_options[@]}" --output "$flower_archive" "$flower_url"; then
  echo '下载未完成，未运行安装器。请检查网络或 Release 下载地址后再试。' >&2
  exit 1
fi
flower_actual_sha="$(/usr/bin/shasum -a 256 "$flower_archive")"
if [[ "${flower_actual_sha%% *}" != "$flower_expected_sha" ]]; then
  echo '安装包 SHA256 校验失败，已停止；未解压、未运行安装器。请联系发布者。' >&2
  exit 1
fi
echo '安装包 SHA256 校验通过。'
if ! /usr/bin/ditto -x -k "$flower_archive" "$flower_work/extracted"; then
  echo '安装包解压失败，未运行安装器。' >&2
  exit 1
fi
flower_installer="$flower_work/extracted/$flower_name/安装资源/integrated_install.sh"
if [[ ! -f "$flower_installer" || -L "$flower_installer" ]]; then
  echo '安装包缺少预期的安装入口，已停止。' >&2
  exit 1
fi

flower_log_root="$HOME/Library/Logs/RotatingFlower"
/bin/mkdir -p "$flower_log_root"
flower_log="$(/usr/bin/mktemp "$flower_log_root/install-release-v$flower_version.XXXXXX")"
echo '正在安装并检查连接…'
# Call the package's real installer, not the Finder launcher that waits for input.
# Application detection, migration, rollback and hardware checks stay in the package.
set +e
/bin/bash "$flower_installer" install </dev/null > "$flower_log" 2>&1
flower_result=$?
set -e
/bin/cat "$flower_log"
case "$flower_result" in
  0) echo '安装成功：已启用的应用、旋转与提醒灯均通过自检。' ;;
  5) echo '安装已完成，等待应用打开或初始化（退出码 5）。按上方“等待应用”提示操作即可，后台会自动重试连接，无需重新安装。' ;;
  3) echo '后台已安装，但 USB 连接或应用状态自检未通过（退出码 3）；请查看上方原因，不能视为全部就绪。' ;;
  4) echo '控制板尚不支持提醒灯（退出码 4）；请联系提供者更新硬件或固件，本安装器不会烧录。' ;;
  *) echo "安装未完成（退出码 ${flower_result}），请保留日志。" >&2 ;;
esac
if [[ "$flower_result" != 0 && "$flower_result" != 4 && "$flower_result" != 5 ]]; then
  echo '若提示 launchctl 或串口权限被拒绝，请停止在相同受限环境反复尝试；通过 Codex 的正常权限申请流程授权，或在系统“终端”运行此脚本。不要使用 sudo 或关闭系统安全设置。' >&2
fi
printf '详细记录：%s\n' "$flower_log"
exit "$flower_result"
