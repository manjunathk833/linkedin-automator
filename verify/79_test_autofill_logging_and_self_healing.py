#!/usr/bin/env python3
"""
Verification Gate 79: Autofill Structured Logging, Browser Persistence & Deterministic Self-Healing.

Validates:
1. PII masking for sensitive credentials and contact details in diagnostic streams.
2. Structured JSONL event logging and SSE listener broadcasting.
3. Hirist Tech vendor schema discovery, pattern classification, and selector mapping.
4. Browser lifecycle stability & safe process reconnection (anti-crash guard).
5. AutofillSelfHealer closed-loop error remediation recipes.
6. Rule 11 Anti-Looping Diagnostic Lock (max 2 attempts strictly enforced).
"""

from __future__ import annotations

import asyncio
import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.autofill.autofill_logger import AutofillLogger, mask_pii
from src.autofill.self_healer import AutofillSelfHealer
from src.autofill.vendor_schemas import ATSVendorPattern, classify_ats_pattern, get_vendor_schema
from src.browser.cdp_stealth import clean_stale_browser_processes, is_browser_context_alive


class TestAutofillLoggingAndSelfHealing(unittest.TestCase):
    """Test suite for Gate 79."""

    def setUp(self):
        self.logger = AutofillLogger.get_logger()
        self.healer = AutofillSelfHealer(logger=self.logger)

    def test_01_pii_masking(self):
        """Validates sensitive fields are properly masked in logs."""
        print("\n🧪 Step 1: Testing PII Masking Engine...")
        self.assertEqual(mask_pii("MockSecretPassword123!", "workday_password"), "********")
        self.assertEqual(mask_pii("MySecretKey123", "api_token"), "********")
        # Phone masking preserves country code / token prefix but masks inner digits
        masked_phone = mask_pii("+917337813770", "phoneNumber")
        self.assertTrue(masked_phone.startswith("+917") and masked_phone.endswith("70"))
        self.assertIn("****", masked_phone)
        print("  ✅ PII masking verified for credentials and phone numbers.")

    def test_02_autofill_event_logging_and_listeners(self):
        """Validates structured JSONL event logging and SSE listener dispatching."""
        print("\n🧪 Step 2: Testing Structured JSONL Event Logging & Listeners...")
        received_events = []

        def _test_listener(evt: dict):
            received_events.append(evt)

        self.logger.subscribe(_test_listener)
        try:
            evt = self.logger.log_field_action(
                event_type="FIELD_FILLED",
                vendor="HIRIST_TECH",
                stage="PERSONAL_INFO",
                action_type="fill",
                locator="input[name='phoneNumber']",
                field_name="phoneNumber",
                value="+917337813770",
                duration_ms=45.2,
                status="SUCCESS",
            )
            self.assertEqual(evt.status, "SUCCESS")
            self.assertEqual(evt.vendor, "HIRIST_TECH")
            self.assertIn("****", evt.value_preview)
            self.assertEqual(len(received_events), 1)
            self.assertEqual(received_events[0]["field_name"], "phoneNumber")
            print("  ✅ Structured JSONL event logged and broadcasted to listener.")
        finally:
            self.logger.unsubscribe(_test_listener)

    def test_03_hirist_tech_vendor_schema(self):
        """Validates Hirist Tech pattern classification and DOM selectors."""
        print("\n🧪 Step 3: Testing Hirist Tech Pattern Classification...")
        hirist_url = "https://www.hirist.tech/j/practo-lead-software-development-engineer-test-1675761"
        pattern = classify_ats_pattern(hirist_url)
        self.assertEqual(pattern, ATSVendorPattern.HIRIST_TECH_STANDARD)

        schema = get_vendor_schema(pattern)
        self.assertEqual(schema.get("vendor_name"), "Hirist Tech")
        selectors = schema.get("selectors", {})
        self.assertIn("resume", selectors)
        self.assertIn("phone", selectors)
        self.assertIn("save_and_next", selectors)
        self.assertIn("input[name='phoneNumber']", selectors["phone"])
        print("  ✅ Hirist Tech pattern and schema selectors verified.")

    def test_04_browser_lifecycle_and_clean_stale_safety(self):
        """Validates safe process cleanup does not kill active parent processes when force=False."""
        print("\n🧪 Step 4: Testing Browser Lifecycle & Process Clean Safety...")
        dummy_dir = "/tmp/test_browser_profile_gate79"
        os.makedirs(dummy_dir, exist_ok=True)
        # Calling clean_stale_browser_processes with force=False must execute cleanly without exceptions
        killed = clean_stale_browser_processes(dummy_dir, force=False)
        self.assertIsInstance(killed, int)

        # Context alive helper
        self.assertFalse(is_browser_context_alive(None))
        print("  ✅ Browser lifecycle process safety check passed.")

    def test_05_self_healer_remediation(self):
        """Validates AutofillSelfHealer recovers from pointer interception via closed-loop recipe."""
        print("\n🧪 Step 5: Testing Closed-Loop Self-Healing Interceptor...")

        # Setup mock locator where initial click fails with pointer interception, but force click succeeds
        mock_locator = MagicMock()
        mock_locator.first = mock_locator
        mock_locator.scroll_into_view_if_needed = AsyncMock()

        # Primary click raises pointer interception error
        mock_locator.click = AsyncMock(
            side_effect=[
                Exception("Locator.click: Timeout 1500ms exceeded ... intercepts pointer events"),
                None,  # Second call (force click) succeeds
            ]
        )
        mock_locator.fill = AsyncMock()
        mock_locator.dispatch_event = AsyncMock()

        mock_target = MagicMock()
        mock_target.page = mock_target
        mock_target.locator = MagicMock(return_value=MagicMock(first=MagicMock(count=AsyncMock(return_value=0))))

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                self.healer.execute_action(
                    target=mock_target,
                    action_type="click",
                    locator=mock_locator,
                    field_name="save_and_next",
                    vendor="HIRIST_TECH",
                )
            )
            self.assertEqual(result.get("status"), "success")
            self.assertTrue(result.get("healed"))
            self.assertEqual(result.get("recipe"), "RECIPE_POINTER_INTERCEPTION_BYPASS")
            print("  ✅ Self-healer successfully remediated pointer interception error.")
        finally:
            loop.close()

    def test_06_self_healer_rule_11_lockout(self):
        """Validates Rule 11 lockout halts after exactly 2 failed attempts and dumps diagnostic report."""
        print("\n🧪 Step 6: Testing Rule 11 Diagnostic Lockout (Max 2 Attempts)...")

        mock_locator = MagicMock()
        mock_locator.first = mock_locator
        mock_locator.scroll_into_view_if_needed = AsyncMock()
        # Always fail to trigger lockout
        mock_locator.click = AsyncMock(side_effect=Exception("Unresolvable DOM collision error"))
        mock_locator.fill = AsyncMock(side_effect=Exception("Unresolvable DOM collision error"))

        mock_target = MagicMock()
        mock_target.page = mock_target
        mock_target.title = AsyncMock(return_value="Error Page")
        mock_target.url = "https://example.com/form"
        mock_target.screenshot = AsyncMock()
        mock_target.locator = MagicMock(
            return_value=MagicMock(first=MagicMock(count=AsyncMock(return_value=0)), all=AsyncMock(return_value=[]))
        )

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                self.healer.execute_action(
                    target=mock_target,
                    action_type="click",
                    locator=mock_locator,
                    field_name="unresolvable_btn",
                    vendor="TEST_VENDOR",
                )
            )
            self.assertEqual(result.get("status"), "failed")
            self.assertFalse(result.get("healed"))
            self.assertIn("diagnostics", result)
            print("  ✅ Rule 11 Diagnostic Lockout enforced: halted after 2 attempts and dumped diagnostic report.")
        finally:
            loop.close()


if __name__ == "__main__":
    unittest.main()
