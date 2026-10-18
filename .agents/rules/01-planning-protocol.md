---
trigger: always_on
---
# Mandatory Planning Protocol & Absolute Execution Lock

1. **Zero-Exemption Scope:** This protocol applies to EVERY task involving file modifications or command execution — including bug fixes, test creation, config tweaks, and refactoring. No task is exempt.
2. **Analysis & Plan First:** Before calling any file modification or state-changing tools, you MUST provide:
   - Root Cause / Technical Analysis of the request.
   - Step-by-step Implementation Plan listing exact target files (MUST explicitly include a dedicated Post-Implementation Dry Run phase).
   - Proposed Changes summary.
3. **Strict Initial Turn Lock:** You are strictly forbidden from calling `write_to_file`, `replace_file_content`, `multi_replace_file_content`, or modifying terminal commands in your initial turn for any request requiring code changes.
4. **Approval Gate:** Every plan MUST terminate with:
   *"Please review this plan. Reply 'PROCEED' to execute these edits, or provide feedback."*
   Only modify files after receiving explicit user confirmation ("PROCEED" / "APPROVED").
5. **Absolute Prohibition on Direct Merges/Pushes to `main` (HARD NO):**
   Any plan that involves pushing code MUST explicitly target `develop` and state that a GitHub Pull Request will be raised for user review. Proposing, executing, or attempting a merge or push to `main` is an immediate protocol violation. The USER alone reviews and merges PRs to `main` on GitHub.
6. **Mandatory Post-Implementation Dry Run in Every Plan (Non-Negotiable):**
   EVERY plan that modifies application logic, parsers, classifiers, databases, APIs, or UI components MUST explicitly include a dedicated phase:
   *"Phase N: Mandatory Post-Implementation Dry Run & System Flow Verification"*.
   Passing unit or regression tests alone is strictly insufficient. The plan MUST specify how authentic live execution, real data persistence, and UI rendering (on `http://localhost:8000` or browser) will be verified BEFORE declaring the task complete or opening/updating a Pull Request. Any plan that omits an explicit post-implementation dry run phase is an immediate protocol violation.