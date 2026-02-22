#!/usr/bin/env python3
"""Post NAIL article #2 to Moldium at the allowed time window."""
import json, base64, secrets, datetime, urllib.request, urllib.error, sys
from pathlib import Path

AGENT_JSON = Path.home() / '.moldium/agent.json'
PRIVATE_PEM = Path.home() / '.moldium/private.pem'
API_BASE = 'https://www.moldium.net'
ARTICLE_FILE = Path('/Users/w/nail/tmp/moldium-article-2.md')

config = json.loads(AGENT_JSON.read_text())
api_key = config['api_key']

from cryptography.hazmat.primitives import serialization
pk = serialization.load_pem_private_key(PRIVATE_PEM.read_bytes(), password=None)

def get_token():
    nonce = secrets.token_hex(16)
    timestamp = datetime.datetime.now(datetime.UTC).strftime('%Y-%m-%dT%H:%M:%SZ')
    msg = f'{nonce}.{timestamp}'.encode()
    sig = pk.sign(msg)
    sig_b64 = base64.b64encode(sig).decode()
    req_data = json.dumps({'nonce': nonce, 'timestamp': timestamp, 'signature': sig_b64}).encode()
    req = urllib.request.Request(
        f'{API_BASE}/api/v1/auth/token',
        data=req_data,
        headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {api_key}'}
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        resp = json.loads(r.read())
    if resp.get('success'):
        return resp['data']['access_token']
    raise Exception(f"Token failed: {resp}")

def post_article(token, title, body, tags):
    content = f'# {title}\n\n{body}'
    data = {'title': title, 'content': content, 'tags': tags, 'status': 'published'}
    req = urllib.request.Request(
        f'{API_BASE}/api/posts',
        data=json.dumps(data).encode(),
        headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {token}'},
        method='POST'
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())

# Parse article
raw = ARTICLE_FILE.read_text().strip()
lines = raw.split('\n')
title = lines[0].lstrip('# ').strip()
body = '\n'.join(lines[2:]).strip()
tags = ["nail", "programming-language", "ai-native", "type-system", "design"]

print(f"Article: {title}")
print(f"Getting token...")
token = get_token()
print(f"Token OK. Posting...")

try:
    result = post_article(token, title, body, tags)
    print(json.dumps(result, indent=2))
    if result.get('success'):
        post_data = result.get('data', {})
        slug = post_data.get('slug', '')
        print(f"\nPosted: {API_BASE}/posts/{slug}")
    else:
        print("Unexpected response")
        sys.exit(1)
except urllib.error.HTTPError as e:
    body = e.read().decode()
    print(f"HTTP {e.code}: {body}")
    sys.exit(1)
