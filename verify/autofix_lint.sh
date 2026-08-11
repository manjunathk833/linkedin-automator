#!/bin/bash
# verify/autofix_lint.sh — Automated Ruff Linter & Formatter Engine
set -e

cd "$(dirname "$0")/.."
source venv/bin/activate

echo "=================================================="
echo "  RUNNING RUFF LINTER & AUTO-FIX ENGINE"
echo "=================================================="

echo "🔧 Step 1: Auto-fixing linter errors (with --unsafe-fixes)..."
ruff check --fix --unsafe-fixes .

echo "🎨 Step 2: Auto-formatting Python files..."
ruff format .

echo "=================================================="
echo "✅ CODEBASE LINTING & FORMATTING COMPLETE!"
echo "=================================================="
