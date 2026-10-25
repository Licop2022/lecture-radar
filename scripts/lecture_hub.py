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
    with open(DATA_PATH, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)


def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


FIELDS = ["title", "speaker", "date", "time_text", "location", "org", "source", "url", "summary"]


def normalize_record(raw):
    rec = {}
    for k in FIELDS:
        v = raw.get(k)
        rec[k] = (v or "").strip() if isinstance(v, str) else ""
    tags = raw.get("tags") or []
    if isinstance(tags, str):
        tags = [t.strip() for t in re.split(r"[,，;；/]", tags) if t.strip()]
    rec["tags"] = tags
    # credit：可获得的「条」/学分，如 学术条、事件条、实践时长；空串表示无
    c = raw.get("credit")
    if isinstance(c, bool):
        rec["credit"] = "学术条" if c else ""
    else:
        rec["credit"] = (c or "").strip()
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
    with open(LOG_PATH, "a", encoding="utf-8") as f:
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
        "rendered_at": iso(now()),
        "scope": cfg.get("scope", ""),
        "watch_count": len(wl),
        "watchlist": wl[:8],
    }
    html = tpl.replace("__LECTURES_JSON__", json.dumps(lectures, ensure_ascii=False))
    html = html.replace("__META_JSON__", json.dumps(meta, ensure_ascii=False))
    with open(OUT_PATH, "w", encoding="utf-8") as f:
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
