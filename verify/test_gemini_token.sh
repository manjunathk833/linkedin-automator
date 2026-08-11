#!/bin/bash
# verify/test_gemini_token.sh — Standalone Gemini API key health check
# Tests the AQ. auth key format against the google-genai Python SDK

set -e

cd "$(dirname "$0")/.."
source venv/bin/activate

python3 -c '
import os
from dotenv import load_dotenv
load_dotenv()

key = os.getenv("GEMINI_API_KEY", "")
print(f"[1/3] Key loaded from .env: {key[:10]}... (length={len(key)})")

from google import genai
client = genai.Client(api_key=key)

print("[2/3] Attempting Gemini 3.6 Flash call...")
try:
    res = client.models.generate_content(model="gemini-3.6-flash", contents="Reply with only the word SUCCESS.")
    text = res.text.strip() if hasattr(res, "text") else str(res)
    print(f"[3/3] ✅ Gemini API responded: {text}")
except Exception as e:
    print(f"[3/3] ❌ Gemini API error: {e}")
    print()
    print("Trying gemini-2.5-flash as fallback model...")
    try:
        res = client.models.generate_content(model="gemini-2.5-flash", contents="Reply with only the word SUCCESS.")
        text = res.text.strip() if hasattr(res, "text") else str(res)
        print(f"  ✅ Fallback model responded: {text}")
    except Exception as e2:
        print(f"  ❌ Fallback also failed: {e2}")
        print()
        print("Your API key may be expired or invalid. Please regenerate it at https://aistudio.google.com/")
'
