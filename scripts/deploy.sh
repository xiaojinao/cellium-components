#!/usr/bin/env bash
# 拉取注册表 → 拉取前端 → 构建索引 → 写进前端 dist（nginx 直读 dist）
set -euo pipefail

REGISTRY="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SITE="${CELLIUM_SITE_DIR:-$REGISTRY/../cellium-components-web}"

cd "$REGISTRY"
if [ -d .git ] && git rev-parse --abbrev-ref '@{u}' >/dev/null 2>&1; then
  git pull --ff-only --quiet || echo "! git pull 注册表失败，继续用本地内容"
fi

if [ ! -d "$SITE" ]; then
  echo "✗ 前端目录不存在: $SITE（可用 CELLIUM_SITE_DIR 指定）" >&2
  exit 1
fi

# 前端是独立仓库，不拉的话前端改版永远上不了线
if [ -d "$SITE/.git" ]; then
  git -C "$SITE" pull --ff-only --quiet || echo "! git pull 前端失败，继续用本地内容"
fi

# 只有 dist 不存在、或前端源码比 dist 更新时才重新打包；纯数据更新不需要构建
need_build=0
if [ ! -f "$SITE/dist/index.html" ]; then
  need_build=1
elif [ -n "$(find "$SITE/src" "$SITE/public" "$SITE/index.html" "$SITE/package.json" "$SITE/vite.config.js" \
  -newer "$SITE/dist/index.html" -print -quit 2>/dev/null)" ]; then
  need_build=1
fi

if [ "$need_build" = 1 ]; then
  if [ ! -d "$SITE/node_modules" ]; then
    echo "✗ 需要构建前端，但依赖未安装（$SITE/node_modules 不存在）。先执行：cd $SITE && npm ci" >&2
    exit 1
  fi
  ( cd "$SITE" && npm run build --silent )
fi

# 数据是运行时 fetch 的静态 JSON，直接写进 dist，不需要再打包前端
if command -v python3 >/dev/null 2>&1; then PY=python3; else PY=python; fi
"$PY" scripts/build.py --tolerant --out "$SITE/dist"

echo "✓ 发布完成 $(date '+%F %T')"
