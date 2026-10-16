#!/usr/bin/env bash
# ==============================================================================
# scripts/run_daily_prod.sh
# Production Execution Script for macOS launchd Scheduled Morning Run.
# Executes inside the dedicated 'linkedinjobsearchautomation-prod' worktree on 'main'.
# ==============================================================================

set -euo pipefail

# 1. Determine directories
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Target execution directory: sibling production worktree or fallback to repo dir
PROD_WORKTREE_DIR="$(cd "${REPO_DIR}/.." && pwd)/linkedinjobsearchautomation-prod"
TARGET_DIR="${REPO_DIR}"
if [[ -d "${PROD_WORKTREE_DIR}" ]]; then
    TARGET_DIR="${PROD_WORKTREE_DIR}"
fi

cd "${TARGET_DIR}"

LOG_DIR="${TARGET_DIR}/data/logs"
mkdir -p "${LOG_DIR}"
RUN_LOG="${LOG_DIR}/launchd_stdout.log"
ERR_LOG="${LOG_DIR}/launchd_stderr.log"

echo "================================================================" >> "${RUN_LOG}"
echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] Launching Scheduled Daily Pipeline" >> "${RUN_LOG}"
echo "Execution Directory: ${TARGET_DIR}" >> "${RUN_LOG}"

# 2. Check and wait for network connectivity (up to 30s) if machine just woke up
echo "Checking network connectivity..." >> "${RUN_LOG}"
NET_READY=false
for i in {1..6}; do
    if curl -s -m 5 https://github.com >/dev/null 2>&1 || ping -c 1 8.8.8.8 >/dev/null 2>&1; then
        echo "✅ Network connectivity confirmed." >> "${RUN_LOG}"
        NET_READY=true
        break
    fi
    echo "Waiting for network connectivity (attempt ${i}/6)..." >> "${RUN_LOG}"
    sleep 5
done

if [[ "${NET_READY}" != "true" ]]; then
    echo "⚠️ Warning: Network connectivity not established within 30s. Proceeding with best effort..." >> "${RUN_LOG}"
fi

# 3. Synchronize latest production code from origin/main
if [[ -d "${PROD_WORKTREE_DIR}" ]] && [[ "${TARGET_DIR}" == "${PROD_WORKTREE_DIR}" ]] && [[ "${NET_READY}" == "true" ]]; then
    echo "Updating production worktree to latest origin/main..." >> "${RUN_LOG}"
    git checkout -- data/config data/logs data/profile 2>/dev/null || true
    git pull origin main >> "${RUN_LOG}" 2>&1 || true
fi

# 3. Source environment and virtualenv
VENV_PYTHON="${REPO_DIR}/venv/bin/python"
if [[ ! -f "${VENV_PYTHON}" ]]; then
    VENV_PYTHON="python3"
fi

if [[ -f "${TARGET_DIR}/.env" ]]; then
    # Export environment variables from .env
    set -a
    # shellcheck disable=SC1091
    source "${TARGET_DIR}/.env"
    set +a
fi

# 4. Execute daily automation pipeline (headless + email dispatch)
echo "Executing: ${VENV_PYTHON} main.py daily --headless" >> "${RUN_LOG}"
"${VENV_PYTHON}" main.py daily --headless >> "${RUN_LOG}" 2>> "${ERR_LOG}" || {
    echo "⚠️ Daily run exited with error code $?" >> "${RUN_LOG}"
}

echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] Daily Pipeline Execution Finished" >> "${RUN_LOG}"
echo "================================================================" >> "${RUN_LOG}"

# 5. Log maintenance: Truncate logs if exceeding 10,000 lines
for log_file in "${RUN_LOG}" "${ERR_LOG}"; do
    if [[ -f "${log_file}" ]] && [[ $(wc -l < "${log_file}") -gt 10000 ]]; then
        tail -n 5000 "${log_file}" > "${log_file}.tmp" && mv "${log_file}.tmp" "${log_file}"
    fi
done

