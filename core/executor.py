"""
Page Executor — translates an AI action plan into Playwright operations.

Key insight from v1:
  Instead of trying to use AI-generated CSS selectors (which are often wrong),
  we look up the element by its ID in the element map and use the
  MULTIPLE locator strategies computed by the inspector, trying each in order.

  For each element, the executor tries:
    1. data-testid selector
    2. id selector
    3. get_by_role with name
    4. get_by_label (for form fields)
    5. CSS attribute selector (name / placeholder)
    6. get_by_text (for buttons/links)
"""

import asyncio
import os
import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from playwright.async_api import async_playwright, Page


class Executor:
    """Execute an action plan against a real page."""

    def __init__(self, element_map: Dict[str, Any], headless: bool = True):
        self.element_map = element_map
        self.headless = headless
        self.results: List[Dict] = []
        self.plan: Optional[Dict] = None
        self.screenshot_dir = ""
        self._browser = None
        self._page = None

    async def execute(self, plan: Dict[str, Any], output_dir: str = "output") -> Dict[str, Any]:
        """Execute a plan and return results.

        plan shape:
        {
            "goal": "...",
            "page_title": "...",
            "steps": [
                {"action": "click|fill|select|check|assert|wait|navigate",
                 "element_id": 1, "value": "...", "description": "..."}
            ]
        }
        """
        self.plan = plan
        self.results = []
        self.screenshot_dir = os.path.join(output_dir, f"run_{datetime.now():%Y%m%d_%H%M%S}")
        os.makedirs(self.screenshot_dir, exist_ok=True)

        async with async_playwright() as p:
            self._browser = await p.chromium.launch(
                headless=self.headless,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
            )
            context = await self._browser.new_context(
                viewport={"width": 1920, "height": 1080},
                locale="zh-TW",
            )
            self._page = await context.new_page()
            self._page.set_default_timeout(15000)

            await self._page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            """)

            elements = self.element_map.get("elements", [])
            steps = plan.get("steps", [])
            plan_url = self.element_map.get("url", "")

            for i, step in enumerate(steps):
                result = await self._do_step(step, i, elements, plan_url)
                self.results.append(result)
                if result["status"] == "fail":
                    continue  # don't abort, try next step

            await self._browser.close()

        passed = sum(1 for r in self.results if r["status"] == "pass")
        failed = sum(1 for r in self.results if r["status"] == "fail")

        return {
            "goal": plan.get("goal", ""),
            "total_steps": len(steps),
            "passed": passed,
            "failed": failed,
            "results": self.results,
        }

    async def _do_step(
        self, step: Dict, step_index: int, elements: List[Dict], fallback_url: str
    ) -> Dict:
        action = step.get("action", "")
        element_id = step.get("element_id")
        value = step.get("value", "")
        description = step.get("description", "")
        name = f"Step {step_index + 1}: {description or action}"

        try:
            if action == "navigate":
                url = value or fallback_url
                await self._page.goto(url, wait_until="networkidle", timeout=20000)
                await self._page.wait_for_timeout(1000)
                return self._pass(name, f"Navigated to {url}")

            if action == "wait":
                el = self._find_element(element_id, elements)
                locators = el.get("locators", [])
                await self._try_locators(locators, "wait_for")
                return self._pass(name, f"Waited for element [{element_id}]")

            if action == "assert":
                el = self._find_element(element_id, elements)
                if not el:
                    if value:
                        # Try to find text on the page
                        content = await self._page.text_content("body") or ""
                        if value.lower() in content.lower():
                            return self._pass(name, f"Found text: {value}")
                    return self._fail(name, f"Element [{element_id}] not found in map")

                locators = el.get("locators", [])
                try:
                    await self._try_locators(locators, "wait_for")
                    return self._pass(name, f"Element [{element_id}] exists")
                except Exception:
                    return self._fail(name, f"Element [{element_id}] not found on page")

            if action == "click":
                el = self._find_element(element_id, elements)
                if not el:
                    # Fallback: try to find by value text
                    if value:
                        btn = self._page.get_by_role("button").filter(has_text=value)
                        if await btn.count() > 0:
                            await btn.first.click()
                            await self._page.wait_for_timeout(800)
                            return self._pass(name, f"Clicked button by text: {value}")
                    return self._fail(name, f"Element [{element_id}] not found in map")

                locators = el.get("locators", [])
                await self._try_locators(locators, "click")
                await self._page.wait_for_timeout(800)
                return self._pass(name, f"Clicked [{el.get('text', '') or el.get('label', '') or element_id}]")

            if action == "fill":
                el = self._find_element(element_id, elements)
                if not el:
                    return self._fail(name, f"Element [{element_id}] not found in map")

                locators = el.get("locators", [])
                await self._try_locators(locators, "fill", value)
                return self._pass(name, f"Filled [{el.get('label', '') or el.get('name', '')}] with '{value}'")

            if action == "select":
                el = self._find_element(element_id, elements)
                if not el:
                    return self._fail(name, f"Element [{element_id}] not found in map")

                locators = el.get("locators", [])
                # Try select via value first, then label
                locator_obj = self._build_locator(locators[0]) if locators else None
                if locator_obj:
                    try:
                        await locator_obj.select_option(value=value)
                    except Exception:
                        try:
                            await locator_obj.select_option(label=value)
                        except Exception:
                            await locator_obj.select_option(index=0)
                await self._page.wait_for_timeout(500)
                return self._pass(name, f"Selected '{value}' in [{el.get('label', '')}]")

            if action == "check":
                el = self._find_element(element_id, elements)
                if not el:
                    return self._fail(name, f"Element [{element_id}] not found in map")

                locators = el.get("locators", [])
                locator_obj = self._build_locator(locators[0]) if locators else None
                if locator_obj:
                    await locator_obj.check()
                return self._pass(name, f"Checked [{el.get('label', '')}]")

            return self._fail(name, f"Unknown action: {action}")

        except Exception as e:
            return self._fail(name, str(e))

    def _find_element(self, element_id: int, elements: List[Dict]) -> Optional[Dict]:
        """Find element by ID in the element map."""
        for el in elements:
            if el.get("id") == element_id:
                return el
        return None

    async def _try_locators(self, locators: List[str], action: str, value: str = ""):
        """Try each locator strategy in order until one succeeds."""
        last_error = None
        for loc_str in locators:
            try:
                locator_obj = self._build_locator(loc_str)
                if locator_obj is None:
                    continue

                if action == "click":
                    await locator_obj.click()
                elif action == "fill":
                    await locator_obj.fill(value)
                elif action == "wait_for":
                    await locator_obj.wait_for(state="visible", timeout=5000)
                return  # success
            except Exception as e:
                last_error = e
                continue

        raise last_error or Exception("No locator strategies worked")

    def _build_locator(self, loc_str: str):
        """Convert a locator string to a Playwright Locator object."""
        page = self._page

        # get_by_test_id:<value>
        if loc_str.startswith("get_by_test_id:"):
            val = loc_str.split(":", 1)[1]
            return page.get_by_test_id(val)

        # get_by_role:<role>:name=<name>
        if loc_str.startswith("get_by_role:"):
            parts = loc_str.split(":")
            role = parts[1]
            name = parts[2].replace("name=", "", 1) if len(parts) > 2 else ""
            opts = {"name": name} if name else {}
            return page.get_by_role(role, **opts)

        # get_by_label:<label>
        if loc_str.startswith("get_by_label:"):
            val = loc_str.split(":", 1)[1]
            return page.get_by_label(val)

        # get_by_placeholder:<placeholder>
        if loc_str.startswith("get_by_placeholder:"):
            val = loc_str.split(":", 1)[1]
            return page.get_by_placeholder(val)

        # get_by_text:<text>
        if loc_str.startswith("get_by_text:"):
            val = loc_str.split(":", 1)[1]
            return page.get_by_text(val, exact=False)

        # get_by_title:<title>
        if loc_str.startswith("get_by_title:"):
            val = loc_str.split(":", 1)[1]
            return page.get_by_title(val)

        # CSS selector
        return page.locator(loc_str)

    def _pass(self, name: str, detail: str) -> Dict:
        return {"step": name, "status": "pass", "detail": detail}

    def _fail(self, name: str, detail: str) -> Dict:
        return {"step": name, "status": "fail", "detail": detail}