"""
Standalone Nomba auth diagnostic.

Run this instead of hand-crafting curl commands - it loads your .env the
exact same way config.py does, so there's no risk of a shell (bash, fish,
zsh - they all differ) failing to export the variables correctly.

Usage:
    python3 test_nomba_auth.py
"""

import os
import json
import sys
from dotenv import load_dotenv

load_dotenv()

REQUIRED = ["NOMBA_ACCOUNT_ID", "NOMBA_CLIENT_ID", "NOMBA_CLIENT_SECRET", "NOMBA_BASE_URL"]

print("=== Step 1: Checking .env values are actually loaded ===")
values = {}
missing = []
for name in REQUIRED:
    value = os.getenv(name)
    values[name] = value
    if not value:
        missing.append(name)
    else:
        # Never print the actual secret - just confirm it loaded and show length.
        preview = value if name == "NOMBA_BASE_URL" else f"<{len(value)} characters>"
        print(f"  {name} = {preview}")

if missing:
    print()
    print(f"MISSING: {', '.join(missing)}")
    print("These are blank even after loading .env. Check that:")
    print("  1. You're running this from the same folder as your .env file")
    print("  2. The .env file has no typos in the variable names")
    print("  3. There's no stray quote or space around the '=' in .env")
    sys.exit(1)

print()
print("All four values loaded successfully. Now testing the actual auth call...")
print()
print("=== Step 2: Calling Nomba's auth endpoint directly ===")

import requests

url = f"{values['NOMBA_BASE_URL']}/auth/token/issue"
headers = {
    "Content-Type": "application/json",
    "accountId": values["NOMBA_ACCOUNT_ID"],
}
payload = {
    "grant_type": "client_credentials",
    "client_id": values["NOMBA_CLIENT_ID"],
    "client_secret": values["NOMBA_CLIENT_SECRET"],
}

print(f"POST {url}")
try:
    response = requests.post(url, headers=headers, json=payload, timeout=15)
    print(f"HTTP status: {response.status_code}")
    print()
    print("=== Full response body (this is the important part) ===")
    try:
        print(json.dumps(response.json(), indent=2))
    except ValueError:
        print(response.text)
except requests.exceptions.RequestException as e:
    print(f"Network error before we even got a response: {e}")
    print("This usually means NOMBA_BASE_URL is wrong or unreachable, not a credentials problem.")