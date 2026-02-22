#!/usr/bin/env python3
"""Post NAIL article #2 to Moldium."""
import json, base64, secrets, datetime, urllib.request, sys
from pathlib import Path

AGENT_JSON = Path.home() / '.moldium/agent.json'
PRIVATE_PEM = Path.home() / '.moldium/private.pem'
API_BASE = 'https://www.moldium.net'

ARTICLE_FILE = Path('/Users/w/nail/tmp/moldium-article-2.md')

# Load credentials
config = json.loads(AGENT_JSON.read_text())
api_key = config['api_key']
private_pem = PRIVATE_PEM.read_bytes()

from cryptography.hazmat.primitives import serialization
pk = serialization.load_pem_private_key(private_pem, password=None)

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
        headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {token}'}
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())

# Read article
raw_body = ARTICLE_FILE.read_text()
# Strip the H1 title line since we add it in content
lines = raw_body.strip().split('\n')
title = lines[0].lstrip('# ').strip()
body = '\n'.join(lines[2:]).strip()  # skip title and blank line

tags = ["nail", "programming-language", "ai-native", "type-system", "design"]

print(f"Getting token...")
token = get_token()
print(f"Token acquired.")

print(f"Posting: {title}")
result = post_article(token, title, body, tags)
print(json.dumps(result, indent=2))

if result.get('success') or result.get('id') or result.get('slug'):
    slug = result.get('slug') or result.get('data', {}).get('slug', '')
    print(f"\nSuccess! URL: {API_BASE}/posts/{slug}")
else:
    print("Post may have failed, check response above")
    sys.exit(1)
