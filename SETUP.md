# 换电脑继续维护 · 交接指南

> 结论先说：**代码、配置、数据、看板、部署流程全在 GitHub 仓库里，新电脑只需要 Git + Python 3 就能接手。**
> 但有 4 样东西只存在于当前这台机器，不会跟着仓库走——见第 3 节。

---

## 1. 新电脑上手（三步）

### 第 1 步：装环境

| 需要 | 版本 | 说明 |
| --- | --- | --- |
| Git | 任意较新版本 | Windows 装 Git for Windows（自带 Git Bash） |
| Python | 3.8 或更高（推荐 3.11+） | 只用标准库，不需要 pip install 任何东西 |

Windows 装 Python 时**务必勾选 `Add python.exe to PATH`**，否则脚本找不到解释器。

### 第 2 步：克隆仓库

```bash
git clone https://github.com/Licop2022/lecture-radar.git
cd lecture-radar
```

仓库是 public，clone 不需要登录。

> 若 `clone` 报 `schannel: server closed abruptly (missing close_notify)`，**先别怀疑凭据或代理**——这是 Git for Windows 的 schannel 后端在该网络下走 HTTP/2 被中断。加一个参数即可：
> ```bash
> git -c http.version=HTTP/1.1 clone https://github.com/Licop2022/lecture-radar.git
> cd lecture-radar && git config http.version HTTP/1.1   # 固化，后续 fetch/push 都走 1.1
> ```

### 第 3 步：验证能跑

```bash
python scripts/lecture_hub.py list   # 应列出现有 7 条讲座
python scripts/lecture_hub.py render # 重新生成 index.html
bash scripts/publish.sh              # 完整发布流程（推荐每次都用这个）
```

> macOS / Linux 上把 `python` 换成 `python3` 即可。`publish.sh` 会自动探测 `python3 → python → py`。

---

## 2. 首次推送要配 GitHub 凭据

新电脑**没有**旧机器的登录状态，第一次 `git push` 一定会要求认证。二选一：

### 方案 A：SSH（推荐，一劳永逸）

```bash
ssh-keygen -t ed25519 -C "your-email@example.com"     # 一路回车
cat ~/.ssh/id_ed25519.pub                              # 复制输出
```

把输出的公钥粘到 GitHub → Settings → SSH and GPG keys → New SSH key，然后：

```bash
git remote set-url origin git@github.com:Licop2022/lecture-radar.git
ssh -T git@github.com     # 看到 "Hi Licop2022!" 就通了
```

### 方案 B：Personal Access Token（PAT）

1. GitHub → Settings → Developer settings → Personal access tokens → **Fine-grained tokens** → Generate new token
2. Repository access 选 `licop2022/lecture-radar`
3. Permissions → Repository permissions → **Contents: Read and write**（只要这一项）
4. 生成后复制 `github_pat_...`

推送时弹出认证窗口：用户名填 GitHub 用户名，密码填 **token**（不是账号密码）。
想免去每次输入：

```bash
git config credential.helper store
```

⚠️ 这会把 token 明文存在用户目录下。公用电脑上别开。

---

## 3. 只在这台机器上、不会跟过去的东西

| 项目 | 为什么不跟过去 | 新电脑怎么补 |
| --- | --- | --- |
| **定时采集（12:30 / 20:30）** | WorkBuddy 自动化是绑定本机的本地任务 | 在新的 WorkBuddy 里按 [`automation/collect-prompt.md`](automation/collect-prompt.md) 重建两条 |
| **Git 凭据** | 存在 `~/.workbuddy/.git-credentials`，是机器级文件 | 按第 2 节重新认证 |
| **提交身份** | `user.name/email` 写在 `.git/config`，不入库 | `publish.sh` 会自动补设 `Lecture Radar <lecture-radar@localhost>`，也可手动 `git config` |
| **代理设置** | `http.proxy` 同样在 `.git/config` | 需要代理时：`git config http.proxy http://127.0.0.1:端口` |
| **个人记忆与偏好** | `.workbuddy/` 被 `.gitignore` 排除 | 如要保留，把 `.workbuddy/memory/` 整个目录拷过去 |

`.workbuddy/memory/` 里存的是采集口径、用户偏好、已验证的网址结论，**对后续维护很有价值**，建议用 U 盘或网盘拷一份过去。

---

## 4. 两台电脑交替使用的规则

1. **采集任务只在一台机器上跑。** 两台同时跑会让同一条讲座各录一次、各自推送、互相覆盖。换主力机后，把旧机器的两条自动化**暂停**。
2. **每次开工前先同步。** `bash scripts/publish.sh` 已内置 `fetch` + 自动 `rebase`，正常情况不用手动 `git pull`。
3. **数据类改动尽量只在主力机上做。** 手改 `data/lectures.json` 后如果另一台也改过同一行，rebase 会冲突并停下报错，需要手动解决。
4. **改代码/模板无所谓。** 冲突了按提示 `git status` 看文件、改完 `git add` + `git rebase --continue` 即可。

---

## 5. 日常命令速查

```bash
bash scripts/publish.sh                          # 同步 → 清理 → 渲染 → 提交 → 推送（最常用）

python scripts/lecture_hub.py add data/patch.json   # 手工录入一批讲座
python scripts/lecture_hub.py list                  # 看库里有什么
python scripts/lecture_hub.py render                # 只重新生成看板（不发布）
python scripts/lecture_hub.py prune                 # 只清理过期记录

git log --oneline -5        # 看最近提交
git status                  # 看工作区状态
curl -s https://licop2022.github.io/lecture-radar/ | grep -c first_seen   # 数线上有几条
```

---

## 6. 出问题怎么查

| 现象 | 原因 | 处理 |
| --- | --- | --- |
| `git clone` 报 `schannel: server closed abruptly (missing close_notify)` | Git for Windows 的 schannel 后端走 HTTP/2 时被网络中断，**与凭据、代理无关** | `git -c http.version=HTTP/1.1 clone …`，进仓库后 `git config http.version HTTP/1.1` 固化 |
| `git clone` 报 `schannel: failed to receive handshake` | 网络需要代理，但新克隆里还没有任何代理配置 | `HTTPS_PROXY=http://127.0.0.1:端口 git clone https://github.com/Licop2022/lecture-radar.git`，或先 `git config --global http.proxy http://127.0.0.1:端口` |
| `找不到 Python 3.8+ 解释器` | Python 没装或没进 PATH | 重装并勾选 Add to PATH；或用 `py` 启动器 |
| `推送失败` + `CONNECT tunnel failed` | 需要代理但没配 | `git config http.proxy http://127.0.0.1:端口` |
| `Authentication failed` | token 过期 / 权限不足 | 重新生成 PAT，确认 Contents 是 Read and write |
| `rebase 失败` | 两台机器改了同一处 | `git status` 找冲突文件，手动改完 `git add .` + `git rebase --continue` |
| 推送成功但网页没变 | Actions 还在跑 / 缓存 | 等 1–2 分钟；到仓库 Actions 页看最近一次是否绿勾 |
| 网页 404 | Pages 源被改回了「Deploy from a branch」 | 仓库 Settings → Pages → Source 必须选 **GitHub Actions** |

---

## 7. 万一要换仓库 / 换账号

```bash
git remote set-url origin https://github.com/新账号/新仓库.git
git push -u origin main
```

然后到新仓库 Settings → Pages → Source 选 **GitHub Actions**，等 `static.yml` 跑完即可。
注意：`scripts/publish.sh` 和本文件里写死了线上地址 `https://licop2022.github.io/lecture-radar/`，换仓库后记得一并改。
