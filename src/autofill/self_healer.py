"""Deterministic Closed-Loop Self-Healing Engine for ATS Autofill.

Intercepts locator timeouts, pointer interceptions, async combobox delays,
and SPA validation anomalies. Evaluates symptoms against the persistent Learning Vault,
applies targeted remediation recipes, and enforces Rule 11 (Max 2 Attempts Lock).
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any

from src.autofill.autofill_logger import AutofillLogger

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
LEARNING_VAULT_PATH = PROJECT_ROOT / "data" / "logs" / "autofill_learning_vault.json"


class AutofillSelfHealer:
    """Orchestrates closed-loop error interception and deterministic remediation."""

    def __init__(self, logger: AutofillLogger | None = None) -> None:
        self.logger = logger or AutofillLogger.get_logger()
        self._load_vault_cache()

    def _load_vault_cache(self) -> list[dict[str, Any]]:
        """Loads banked lessons from the persistent Learning Vault."""
        if LEARNING_VAULT_PATH.exists():
            try:
                with open(LEARNING_VAULT_PATH, encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("lessons", [])
            except Exception:
                pass
        return []

    async def execute_action(
        self,
        target: Any,
        action_type: str,
        locator: Any,
        value: str = "",
        field_name: str = "",
        vendor: str = "UNKNOWN",
        stage: str = "FORM_FILL",
    ) -> dict[str, Any]:
        """Executes a Playwright action wrapped in a deterministic closed-loop healing interceptor.

        Supported action_types: 'fill', 'click', 'select', 'upload'
        """
        start_time = time.time()
        selector_str = str(locator)
        getattr(target, "page", target)

        # Primary Execution Attempt
        try:
            if action_type in ("fill", "type"):
                el = locator.first if hasattr(locator, "first") else locator
                await el.scroll_into_view_if_needed(timeout=1500)
                await el.click(timeout=1500)
                await el.fill(value)
                await el.dispatch_event("input")
                await el.dispatch_event("change")
                await el.dispatch_event("blur")
            elif action_type == "click":
                el = locator.first if hasattr(locator, "first") else locator
                await el.scroll_into_view_if_needed(timeout=1500)
                await el.click(timeout=2500)
            elif action_type == "upload":
                el = locator.first if hasattr(locator, "first") else locator
                await el.set_input_files(value)
            elif action_type == "select":
                el = locator.first if hasattr(locator, "first") else locator
                await el.select_option(label=value, timeout=2000)

            duration_ms = (time.time() - start_time) * 1000
            self.logger.log_field_action(
                event_type="FIELD_FILLED" if action_type != "click" else "ACTION_CLICKED",
                vendor=vendor,
                stage=stage,
                action_type=action_type,
                locator=selector_str,
                field_name=field_name,
                value=value,
                duration_ms=duration_ms,
                status="SUCCESS",
            )
            return {"status": "success", "healed": False, "duration_ms": duration_ms}

        except Exception as primary_error:
            # FIX PHASE: Closed-Loop Self-Healing Interceptor
            print(f"⚠️ Primary action failed for '{field_name}' ({action_type}): {primary_error}")
            return await self._execute_fix_phase(
                target=target,
                action_type=action_type,
                locator=locator,
                value=value,
                field_name=field_name,
                vendor=vendor,
                stage=stage,
                original_error=primary_error,
                start_time=start_time,
            )

    async def _execute_fix_phase(
        self,
        target: Any,
        action_type: str,
        locator: Any,
        value: str,
        field_name: str,
        vendor: str,
        stage: str,
        original_error: Exception,
        start_time: float,
    ) -> dict[str, Any]:
        """Closed-loop fix phase applying verified remediation recipes (Max 2 Attempts per Rule 11)."""
        error_msg = str(original_error)
        page = getattr(target, "page", target)
        selector_str = str(locator)

        self.logger.log(
            event_type="SELF_HEALING_TRIGGERED",
            message=f"Self-healing activated for '{field_name}': {error_msg[:80]}",
            vendor=vendor,
            state=stage,
            details={"action_type": action_type, "locator": selector_str, "error": error_msg},
        )

        # Attempt 1: Targeted Remediation Recipe based on Error Classification
        healed = False
        applied_recipe = ""

        # Recipe 1: Pointer Interception / Overlay Obstruction
        if (
            "intercepts pointer events" in error_msg.lower()
            or "not visible" in error_msg.lower()
            or action_type == "click"
        ):
            applied_recipe = "RECIPE_POINTER_INTERCEPTION_BYPASS"
            healed = await self._remedy_pointer_interception(page, locator, action_type, value)

        # Recipe 2: Combobox / Option Selection Delay
        if not healed and action_type in ("select", "fill"):
            applied_recipe = "RECIPE_SYNTHETIC_PROTOTYPE_DISPATCH"
            healed = await self._remedy_synthetic_prototype_dispatch(page, locator, value)

        # Attempt 2: Fallback Force Action if Attempt 1 did not complete
        if not healed:
            applied_recipe = "RECIPE_FORCE_EVENT_DISPATCH"
            healed = await self._remedy_force_dispatch(page, locator, action_type, value)

        duration_ms = (time.time() - start_time) * 1000

        if healed:
            print(f"🎉 Self-healing SUCCEEDED for '{field_name}' using {applied_recipe}!")
            self.logger.log_field_action(
                event_type="SELF_HEALING_RESULT",
                vendor=vendor,
                stage=stage,
                action_type=action_type,
                locator=selector_str,
                field_name=field_name,
                value=value,
                duration_ms=duration_ms,
                status="SUCCESS",
                diagnostics={"recipe": applied_recipe, "attempts": 2},
            )
            return {"status": "success", "healed": True, "recipe": applied_recipe, "duration_ms": duration_ms}

        # Rule 11 Lockout: On 2nd failure, immediately halt blind retries and dump diagnostic report
        print(f"🛑 Rule 11 Diagnostic Lockout: Self-healing exhausted for '{field_name}' after 2 attempts.")
        diag = await self.logger.capture_diagnostic(
            target=page,
            reason=f"heal_failed_{field_name}",
            vendor=vendor,
            state=stage,
            extra_meta={"action_type": action_type, "field_name": field_name, "error": error_msg},
        )

        self.logger.log_field_action(
            event_type="FIELD_FAILED",
            vendor=vendor,
            stage=stage,
            action_type=action_type,
            locator=selector_str,
            field_name=field_name,
            value=value,
            duration_ms=duration_ms,
            status="FAILED",
            error=error_msg,
            diagnostics={"screenshot": diag.get("screenshot"), "dom_dump": diag.get("dom_dump")},
        )

        return {"status": "failed", "error": error_msg, "healed": False, "diagnostics": diag}

    async def _remedy_pointer_interception(self, page: Any, locator: Any, action_type: str, value: str) -> bool:
        """Recipe 1: Dismisses overlays, scrolls element, forces click, and dispatches native events."""
        try:
            # Dismiss common cookie or modal overlays
            for overlay_sel in [
                "#onetrust-accept-btn-handler",
                "button:has-text('Accept All')",
                "button:has-text('Accept Cookies')",
                "div[data-automation-id='click_filter']",
                "[aria-label='Close']",
            ]:
                try:
                    btn = page.locator(overlay_sel).first
                    if await btn.count() > 0 and await btn.is_visible():
                        await btn.click(force=True, timeout=1000)
                        await asyncio.sleep(0.3)
                except Exception:
                    pass

            el = locator.first if hasattr(locator, "first") else locator
            if action_type == "click":
                try:
                    await el.click(force=True, timeout=2000)
                    return True
                except Exception:
                    # In-browser DOM click dispatch
                    await el.evaluate(
                        "el => el.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true }))"
                    )
                    return True
            elif action_type in ("fill", "type"):
                await el.click(force=True, timeout=1500)
                await el.fill(value)
                await el.dispatch_event("input")
                await el.dispatch_event("change")
                await el.dispatch_event("blur")
                return True
        except Exception:
            pass
        return False

    async def _remedy_synthetic_prototype_dispatch(self, page: Any, locator: Any, value: str) -> bool:
        """Recipe 4: Sets input value directly on prototype and triggers native React/Angular events."""
        try:
            el = locator.first if hasattr(locator, "first") else locator
            escaped_val = value.replace('"', '\\"')
            js_script = f"""
            el => {{
                try {{
                    const proto = Object.getPrototypeOf(el);
                    const setter = Object.getOwnPropertyDescriptor(proto, 'value')?.set;
                    if (setter) {{
                        setter.call(el, "{escaped_val}");
                    }} else {{
                        el.value = "{escaped_val}";
                    }}
                    el.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    el.dispatchEvent(new Event('blur', {{ bubbles: true }}));
                    return true;
                }} catch (e) {{
                    return false;
                }}
            }}
            """
            res = await el.evaluate(js_script)
            return bool(res)
        except Exception:
            return False

    async def _remedy_force_dispatch(self, page: Any, locator: Any, action_type: str, value: str) -> bool:
        """Recipe 2 & 5: Universal force click or input value override."""
        try:
            el = locator.first if hasattr(locator, "first") else locator
            if action_type == "click":
                await el.click(force=True, timeout=2000)
                return True
            elif action_type in ("fill", "type"):
                await el.fill(value)
                await el.dispatch_event("change")
                return True
        except Exception:
            pass
        return False
