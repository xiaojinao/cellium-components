#!/usr/bin/env bash
# 兼容入口：部署逻辑已迁至前端仓库 cellium-components-web
# 老 crontab 可以继续指向这里，不需要改；也可以直接调用前端仓库的 scripts/deploy.sh
set -euo pipefail

SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WEB="${CELLIUM_WEB_DIR:-$SELF_DIR/../../cellium-components-web}"

if [ ! -f "$WEB/scripts/deploy.sh" ]; then
  echo "✗ 找不到前端仓库部署脚本：$WEB/scripts/deploy.sh" >&2
  echo "  用 CELLIUM_WEB_DIR 指定前端仓库路径，或把 crontab 指向前端仓库的 scripts/deploy.sh" >&2
  exit 1
fi

exec bash "$WEB/scripts/deploy.sh" "$@"
