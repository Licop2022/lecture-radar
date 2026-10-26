#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""讲座信息收集中枢

子命令:
  add       从 JSON 文件或 stdin 录入讲座记录（自动去重合并）
  render    重新渲染 index.html 看板
  list      打印当前库内记录概要
  prune     清理超过 retention_days 的过期记录

记录字段（除 title 外都可缺省）:
  title, speaker, date(YYYY-MM-DD), time_text, location, org, source, url, summary, tags
"""

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(BASE, "data", "lectures.json")
CONFIG_PATH = os.path.join(BASE, "config.json")
TEMPLATE_PATH = os.path.join(BASE, "dashboard", "template.html")
OUT_PATH = os.path.join(BASE, "index.html")
LOG_PATH = os.path.join(BASE, "data", "runs.log")

TZ = timezone(timedelta(hours=8))


def now():
    return datetime.now(TZ)


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%S+08:00")


def norm(text):
    """归一化文本用于去重比对"""
    s = (text or "").lower()
    s = re.sub(r"[\s\u3000]+", "", s)
    s = re.sub(r"[「」『』【】\[\]（）()《》<>:：,，.。、·\-—_/\\|!！?？\"'“”‘’~*#]", "", s)
    return s


def make_id(rec):
    key = norm(rec.get("title", ""))[:60] + "|" + (rec.get("date") or "")[:10]
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]


def load_db():
    if os.path.exists(DATA_PATH):
        with open(DATA_PATH, "r", encoding="utf-8") as f:
            db = json.load(f)
    else:
        db = {"updated_at": None, "lectures": []}
    db.setdefault("lectures", [])
    return db


def save_db(db):
    os.makedirs(os.path.dirname(DATA_PATH), exist_ok=True)
    db["lectures"].sort(key=lambda r: (r.get("date") or "9999-99-99", r.get("time_text") or ""))
    # newline="\n"：Windows 上默认会把 \n 转成 \r\n，导致每次写库都在 git 里产生全文 diff
    with open(DATA_PATH, "w", encoding="utf-8", newline="\n") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)


def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


FIELDS = ["title", "speaker", "date", "time_text", "location", "org", "source", "url", "summary", "category", "audience", "college", "host_college", "campus"]

# 面向学院（college）：只在原文有明确「面向」表述时才认。
# 主办方是谁 ≠ 只面向谁 —— 信工主办的论坛常常面向全校研究生报名。
COLLEGE_FACING_MARKERS = {
    "自动化学院": ["面向自动化学院", "自动化学院研究生", "自动化学院学生", "自动化学院全体", "自动化学院师生"],
    "信息工程学院": ["面向信息工程学院", "信息工程学院研究生", "信息工程学院学生",
                     "信息工程学院全体", "信息工程学院师生"],
}
# 主办 / 来源学院（host_college）：学院名、品牌栏目、栏目域名都算，只表示「谁办的」
COLLEGE_HOST_MARKERS = {
    "自动化学院": ["自动化学院", "自动化学工", "汇智自动化", "自动化专业", "控制科学"],
    "信息工程学院": ["信息工程学院", "信工学院", "信研博学", "信息工程专业", "通信工程"],
}
COLLEGE_HOSTS = {
    "xxgcxy.gdut.edu.cn": "信息工程学院",
    "automation.gdut.edu.cn": "自动化学院",
}

# 校内地点判定：校区名 → 具体建筑 → 校外场所
CAMPUS_NAMES = ["大学城校区", "东风路校区", "龙洞校区", "番禺校区", "揭阳校区", "沙河校区"]
ON_CAMPUS_MARKERS = ["大讲堂", "工学一号馆", "工学二号馆", "工学四号馆", "实验四号楼", "理学馆",
                     "文化活动中心", "青春报告厅", "学术报告厅", "图书馆", "教八", "教三", "教五"]
OFF_CAMPUS_MARKERS = ["国际会议中心", "会议中心", "酒店", "会展中心", "北京", "上海", "深圳", "珠海", "佛山"]

# 受众推断：仅在原文/摘要显式出现时才标注，不臆测
AUDIENCE_RULES = [
    ("全校学生", ["全校学生", "全体学生", "全校师生", "全体师生", "全校研究生"]),
    ("研究生", ["研究生", "博士生", "硕士生", "硕博"]),
    ("本科生", ["本科生", "本科同学"]),
    ("教师", ["青年教师", "教职工", "专任教师"]),
]

# 类型推断：按关键词优先级匹配，title 命中即归类
CATEGORY_RULES = [
    ("宣讲招聘", ["宣讲", "招聘", "双选", "供需见面"]),
    ("学科竞赛", ["竞赛", "大赛", "挑战杯", "数学建模"]),
    ("论坛会议", ["论坛", "研讨会", "峰会", "圆桌", "沙龙", "工作坊"]),
    ("学术会议", ["大会", "年会", "学术会议", "会议通知"]),
    ("学术报告", ["大讲堂", "学术报告", "报告会", "讲座", "讲坛", "学术报告会"]),
]


def infer_category(title):
    t = title or ""
    for name, keys in CATEGORY_RULES:
        for k in keys:
            if k in t:
                return name
    return "其他"


def classify_location(loc):
    """返回 (campus, on_campus)。on_campus 为 True/False/None（无法判断）"""
    s = loc or ""
    if not s.strip():
        return "", None
    for c in CAMPUS_NAMES:
        if c in s:
            return c, True
    for k in ON_CAMPUS_MARKERS:
        if k in s:
            return "校内", True
    for k in OFF_CAMPUS_MARKERS:
        if k in s:
            return "校外", False
    return "", None


def infer_audience(text):
    """从标题/摘要/主办中提取受众标签，多个用顿号连接；无明确线索返回空串"""
    t = text or ""
    hits = []
    for label, keys in AUDIENCE_RULES:
        if any(k in t for k in keys):
            hits.append(label)
    return "、".join(hits)


def _match_first(blob, table):
    """在文本中找出位置最靠前的关键词，返回它所属的学院名"""
    best, pos = "", None
    for name, keys in table.items():
        for k in keys:
            i = blob.find(k)
            if i >= 0 and (pos is None or i < pos):
                best, pos = name, i
    return best


def infer_college(title="", summary=""):
    """面向学院：只认「面向 XX 学院」这类明确表述。

    无明确表述一律留空 —— 面向全校、面向其他院系、或原文没说，都不猜。
    特别注意：**主办方不等于面向对象**。信工主办的论坛经常面向全校研究生报名，
    所以这里不看主办单位（org）、不看品牌栏目、不看域名，那些归 host_college。
    """
    return _match_first(" ".join([title or "", summary or ""]), COLLEGE_FACING_MARKERS)


def infer_host_college(title="", org="", source="", url=""):
    """主办 / 来源学院：从主办单位、品牌栏目、来源与栏目域名判断。

    只表示「谁办的」，不代表只面向谁 —— 看板的「面向学院」导航把它作为
    「与该学院相关」的兜底，受众拆分（gradAuds）仍然只看 college。
    """
    name = _match_first(" ".join([title or "", org or "", source or ""]), COLLEGE_HOST_MARKERS)
    if name:
        return name
    host = re.sub(r"^https?://", "", url or "").split("/")[0].lower()
    for h, n in COLLEGE_HOSTS.items():
        if host.endswith(h):
            return n
    return ""


def normalize_record(raw):
    rec = {}
    for k in FIELDS:
        v = raw.get(k)
        rec[k] = (v or "").strip() if isinstance(v, str) else ""
    tags = raw.get("tags") or []
    if isinstance(tags, str):
        tags = [t.strip() for t in re.split(r"[,，;；/]", tags) if t.strip()]
    rec["tags"] = tags
    # credit：可获得的「条」/学分，如 学术条、实践条、实践时长；空串表示无
    c = raw.get("credit")
    if isinstance(c, bool):
        rec["credit"] = "学术条" if c else ""
    else:
        rec["credit"] = (c or "").strip()
    if not rec.get("category"):
        rec["category"] = infer_category(rec["title"])
    # 校内/校外判定：写回 campus（校区名或「校内」「校外」）与 on_campus（True/False/None）
    campus, on_campus = classify_location(rec["location"])
    rec["campus"] = campus
    rec["on_campus"] = on_campus
    # 受众：原文未写明时按标题/摘要/主办显式线索推断
    if not rec["audience"]:
        rec["audience"] = infer_audience(" ".join([rec["title"], rec["summary"], rec["org"]]))
    # 面向学院：只认明确「面向 X 学院」的表述，免得把主办方当成受众
    if not rec["college"]:
        rec["college"] = infer_college(rec["title"], rec["summary"])
    # 主办 / 来源学院：谁办的（不等于只面向谁）
    if not rec["host_college"]:
        rec["host_college"] = infer_host_college(rec["title"], rec["org"], rec["source"], rec["url"])
    # 日期兜底：从 time_text 里抠 YYYY-MM-DD 或 YYYY年M月D日
    if not rec["date"]:
        m = re.search(r"(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})", rec["time_text"] or rec["title"])
        if m:
            rec["date"] = "%04d-%02d-%02d" % (int(m.group(1)), int(m.group(2)), int(m.group(3)))
    if rec["date"]:
        m = re.match(r"(\d{4})-(\d{1,2})-(\d{1,2})", rec["date"])
        if m:
            rec["date"] = "%04d-%02d-%02d" % (int(m.group(1)), int(m.group(2)), int(m.group(3)))
    return rec


def cmd_add(args):
    raw_text = ""
    if args.file and args.file != "-":
        with open(args.file, "r", encoding="utf-8") as f:
            raw_text = f.read()
    else:
        raw_text = sys.stdin.read()
    payload = json.loads(raw_text)
    items = payload if isinstance(payload, list) else payload.get("lectures", [payload])

    db = load_db()
    index = {r["id"]: r for r in db["lectures"]}
    stamp = iso(now())
    added, updated, skipped = 0, 0, 0

    for raw in items:
        rec = normalize_record(raw)
        if not rec["title"]:
            skipped += 1
            continue
        rid = make_id(rec)
        rec["id"] = rid
        if rid in index:
            old = index[rid]
            changed = False
            for k in FIELDS:
                if rec[k] and rec[k] != old.get(k):
                    old[k] = rec[k]
                    changed = True
            merged_tags = sorted(set(old.get("tags", [])) | set(rec["tags"]))
            if merged_tags != old.get("tags", []):
                old["tags"] = merged_tags
                changed = True
            # credit 合并：多种「条」并存时用顿号拼接
            old_credit = old.get("credit", "") or ""
            new_credit = rec.get("credit", "") or ""
            if new_credit:
                existing = {x.strip() for x in re.split(r"[、,，/]", old_credit) if x.strip()}
                if new_credit not in existing:
                    old["credit"] = (old_credit + "、" + new_credit) if old_credit else new_credit
                    changed = True
            # campus / on_campus 始终随 location 重算，避免历史记录残留旧判定
            ncampus, non = classify_location(old.get("location"))
            if old.get("campus") != ncampus or old.get("on_campus") != non:
                old["campus"], old["on_campus"] = ncampus, non
                changed = True
            old["last_seen"] = stamp
            updated += 1 if changed else 0
            skipped += 0 if changed else 1
        else:
            rec["first_seen"] = stamp
            rec["last_seen"] = stamp
            index[rid] = rec
            added += 1

    db["lectures"] = list(index.values())
    db["updated_at"] = stamp
    save_db(db)

    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8", newline="\n") as f:
        f.write("%s  add=%d update=%d skip=%d total=%d\n" % (stamp, added, updated, skipped, len(db["lectures"])))

    print("新增 %d 条，更新 %d 条，跳过 %d 条，库内共 %d 条" % (added, updated, skipped, len(db["lectures"])))


def cmd_prune(args):
    cfg = load_config()
    days = args.days or cfg.get("settings", {}).get("retention_days", 60)
    today = now().date()
    db = load_db()
    keep, drop = [], 0
    for r in db["lectures"]:
        d = r.get("date") or ""
        try:
            dt = datetime.strptime(d[:10], "%Y-%m-%d").date()
        except ValueError:
            keep.append(r)
            continue
        if (today - dt).days > days:
            drop += 1
        else:
            keep.append(r)
    db["lectures"] = keep
    save_db(db)
    print("清理过期记录 %d 条，剩余 %d 条" % (drop, len(keep)))


def cmd_list(args):
    db = load_db()
    print("更新时间：%s  共 %d 条" % (db.get("updated_at") or "-", len(db["lectures"])))
    for r in db["lectures"]:
        print("  [%s] %s | %s | %s" % (r.get("date") or "?", r.get("title", "")[:40], r.get("org") or r.get("source") or "-", r.get("id")))


def cmd_render(args):
    db = load_db()
    cfg = load_config()
    today = now().date()
    lectures = []
    for r in db["lectures"]:
        rec = dict(r)
        if not rec.get("category"):
            rec["category"] = infer_category(rec.get("title", ""))
        # 兼容历史记录：现场重算校内归属与受众
        if not rec.get("campus") or "on_campus" not in rec:
            rcampus, ron = classify_location(rec.get("location"))
            rec["campus"] = rec.get("campus") or rcampus
            rec["on_campus"] = ron
        if not rec.get("audience"):
            rec["audience"] = infer_audience(" ".join([
                rec.get("title", ""), rec.get("summary", ""), rec.get("org", "")]))
        if not rec.get("college"):
            rec["college"] = infer_college(rec.get("title", ""), rec.get("summary", ""))
        if not rec.get("host_college"):
            rec["host_college"] = infer_host_college(rec.get("title", ""), rec.get("org", ""),
                                                     rec.get("source", ""), rec.get("url", ""))
        rec["src_type"] = "wechat" if "mp.weixin.qq.com" in (rec.get("url") or "") else "web"
        d = r.get("date") or ""
        try:
            dt = datetime.strptime(d[:10], "%Y-%m-%d").date()
            delta = (dt - today).days
            if delta == 0:
                rec["status"], rec["status_text"] = "today", "今天"
            elif delta == 1:
                rec["status"], rec["status_text"] = "soon", "明天"
            elif delta > 1:
                rec["status"], rec["status_text"] = "upcoming", "%d天后" % delta
            else:
                rec["status"], rec["status_text"] = "past", "已结束"
        except ValueError:
            rec["status"], rec["status_text"] = "unknown", "待确认"
        # 是否 24 小时内新收录
        fs = r.get("first_seen")
        rec["is_new"] = False
        if fs:
            try:
                rec["is_new"] = (now() - datetime.strptime(fs[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=TZ)) < timedelta(hours=24)
            except ValueError:
                pass
        lectures.append(rec)

    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        tpl = f.read()

    wl = cfg.get("watchlist", [])
    if isinstance(wl, dict):
        wl = [x for v in wl.values() if isinstance(v, list) for x in v]
    meta = {
        "updated_at": db.get("updated_at"),
        # 不写 render 时间戳：看板内容应只随数据变化，否则每次渲染都会产生无意义提交
        "scope": cfg.get("scope", ""),
        "watch_count": len(wl),
        "watchlist": wl[:8],
        "focus_audience": cfg.get("focus_audience", []),
        "college_groups": (cfg.get("college_scope") or {}).get("groups", []),
        "campuses": (cfg.get("campus_scope") or {}).get("campuses", []),
    }
    html = tpl.replace("__LECTURES_JSON__", json.dumps(lectures, ensure_ascii=False))
    html = html.replace("__META_JSON__", json.dumps(meta, ensure_ascii=False))
    # 同上：统一用 LF，保证与仓库里的 index.html 字节一致
    with open(OUT_PATH, "w", encoding="utf-8", newline="\n") as f:
        f.write(html)
    print("已渲染 %s（%d 条记录）" % (OUT_PATH, len(lectures)))


def main():
    p = argparse.ArgumentParser(description="讲座信息收集中枢")
    sub = p.add_subparsers(dest="cmd", required=True)

    pa = sub.add_parser("add", help="录入讲座记录")
    pa.add_argument("file", nargs="?", default="-", help="JSON 文件路径，默认读 stdin")
    pa.set_defaults(func=cmd_add)

    pp = sub.add_parser("prune", help="清理过期记录")
    pp.add_argument("--days", type=int, default=None)
    pp.set_defaults(func=cmd_prune)

    pl = sub.add_parser("list", help="列出库内记录")
    pl.set_defaults(func=cmd_list)

    pr = sub.add_parser("render", help="渲染看板")
    pr.set_defaults(func=cmd_render)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
