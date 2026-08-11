#!/bin/bash
# verify/04_test_playwright_cdp.sh
# Tests Playwright CDP connection by launching Chrome with remote debugging
# and connecting to it via a Python script.
#
# Usage: ./verify/04_test_playwright_cdp.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "============================================"
echo "  Playwright CDP Connection Verification"
echo "============================================"

# Step 1: Check if Chrome is installed
CHROME_PATH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
if [ ! -f "$CHROME_PATH" ]; then
    echo "❌ Google Chrome not found at $CHROME_PATH"
    echo "   Please install Google Chrome to use CDP mode."
    exit 1
fi
echo "✅ Google Chrome found."

# Step 2: Launch Chrome with remote debugging on port 9222
echo "🚀 Launching Chrome with --remote-debugging-port=9222..."
"$CHROME_PATH" --remote-debugging-port=9222 --user-data-dir="$PROJECT_DIR/.browser_data_cdp" &
CHROME_PID=$!
echo "   Chrome PID: $CHROME_PID"

# Give Chrome time to start and retry CDP check
echo "🔍 Waiting for CDP endpoint at http://localhost:9222/json/version..."
CDP_RESPONSE="FAILED"
for i in 1 2 3 4 5; do
    sleep 2
    CDP_RESPONSE=$(curl -s http://localhost:9222/json/version 2>/dev/null || echo "FAILED")
    if echo "$CDP_RESPONSE" | grep -q "webSocketDebuggerUrl"; then
        break
    fi
    echo "   Attempt $i: not ready yet, retrying..."
done

if echo "$CDP_RESPONSE" | grep -q "webSocketDebuggerUrl"; then
    echo "✅ CDP endpoint is live!"
    echo "   Response: $(echo "$CDP_RESPONSE" | head -c 200)"
else
    echo "❌ CDP endpoint not responding."
    kill $CHROME_PID 2>/dev/null || true
    exit 1
fi

# Step 4: Run Playwright CDP connection test
echo ""
echo "🧪 Running Playwright CDP connection test..."
cd "$PROJECT_DIR"
source venv/bin/activate
python3 verify/04_test_playwright_cdp_connect.py

# Step 5: Cleanup
echo ""
echo "🧹 Cleaning up Chrome process..."
kill $CHROME_PID 2>/dev/null || true
echo "✅ Done."
