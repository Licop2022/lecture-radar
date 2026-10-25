# 讲座雷达 · 微信公众号讲座信息收集

面向广东工业大学（重点：自动化学院）的讲座信息汇总工具。每天 08:00 / 20:00 自动采集一轮公众号与校方官网的讲座预告，落库去重后渲染成本地网页看板。

## 特点

- **全校范围**：校级 9 个来源 + 18 个学院，公众号优先、官网栏目兜底
- **学分条标记**：自动抽取「学术条 / 实践条 / 实践时长 / 素拓条」，看板可一键筛出带条的活动
- **自动去重**：标题归一化 + 日期生成指纹，同一场讲座在不同公众号重复出现只留一条
- **纯本地运行**：数据是 `data/lectures.json`，看板是单个 `index.html`，不依赖任何服务端

## 目录结构

```
config.json                  关注名单、检索参数、来源白名单
scripts/lecture_hub.py       采集中枢：add / render / prune / list
dashboard/template.html      看板模板（占位符替换）
data/lectures.json           讲座主库
index.html                   渲染产物，直接用浏览器打开
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

记录字段：`title` `speaker` `date`(YYYY-MM-DD) `time_text` `location` `org` `source` `url` `summary` `tags` `credit`

- `credit`：可获得的「条」，如 `学术条`、`实践条`、`学术条、实践条`；没有则留空。
- 日期不确定时 `date` 留空，`time_text` 照抄原文表述。

## 已知限制

微信公众号没有开放接口，无法按账号拉取全部历史推文。本项目采用「关键词定向检索 + 官网栏目抓取 + 本地去重」的方式，对讲座预告这类高频内容够用，但未被搜索引擎收录的推文可能会漏。
