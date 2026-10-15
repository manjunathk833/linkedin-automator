#!/usr/bin/env bash
# ==============================================================================
# scripts/setup_daily_runner.sh
# Production Setup: Configures Git Worktree, Shared Data Symlinks,
# and Registers macOS launchd LaunchAgent for 8:00 AM Automated Daily Runs.
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
PARENT_DIR="$(cd "${REPO_DIR}/.." && pwd)"
PROD_DIR="${PARENT_DIR}/linkedinjobsearchautomation-prod"
PLIST_NAME="com.linkedin.automator.daily.plist"
USER_AGENTS_DIR="${HOME}/Library/LaunchAgents"

echo "================================================================"
echo "  SETTING UP PRODUCTION AUTOMATION WORKTREE & LAUNCHD DAEMON"
echo "================================================================"

# 1. Ensure 'main' branch exists locally and is tracked
cd "${REPO_DIR}"
echo "Fetching latest refs from origin..."
git fetch origin

if ! git show-ref --verify --quiet refs/heads/main; then
    echo "Creating local 'main' tracking 'origin/main'..."
    git branch --track main origin/main || git branch main
fi

# 2. Create production Git worktree if not present
if [[ ! -d "${PROD_DIR}" ]]; then
    echo "Creating dedicated production worktree at: ${PROD_DIR}..."
    git worktree add "${PROD_DIR}" main
else
    echo "✅ Production worktree already exists at: ${PROD_DIR}"
fi

# 3. Create shared data & credential symlinks
echo "Configuring shared data symlinks..."
mkdir -p "${REPO_DIR}/data" "${REPO_DIR}/.browser_data"

if [[ -d "${PROD_DIR}" ]]; then
    # Link data/ directory
    if [[ ! -L "${PROD_DIR}/data" ]]; then
        rm -rf "${PROD_DIR}/data"
        ln -s "${REPO_DIR}/data" "${PROD_DIR}/data"
        echo "   • Symlinked ${PROD_DIR}/data -> ${REPO_DIR}/data"
    fi

    # Link .browser_data/ directory
    if [[ ! -L "${PROD_DIR}/.browser_data" ]]; then
        rm -rf "${PROD_DIR}/.browser_data"
        ln -s "${REPO_DIR}/.browser_data" "${PROD_DIR}/.browser_data"
        echo "   • Symlinked ${PROD_DIR}/.browser_data -> ${REPO_DIR}/.browser_data"
    fi

    # Link .env file if present
    if [[ -f "${REPO_DIR}/.env" ]] && [[ ! -L "${PROD_DIR}/.env" ]]; then
        ln -s "${REPO_DIR}/.env" "${PROD_DIR}/.env"
        echo "   • Symlinked ${PROD_DIR}/.env -> ${REPO_DIR}/.env"
    fi
fi

# 4. Install macOS LaunchAgent
mkdir -p "${USER_AGENTS_DIR}"
DEST_PLIST="${USER_AGENTS_DIR}/${PLIST_NAME}"

# Replace hardcoded paths in plist with actual paths
sed -e "s|/Users/yeshwinmanjunath/development/linkedinjobsearchautomation|${REPO_DIR}|g" \
    "${SCRIPT_DIR}/${PLIST_NAME}" > "${DEST_PLIST}"

echo "Installed LaunchAgent to: ${DEST_PLIST}"

# 5. Register with launchd
UID_NUM="$(id -u)"
echo "Unloading any existing daemon..."
launchctl bootout "gui/${UID_NUM}" "${DEST_PLIST}" 2>/dev/null || true

echo "Registering LaunchAgent with launchd..."
launchctl bootstrap "gui/${UID_NUM}" "${DEST_PLIST}" 2>/dev/null || launchctl load "${DEST_PLIST}" 2>/dev/null || true

echo ""
echo "================================================================"
echo "🎉 PRODUCTION SETUP COMPLETE!"
echo "================================================================"
echo "• Production Worktree: ${PROD_DIR} (Branch: main)"
echo "• Active Development:  ${REPO_DIR} (Branch: develop)"
echo "• Shared State:        Both workspaces share data/ and .browser_data/"
echo "• Scheduled Trigger:   Daily at 8:00 AM IST (or upon laptop wakeup)"
echo "• Manual Test:         bash ${REPO_DIR}/scripts/run_daily_prod.sh"
echo "• Audit Logs:          python main.py daily audit"
echo "================================================================"
