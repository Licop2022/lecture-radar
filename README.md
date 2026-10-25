# 讲座雷达 · 微信公众号讲座信息收集

面向广东工业大学（重点：自动化学院、信息工程学院）的讲座信息汇总工具。每天 12:30 / 20:30 自动采集一轮公众号与校方官网的讲座预告，落库去重后渲染成本地网页看板。

## 特点

- **全校范围**：校级 9 个来源 + 17 个学院（不含物理与光电工程学院），公众号优先、官网栏目兜底
- **校内优先**：按参与地点判定校内 / 校外 / 待确认，广工各校区与工学一号馆、大讲堂等校内场所优先收录
- **面向学院分开导航**：自动化学院、信息工程学院各占一个独立入口，另设「其他院系 / 全校」兜底
- **学分条标记**：自动抽取「学术条 / 实践条 / 实践时长 / 素拓条」，看板可一键筛出带条的活动
- **分类导航**：按时间 / 学分条 / 面向学院 / 参与范围（校内·校外·待确认）/ 受众身份 / 类型（学术报告·学术会议·论坛会议·宣讲招聘·学科竞赛）/ 来源（公众号·官网）多维导航，每项带实时计数
- **三种视图**：卡片、时间轴（按日期分组）、表格，一键切换
- **自动去重**：标题归一化 + 日期生成指纹，同一场讲座在不同公众号重复出现只留一条
- **纯本地运行**：数据是 `data/lectures.json`，看板是单个 `index.html`，不依赖任何服务端
- **线上同步**：`scripts/publish.sh` 一条命令完成渲染→提交→推送，GitHub Actions 自动重新部署 Pages

## 换电脑继续维护

代码、配置、数据、部署流程都在仓库里，装好 Git + Python 3 后 `git clone` 即可接手。
定时采集任务、Git 凭据、个人记忆是**本机文件**，不随仓库走，需要单独补。完整步骤见 **[SETUP.md](SETUP.md)**。

## 目录结构

```
config.json                  关注名单、检索参数、来源白名单
scripts/lecture_hub.py       采集中枢：add / render / prune / list
scripts/publish.sh           一键发布：同步→清理→渲染→提交→推送（跨机通用）
dashboard/template.html      看板模板（占位符替换）
data/lectures.json           讲座主库
index.html                   渲染产物，直接用浏览器打开
automation/collect-prompt.md 定时采集任务的 prompt 备份，换机时照它重建
SETUP.md                     换电脑 / 交接指南
```

## 用法

```bash
# 录入（JSON 数组，字段见下）
python scripts/lecture_hub.py add batch.json

# 清理超过 retention_days 的过期记录
python scripts/lecture_hub.py prune

# 渲染看板
python scripts/lecture_hub.py render

# 查看库内记录
python scripts/lecture_hub.py list
```

记录字段：`title` `speaker` `date`(YYYY-MM-DD) `time_text` `location` `org` `source` `url` `summary` `tags` `credit` `audience` `college`

- `credit`：可获得的「条」，如 `学术条`、`实践条`、`学术条、实践条`；没有则留空。
- `audience`：面向群体，如 `研究生`、`全校学生、研究生`；原文无线索则留空，不做推测。
- `college`：面向学院，仅填 `自动化学院` 或 `信息工程学院`；其他院系或无法确认时留空。
- `campus` / `on_campus`：由 `location` 自动判定，无需手填。
- 日期不确定时 `date` 留空，`time_text` 照抄原文表述。

## 已知限制

微信公众号没有开放接口，无法按账号拉取全部历史推文。本项目采用「关键词定向检索 + 官网栏目抓取 + 本地去重」的方式，对讲座预告这类高频内容够用，但未被搜索引擎收录的推文可能会漏。
