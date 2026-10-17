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

# 3. Create shared runtime data & credential symlinks (granular to preserve tracked Git files)
echo "Configuring granular shared data symlinks..."
mkdir -p "${REPO_DIR}/data" "${REPO_DIR}/data/logs" "${REPO_DIR}/data/profile" "${REPO_DIR}/.browser_data"

if [[ -d "${PROD_DIR}" ]]; then
    # If prod/data is a directory symlink, remove it and restore git-tracked files
    if [[ -L "${PROD_DIR}/data" ]]; then
        echo "   • Removing legacy directory symlink ${PROD_DIR}/data..."
        rm "${PROD_DIR}/data"
        git -C "${PROD_DIR}" checkout -- data/
    fi

    # Ensure prod directories exist
    mkdir -p "${PROD_DIR}/data" "${PROD_DIR}/data/profile" "${PROD_DIR}/data/logs"

    # Symlink runtime queue directories
    for queue_dir in "pending_queue" "approved_queue" "resumes"; do
        mkdir -p "${REPO_DIR}/data/${queue_dir}"
        if [[ ! -L "${PROD_DIR}/data/${queue_dir}" ]]; then
            rm -rf "${PROD_DIR}/data/${queue_dir}"
            ln -s "${REPO_DIR}/data/${queue_dir}" "${PROD_DIR}/data/${queue_dir}"
            echo "   • Symlinked data/${queue_dir} -> ${REPO_DIR}/data/${queue_dir}"
        fi
    done

    # Symlink screenshots directory inside logs
    mkdir -p "${REPO_DIR}/data/logs/screenshots"
    if [[ ! -L "${PROD_DIR}/data/logs/screenshots" ]]; then
        rm -rf "${PROD_DIR}/data/logs/screenshots"
        ln -s "${REPO_DIR}/data/logs/screenshots" "${PROD_DIR}/data/logs/screenshots"
        echo "   • Symlinked data/logs/screenshots -> ${REPO_DIR}/data/logs/screenshots"
    fi

    # Symlink shared database and runtime data files
    shared_files=(
        "data/app_database.db"
        "data/resume_profile.json"
        "data/master_knowledge_bank.json"
        "data/profile/candidate_master_data.json"
        "data/application_history.json"
        "data/processed_jobs.json"
    )

    for rel_file in "${shared_files[@]}"; do
        src_path="${REPO_DIR}/${rel_file}"
        dest_path="${PROD_DIR}/${rel_file}"
        if [[ -f "${src_path}" ]]; then
            if [[ ! -L "${dest_path}" ]]; then
                rm -f "${dest_path}"
                ln -s "${src_path}" "${dest_path}"
                echo "   • Symlinked ${rel_file} -> ${src_path}"
            fi
        fi
    done

    # Symlink log files so prod outputs appear in dev session
    log_files=(
        "data/logs/daily_runs.log"
        "data/logs/daily_runs.jsonl"
        "data/logs/launchd_stdout.log"
        "data/logs/launchd_stderr.log"
        "data/logs/dashboard.log"
        "data/logs/autofill_events.jsonl"
        "data/logs/autofill_diagnostics.log"
        "data/logs/naukri_pinger.log"
        "data/logs/llm_requests.log"
    )

    for log_file in "${log_files[@]}"; do
        src_log="${REPO_DIR}/${log_file}"
        dest_log="${PROD_DIR}/${log_file}"
        touch "${src_log}"
        if [[ ! -L "${dest_log}" ]]; then
            rm -f "${dest_log}"
            ln -s "${src_log}" "${dest_log}"
            echo "   • Symlinked ${log_file} -> ${src_log}"
        fi
    done

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
