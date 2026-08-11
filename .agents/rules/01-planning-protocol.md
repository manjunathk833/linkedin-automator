---
trigger: always_on
---
# Mandatory Planning Protocol & Absolute Execution Lock

1. **Zero-Exemption Scope:** This protocol applies to EVERY task involving file modifications or command execution — including bug fixes, test creation, config tweaks, and refactoring. No task is exempt.
2. **Analysis & Plan First:** Before calling any file modification or state-changing tools, you MUST provide:
   - Root Cause / Technical Analysis of the request.
   - Step-by-step Implementation Plan listing exact target files.
   - Proposed Changes summary.
3. **Strict Initial Turn Lock:** You are strictly forbidden from calling `write_to_file`, `replace_file_content`, `multi_replace_file_content`, or modifying terminal commands in your initial turn for any request requiring code changes.
4. **Approval Gate:** Every plan MUST terminate with:
   *"Please review this plan. Reply 'PROCEED' to execute these edits, or provide feedback."*
   Only modify files after receiving explicit user confirmation ("PROCEED" / "APPROVED").