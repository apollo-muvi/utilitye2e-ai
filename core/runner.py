"""
Runner — executes a TestSpec with Playwright.

DOM snapshot diff: click button → compare DOM before/after → report change.
"""

import os
import re
import asyncio
import hashlib

from playwright.async_api import async_playwright, Page

from core.spec import TestSpec, TestStep
from core.recorder import Recorder

_BROWSER_PATH = os.environ.get("PLAYWRIGHT_BROWSERS_PATH",
    os.path.expanduser("~/.cache/ms-playwright/chromium_headless_shell-1228/chrome-linux/headless_shell"))


class Runner:
    def __init__(self, spec: TestSpec, headless=True, screenshot_dir="screenshots"):
        self.spec = spec
        self.headless = headless
        self.recorder = Recorder()
        os.makedirs(screenshot_dir, exist_ok=True)

    async def run(self) -> dict:
        print("  → Starting browser...")
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=self.headless,
                args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
                executable_path=_BROWSER_PATH)
            ctx = await browser.new_context(viewport={"width": 1920, "height": 1080}, locale="zh-TW")
            page = await ctx.new_page()
            page.set_default_timeout(15000)
            page.on("dialog", lambda d: asyncio.ensure_future(d.accept()))

            try:
                await self._login(page)
                print(f"  → Navigate: {self.spec.target.url}")
                await page.goto(self.spec.target.url, wait_until="networkidle")
                await page.wait_for_timeout(3000)

                for i, step in enumerate(self.spec.steps):
                    label = f"{self.spec.name} #{i+1} {step.desc or step.button}"
                    await self._run_step(page, step, label)

                print("  → Done")
            except Exception as exc:
                print(f"  ✗ Fatal: {exc}")
                self.recorder.fail("setup", str(exc))
            finally:
                await browser.close()

        return self.recorder.summary()

    async def _login(self, page: Page):
        t = self.spec.target
        if not t.login_url or not t.username:
            return
        url = t.login_url if t.login_url.startswith("http") else f"{t.url.rstrip('/')}/{t.login_url.lstrip('/')}"
        print(f"  → Login: {url}")
        await page.goto(url, wait_until="networkidle")
        await page.wait_for_timeout(2000)
        await page.fill('input[type="text"]', t.username)
        await page.fill('input[type="password"]', t.password)
        await page.click('button:has-text("登入")')
        await page.wait_for_timeout(3000)

    # ─── DOM snapshot ───
    async def _snapshot(self, page: Page) -> str:
        """Hash of page DOM structure — element count + visible text."""
        return await page.evaluate("""
            () => {
                const els = document.querySelectorAll('*');
                let count = els.length;
                let texts = [];
                for (const el of els) {
                    const r = el.getBoundingClientRect();
                    if (r.width > 0 && r.height > 0 && el.tagName === 'BUTTON') {
                        texts.push(el.innerText.trim());
                    }
                }
                const inputs = document.querySelectorAll('input, textarea, select').length;
                return JSON.stringify({count, inputs, btns: texts.sort().join('|')});
            }
        """)

    # ─── Run one step ───
    async def _run_step(self, page: Page, step: TestStep, label: str):
        try:
            # 1. Snapshot before
            before = await self._snapshot(page)
            url_before = page.url

            # 2. Find button
            btn = await self._find_button(page, step.button)
            if not btn:
                self.recorder.fail(label, f"找不到按鈕: {step.button}")
                return

            # 3. Click
            try:
                await btn.click(timeout=5000)
            except Exception:
                await btn.click(force=True, timeout=5000)
            print(f"    → Clicked: {step.button}")
            await page.wait_for_timeout(2000)

            # 4. Fill fields if any
            if step.fill_fields:
                await self._fill_fields(page, step.fill_fields)
                await page.wait_for_timeout(500)

            # 5. Snapshot after
            after = await self._snapshot(page)
            url_after = page.url

            # 6. Diff
            if before != after:
                # Describe what changed
                import json
                b, a = json.loads(before), json.loads(after)
                d_el = a["count"] - b["count"]
                d_in = a["inputs"] - b["inputs"]
                parts = []
                if d_el: parts.append(f"DOM {b['count']}→{a['count']} ({'+' if d_el>0 else ''}{d_el})")
                if d_in: parts.append(f"inputs {b['inputs']}→{a['inputs']}")
                if url_before != url_after: parts.append(f"URL→{url_after}")
                if not parts: parts.append("按鈕文字變化")
                self.recorder.pass_(label, f"✓ {', '.join(parts)}")
            else:
                self.recorder.fail(label, "DOM 無變化，按鈕可能無效")

            # 7. Reload to reset state for next step
            try:
                await page.reload(wait_until="networkidle")
                await page.wait_for_timeout(2000)
            except:
                pass

        except Exception as exc:
            print(f"    ✗ {exc}")
            self.recorder.fail(label, str(exc))
            try:
                await page.reload(wait_until="networkidle")
                await page.wait_for_timeout(2000)
            except:
                pass

    # ─── Find button ───
    async def _find_button(self, page: Page, text: str):
        if not text:
            return None
        # 1. exact role match
        loc = page.get_by_role("button", name=text, exact=True)
        if await loc.count() > 0 and await loc.first.is_visible():
            return loc.first
        # 2. fuzzy role match
        loc = page.get_by_role("button", name=text, exact=False)
        if await loc.count() > 0 and await loc.first.is_visible():
            return loc.first
        # 3. partial text on all buttons
        for btn in await page.query_selector_all("button"):
            bt = (await btn.inner_text()).strip()
            if text in bt and await btn.is_visible():
                return btn
        # 4. keyword
        cn = re.findall(r'[\u4e00-\u9fff]+', text)
        for btn in await page.query_selector_all("button"):
            bt = (await btn.inner_text()).strip()
            if any(k in bt for k in cn) and await btn.is_visible():
                return btn
        # 5. links
        for a in await page.query_selector_all("a"):
            at = (await a.inner_text()).strip()
            if text in at and await a.is_visible():
                return a
        return None

    # ─── Fill fields ───
    async def _fill_fields(self, page: Page, fields: list):
        for f in fields:
            if not f.selector or not f.value:
                continue
            try:
                el = page.locator(f.selector)
                if await el.count() > 0 and await el.first.is_visible():
                    if f.field_type == "select" and f.options:
                        await el.first.select_option(label=f.options[0])
                    elif f.field_type == "checkbox":
                        await el.first.check()
                    else:
                        await el.first.fill(f.value)
                    print(f"    → Fill: {f.selector} = {f.value}")
            except:
                pass
