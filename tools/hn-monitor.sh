#!/bin/bash
# hn-monitor.sh — HN Show HN 投稿のコメント監視スクリプト
# 使用方法: ./tools/hn-monitor.sh <item_id>
# 例: ./tools/hn-monitor.sh 43456789
#
# HN投稿後にitem_idを受け取り、新しいコメントをSlackに通知する

set -euo pipefail

ITEM_ID="${1:-}"
SLACK_CHANNEL="D0ACJ17QJ4R"
STATE_FILE="/tmp/hn-monitor-state-${ITEM_ID}.json"
RESPONSE_FILE="$(dirname "$0")/../tmp/hn-comment-responses.md"

if [ -z "$ITEM_ID" ]; then
  echo "Usage: $0 <hn_item_id>"
  echo "Example: $0 43456789"
  echo ""
  echo "Get the item_id from the URL after posting:"
  echo "  https://news.ycombinator.com/item?id=<item_id>"
  exit 1
fi

fetch_item() {
  curl -s "https://hacker-news.firebaseio.com/v0/item/${ITEM_ID}.json"
}

fetch_comment() {
  local cid="$1"
  curl -s "https://hacker-news.firebaseio.com/v0/item/${cid}.json"
}

notify_slack() {
  local msg="$1"
  # openclaw経由でSlack通知 — 直接API叩かず
  echo "[HN MONITOR] $msg"
  # 実際の通知はOpenClawのSlackチャンネル経由
  # このスクリプト単体では標準出力のみ。ラッパーから呼ぶこと。
}

main() {
  echo "=== HN Monitor: item/${ITEM_ID} ==="
  echo "Started: $(date '+%Y-%m-%d %H:%M:%S JST')"
  echo ""
  
  # アイテム取得
  local item
  item=$(fetch_item)
  
  if [ "$(echo "$item" | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("type","unknown"))')" = "null" ]; then
    echo "ERROR: Item ${ITEM_ID} not found"
    exit 1
  fi
  
  # タイトル・スコア・コメント数表示
  echo "$item" | python3 - << 'PYTHON'
import json, sys
d = json.load(sys.stdin)
title = d.get('title', 'N/A')
score = d.get('score', 0)
descendants = d.get('descendants', 0)
url = d.get('url', '')
kids = d.get('kids', [])

print(f"Title: {title}")
print(f"Score: {score} | Comments: {descendants}")
print(f"URL: https://news.ycombinator.com/item?id={d['id']}")
print(f"Posted: {d.get('time', 'N/A')}")
print(f"Kids: {len(kids)} top-level comments")
print("")

if kids:
    print(f"Top-level comment IDs: {kids[:10]}")
PYTHON

  echo ""
  
  # 全コメント取得（再帰的）
  echo "=== Comments ==="
  echo "$item" | python3 << PYTHON
import json, sys, urllib.request, time

item = json.load(sys.stdin)
kids = item.get('kids', [])

def fetch_comment(cid):
    url = f"https://hacker-news.firebaseio.com/v0/item/{cid}.json"
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            return json.loads(r.read())
    except:
        return None

def print_comment(cid, depth=0):
    c = fetch_comment(cid)
    if not c or c.get('deleted') or c.get('dead'):
        return
    
    indent = "  " * depth
    by = c.get('by', '[deleted]')
    text = c.get('text', '').replace('<p>', '\n').replace('&#x27;', "'").replace('&amp;', '&').replace('&gt;', '>').replace('&lt;', '<').replace('<i>', '').replace('</i>', '').replace('<a href="', '').replace('" rel="nofollow">', ' ').replace('</a>', '')
    # 長すぎるテキストは省略
    if len(text) > 500:
        text = text[:500] + "..."
    
    print(f"{indent}[{by}] (id:{cid})")
    for line in text.split('\n')[:5]:
        if line.strip():
            print(f"{indent}  {line.strip()}")
    print()
    
    # 子コメント（深さ2まで）
    if depth < 2:
        for kid in c.get('kids', [])[:3]:
            time.sleep(0.1)
            print_comment(kid, depth + 1)

for kid in kids[:20]:
    time.sleep(0.1)
    print_comment(kid)

print(f"\n[Total top-level comments: {len(kids)}]")
PYTHON
}

main
