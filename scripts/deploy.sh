#!/usr/bin/env bash
# 拉取注册表 → 构建索引 → 拉取前端 → 打包前端（nginx 直读 dist）
set -euo pipefail

REGISTRY="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SITE="${CELLIUM_SITE_DIR:-$REGISTRY/../cellium-components-web}"

# 部署会在 public/ 里生成临时数据，构建完清掉，保持前端仓库干净
cleanup_data() {
  rm -rf "$SITE/public/data/c" "$SITE/public/pkg"
  if [ -d "$SITE/.git" ]; then
    git -C "$SITE" checkout -- public/data 2>/dev/null || true
  fi
}

cd "$REGISTRY"
if [ -d .git ] && git rev-parse --abbrev-ref '@{u}' >/dev/null 2>&1; then
  git pull --ff-only --quiet || echo "! git pull 注册表失败，继续用本地内容"
fi

if [ ! -d "$SITE" ]; then
  echo "✗ 前端目录不存在: $SITE（可用 CELLIUM_SITE_DIR 指定）" >&2
  exit 1
fi
if [ ! -d "$SITE/node_modules" ]; then
  echo "✗ 前端依赖未安装（$SITE/node_modules 不存在），中止：否则只会更新 JSON 不重建前端" >&2
  exit 1
fi

# 前端是独立仓库，不拉的话前端改版永远上不了线
cleanup_data
if [ -d "$SITE/.git" ]; then
  git -C "$SITE" pull --ff-only --quiet || echo "! git pull 前端失败，继续用本地内容"
fi

node scripts/build.mjs --tolerant --out "$SITE/public"

( cd "$SITE" && npm run build --silent )

cleanup_data

echo "✓ 发布完成 $(date '+%F %T')"
