#!/usr/bin/env python3
"""
hn-monitor.py — HN Show HN 投稿のコメント監視ツール

使用方法:
  python3 tools/hn-monitor.py <item_id>
  python3 tools/hn-monitor.py <item_id> --watch   # 5分おきに監視
  python3 tools/hn-monitor.py <item_id> --summary # スコア・コメント数のみ

投稿後にURLから item_id を取得:
  https://news.ycombinator.com/item?id=<item_id>
"""

import sys
import json
import time
import argparse
import urllib.request
from datetime import datetime, timezone

BASE_URL = "https://hacker-news.firebaseio.com/v0"


def fetch(path: str) -> dict | None:
    url = f"{BASE_URL}/{path}.json"
    try:
        with urllib.request.urlopen(url, timeout=8) as r:
            data = r.read()
            if not data or data == b'null':
                return None
            return json.loads(data)
    except Exception as e:
        print(f"[WARN] fetch failed: {path} — {e}", file=sys.stderr)
        return None


def clean_html(text: str) -> str:
    """HN HTMLを簡易的にプレーンテキストに変換"""
    replacements = [
        ('<p>', '\n'), ('</p>', ''), ('<br>', '\n'),
        ('<i>', ''), ('</i>', ''), ('<b>', ''), ('</b>', ''),
        ('<code>', '`'), ('</code>', '`'),
        ('&#x27;', "'"), ('&amp;', '&'), ('&gt;', '>'),
        ('&lt;', '<'), ('&quot;', '"'), ('&#x2F;', '/'),
    ]
    for old, new in replacements:
        text = text.replace(old, new)
    # URLタグを簡易処理
    import re
    text = re.sub(r'<a href="([^"]+)"[^>]*>([^<]*)</a>', r'\2 (\1)', text)
    text = re.sub(r'<[^>]+>', '', text)
    return text.strip()


def format_time(unix_ts: int) -> str:
    dt = datetime.fromtimestamp(unix_ts, tz=timezone.utc)
    # UTC -> JST (+9)
    from datetime import timedelta
    jst = dt + timedelta(hours=9)
    return jst.strftime('%m/%d %H:%M JST')


def print_comment(cid: int, depth: int = 0, seen: set = None) -> int:
    if seen is None:
        seen = set()
    if cid in seen:
        return 0
    seen.add(cid)

    c = fetch(f"item/{cid}")
    if not c or c.get('deleted') or c.get('dead') or c.get('type') != 'comment':
        return 0

    indent = "  " * depth
    by = c.get('by', '[deleted]')
    text = clean_html(c.get('text', ''))
    ts = format_time(c.get('time', 0)) if c.get('time') else ''

    # 長すぎる場合は省略
    lines = [l for l in text.split('\n') if l.strip()]
    display = '\n'.join(lines[:6])
    if len(lines) > 6:
        display += f"\n{indent}  [... {len(lines) - 6} more lines]"

    print(f"{indent}┌ {by}  ({ts})  id:{cid}")
    for line in display.split('\n'):
        print(f"{indent}│ {line}")
    print()

    count = 1
    for kid in c.get('kids', []):
        time.sleep(0.05)
        count += print_comment(kid, depth + 1, seen)

    return count


def show_summary(item: dict) -> None:
    title = item.get('title', 'N/A')
    score = item.get('score', 0)
    desc = item.get('descendants', 0)
    item_id = item.get('id')
    ts = format_time(item.get('time', 0)) if item.get('time') else ''

    print(f"📊 NAIL on HN")
    print(f"   Title : {title}")
    print(f"   Score : {score} pts")
    print(f"   Comments: {desc}")
    print(f"   Posted: {ts}")
    print(f"   URL   : https://news.ycombinator.com/item?id={item_id}")
    print()


def monitor_once(item_id: int, show_comments: bool = True) -> dict:
    print(f"=== HN Monitor: item/{item_id} ({datetime.now().strftime('%H:%M:%S JST')}) ===")

    item = fetch(f"item/{item_id}")
    if not item:
        print(f"ERROR: item/{item_id} not found or null")
        return {}

    show_summary(item)

    if not show_comments:
        return item

    kids = item.get('kids', [])
    if not kids:
        print("No comments yet.")
        return item

    print(f"=== {len(kids)} top-level comment(s) ===\n")
    total = 0
    for kid in kids:
        time.sleep(0.1)
        total += print_comment(kid)

    print(f"[Total: {total} comment(s) fetched]")
    return item


def watch_mode(item_id: int, interval_min: int = 5) -> None:
    """定期監視モード — 新しいコメントを検出"""
    seen_kids: set = set()
    print(f"👁  Watching item/{item_id} (interval: {interval_min}min)")
    print("   Press Ctrl+C to stop\n")

    while True:
        item = fetch(f"item/{item_id}")
        if not item:
            print(f"[{datetime.now().strftime('%H:%M')}] Fetch failed, retrying...")
            time.sleep(60)
            continue

        score = item.get('score', 0)
        desc = item.get('descendants', 0)
        kids = set(item.get('kids', []))
        new_kids = kids - seen_kids

        if new_kids:
            print(f"\n[{datetime.now().strftime('%H:%M JST')}] 🆕 {len(new_kids)} new comment(s)! Score:{score} Total:{desc}")
            for kid in new_kids:
                time.sleep(0.1)
                print_comment(kid)
            seen_kids.update(new_kids)
        else:
            print(f"[{datetime.now().strftime('%H:%M JST')}] No new comments. Score:{score} Comments:{desc}")

        time.sleep(interval_min * 60)


def main():
    parser = argparse.ArgumentParser(description='HN Show HN comment monitor for NAIL')
    parser.add_argument('item_id', type=int, help='HN item ID from URL')
    parser.add_argument('--watch', action='store_true', help='Watch mode: poll every 5 minutes')
    parser.add_argument('--summary', action='store_true', help='Summary only (no comments)')
    parser.add_argument('--interval', type=int, default=5, help='Watch interval in minutes (default: 5)')
    args = parser.parse_args()

    if args.watch:
        watch_mode(args.item_id, args.interval)
    else:
        monitor_once(args.item_id, show_comments=not args.summary)


if __name__ == '__main__':
    main()
