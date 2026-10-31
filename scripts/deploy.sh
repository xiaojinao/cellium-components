#!/usr/bin/env bash
# 拉取最新提交 → 校验构建 → 重新打包前端（站点由 nginx 直读 dist）
set -euo pipefail

REGISTRY="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SITE="${CELLIUM_SITE_DIR:-$REGISTRY/../cellium-components/frontend}"

cd "$REGISTRY"
if [ -d .git ] && git rev-parse --abbrev-ref '@{u}' >/dev/null 2>&1; then
  git pull --ff-only --quiet || echo "! git pull 失败，继续用本地内容"
fi

node scripts/build.mjs --tolerant --out "$SITE/public"

if [ -d "$SITE/node_modules" ]; then
  ( cd "$SITE" && npm run build --silent )
else
  echo "! 前端未安装依赖，跳过 npm run build（$SITE/node_modules 不存在）"
fi

echo "✓ 发布完成 $(date '+%F %T')"
