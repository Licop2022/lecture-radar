#!/usr/bin/env bash
# 一键发布：同步远端 → 清理过期记录 → 渲染看板 → 提交 → 推送 GitHub
# GitHub Actions 收到提交后会自动重新部署 Pages
#
# 设计目标：任何一台装了 Git + Python 3.8+ 的机器都能直接跑，不依赖特定路径。
set -euo pipefail

cd "$(dirname "$0")/.."

# ---------- 0. 找 Python：python3 → python → py ----------
PY=""
for c in python3 python py; do
  if command -v "$c" >/dev/null 2>&1; then
    if "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3,8) else 1)' >/dev/null 2>&1; then
      PY="$c"; break
    fi
  fi
done
if [ -z "$PY" ]; then
  echo "找不到 Python 3.8+ 解释器。请先安装 Python 3（Windows 勾选 Add to PATH）。" >&2
  exit 1
fi

# ---------- 0b. 提交身份缺失时补一个仓库级身份 ----------
if ! git config user.email >/dev/null 2>&1; then
  git config user.name "Lecture Radar"
  git config user.email "lecture-radar@localhost"
  echo "   已为本仓库补设提交身份：Lecture Radar <lecture-radar@localhost>"
fi

# ---------- 1. 同步远端（两台电脑交替使用时避免互相覆盖） ----------
echo "== 1/5 同步远端 =="
HAS_REMOTE=0
if git remote get-url origin >/dev/null 2>&1; then
  HAS_REMOTE=1
  if git fetch -q origin main 2>/dev/null; then
    if ! git merge-base --is-ancestor origin/main HEAD 2>/dev/null; then
      echo "   远端有新提交，先 rebase 到本地"
      if ! git pull --rebase --autostash -q origin main; then
        echo "   自动 rebase 失败：请先手动解决冲突（git status 查看），再重新发布。" >&2
        exit 1
      fi
    else
      echo "   已是最新"
    fi
  else
    echo "   警告：拉取远端失败（网络 / 代理 / 权限），本轮只在本地提交"
  fi
else
  echo "   未配置 origin，跳过同步"
fi

# ---------- 2. 清理过期 ----------
echo "== 2/5 清理过期记录 =="
"$PY" scripts/lecture_hub.py prune

# ---------- 3. 渲染 ----------
echo "== 3/5 渲染看板 =="
"$PY" scripts/lecture_hub.py render

# ---------- 4. 提交 ----------
echo "== 4/5 检查改动 =="
if git diff --quiet && git diff --cached --quiet; then
  echo "   没有变化，跳过提交"
  exit 0
fi
git add -A
git commit -q -m "数据更新：$(date '+%Y-%m-%d %H:%M')"

# ---------- 5. 推送 ----------
if [ "$HAS_REMOTE" = "0" ]; then
  echo "   已提交在本地（未配置远端，不推送）"
  exit 0
fi
echo "== 5/5 推送到 GitHub =="
if ! git push -q origin main; then
  echo "" >&2
  echo "推送失败：改动已提交在本地，只是没上传。" >&2
  echo "  常见原因与处理：" >&2
  echo "  · 需要代理：git config http.proxy http://127.0.0.1:你的端口" >&2
  echo "  · 凭据失效：重新配置 PAT 或改用 SSH（见 SETUP.md）" >&2
  echo "  · 网络问题：稍后执行 bash scripts/publish.sh 重试" >&2
  exit 1
fi
echo "   已发布，线上大约 1 分钟后更新：https://licop2022.github.io/lecture-radar/"
