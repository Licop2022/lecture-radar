#!/usr/bin/env bash
# 一键发布：清理过期记录 → 渲染看板 → 提交 → 推送 GitHub
# GitHub Actions 收到提交后会自动重新部署 Pages
set -euo pipefail

cd "$(dirname "$0")/.."

# 优先用 PATH 里的 python，找不到就用 WorkBuddy 内置解释器
if command -v python >/dev/null 2>&1; then
  PY=python
elif [ -x "C:/Users/86134/.workbuddy/binaries/python/versions/3.13.12/python.exe" ]; then
  PY="C:/Users/86134/.workbuddy/binaries/python/versions/3.13.12/python.exe"
else
  echo "找不到 Python 解释器" >&2
  exit 1
fi

echo "== 1/4 清理过期记录 =="
"$PY" scripts/lecture_hub.py prune

echo "== 2/4 渲染看板 =="
"$PY" scripts/lecture_hub.py render

echo "== 3/4 检查改动 =="
if git diff --quiet && git diff --cached --quiet; then
  echo "   没有变化，跳过提交"
  exit 0
fi

git add -A
git commit -q -m "数据更新：$(date '+%Y-%m-%d %H:%M')"

echo "== 4/4 推送到 GitHub =="
git push -q origin main
echo "   已发布，线上大约 1 分钟后更新：https://licop2022.github.io/lecture-radar/"
