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

_BROWSER_PATH = os.path.expanduser("~/.cache/ms-playwright/chromium_headless_shell-1228/chrome-linux/headless_shell")


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
                    await self._run_step(page, step, label, i)

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
        """Hash of page DOM structure — element count + visible text + table cell text."""
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
                // Capture table cell text (detects status changes like 出席/遲到)
                let cellTexts = [];
                document.querySelectorAll('td').forEach(td => {
                    const t = (td.textContent || '').trim().slice(0, 20);
                    if (t) cellTexts.push(t);
                });
                const inputs = document.querySelectorAll('input, textarea, select').length;
                return JSON.stringify({count, inputs, btns: texts.sort().join('|'), cells: cellTexts.join('|')});
            }
        """)

    # ─── Run one step ───
    async def _run_step(self, page: Page, step: TestStep, label: str, step_idx: int):
        try:
            # 0. Auto-fill visible empty inputs BEFORE clicking (skip first step)
            if step_idx > 0:
                await self._auto_fill_empty_inputs(page)

            # 1. Snapshot before
            before = await self._snapshot(page)
            url_before = page.url

            # 2. Find + click button
            btn = await self._find_button(page, step.button, step.row)
            if not btn:
                self.recorder.fail(label, f"找不到按鈕: {step.button}")
                return

            try:
                await btn.click(timeout=5000)
            except Exception:
                await btn.click(force=True, timeout=5000)
            print(f"    → Clicked: {step.button}")
            await page.wait_for_timeout(2000)

            # 3. Fill explicit fields if any
            if step.fill_fields:
                await self._fill_fields(page, step.fill_fields)
                await page.wait_for_timeout(500)

            # 4. Snapshot after
            after = await self._snapshot(page)
            url_after = page.url

            # 5. Diff
            changed = before != after
            if not changed:
                # 5a. Wait longer for async operations (delete via confirm dialog)
                await page.wait_for_timeout(3000)
                after = await self._snapshot(page)
                changed = before != after
            if not changed:
                # 5b. Reload page to check if server-side change happened
                #     (e.g. delete succeeded but React didn't re-render)
                try:
                    await page.reload(wait_until="networkidle")
                    await page.wait_for_timeout(2000)
                    after = await self._snapshot(page)
                    changed = before != after
                except:
                    pass

            after_final = await self._snapshot(page) if not changed else after

            # 6. Report
            if changed or (before != after_final):
                import json
                snap = after_final if changed else after
                b, a = json.loads(before), json.loads(snap)
                d_el = a["count"] - b["count"]
                d_in = a["inputs"] - b["inputs"]
                parts = []
                if d_el: parts.append(f"DOM {b['count']}→{a['count']} ({'+' if d_el>0 else ''}{d_el})")
                if d_in: parts.append(f"inputs {b['inputs']}→{a['inputs']}")
                if url_before != page.url: parts.append(f"URL→{page.url}")
                if not parts: parts.append("按鈕文字變化")
                self.recorder.pass_(label, f"✓ {', '.join(parts)}")
            else:
                self.recorder.fail(label, "DOM 無變化，按鈕可能無效")

            # 7. Dismiss overlay only if step changed DOM and a backdrop exists
            try:
                has_overlay = await page.evaluate("""
                    () => {
                        const els = [...document.querySelectorAll('*')];
                        return els.some(el => {
                            const s = getComputedStyle(el);
                            return (s.position === 'fixed' || s.position === 'absolute')
                                && parseFloat(s.zIndex) > 100
                                && el.getBoundingClientRect().width > window.innerWidth * 0.5;
                        });
                    }
                """)
                if has_overlay:
                    await page.keyboard.press("Escape")
                    await page.wait_for_timeout(500)
            except:
                pass

            # 8. Only reload if nothing changed (reset dead state)
            final_changed = before != await self._snapshot(page)
            if not final_changed:
                try:
                    await page.reload(wait_until="networkidle")
                    await page.wait_for_timeout(2000)
                except:
                    pass

        except Exception as exc:
            print(f"    ✗ {exc}")
            self.recorder.fail(label, str(exc))

    # ─── Auto-fill visible empty inputs with test data ───
    async def _auto_fill_empty_inputs(self, page: Page):
        """Fill any visible empty input/textarea/select with generic test data.
        Only fills if a form is open (has visible text inputs)."""
        try:
            # Only fill if there are visible text inputs (form is open)
            text_inputs = await page.query_selector_all('input:not([type]), input[type="text"], input[type="email"], input[type="tel"], textarea')
            has_visible_text = False
            for el in text_inputs:
                try:
                    if await el.is_visible():
                        has_visible_text = True
                        break
                except:
                    pass
            if not has_visible_text:
                return  # No form open, don't touch selects

            # 1. Fill selects first (often required)
            selects = await page.query_selector_all("select")
            for sel in selects:
                try:
                    if await sel.is_visible():
                        opts = await sel.query_selector_all("option")
                        for opt in opts[1:]:  # skip placeholder
                            ov = await opt.get_attribute("value")
                            if ov:
                                await sel.select_option(value=ov)
                                print(f"    → Auto-filled select: {ov}")
                                break
                except:
                    pass
            # 2. Fill text inputs
            for el in text_inputs:
                try:
                    if not await el.is_visible():
                        continue
                    val = await el.input_value()
                    if val.strip():
                        continue
                    ph = await el.get_attribute("placeholder") or ""
                    el_id = await el.get_attribute("id") or ""
                    if "phone" in ph.lower() or "phone" in el_id.lower() or "電" in ph:
                        await el.fill("0900000000")
                    elif "email" in ph.lower():
                        await el.fill("test@test.com")
                    elif "name" in ph.lower() or "name" in el_id.lower() or "名" in ph:
                        await el.fill("E2E測試")
                    else:
                        await el.fill("test_data")
                    print(f"    → Auto-filled: {ph or el_id or 'input'}")
                except:
                    pass
        except:
            pass

    # ─── Confirm retry: click newly visible button if DOM unchanged ───
    async def _try_confirm_retry(self, page: Page, before_snap: str, step: TestStep) -> bool:
        """If click didn't change DOM, maybe a confirm dialog appeared.
        Try clicking any newly visible button that looks like confirm/delete."""
        import json
        try:
            b = json.loads(before_snap)
            b_texts = set(b.get("btns", "").split("|"))
            # Look for confirm-like buttons
            for btn in await page.query_selector_all("button"):
                try:
                    if not await btn.is_visible():
                        continue
                    bt = (await btn.inner_text()).strip()
                    if bt and bt not in b_texts:
                        # Click it (it's newly visible)
                        await btn.click(timeout=3000)
                        await page.wait_for_timeout(2000)
                        print(f"    → Confirm retry clicked: {bt}")
                        return True
                except:
                    continue
        except:
            pass
        return False

    # ─── Find button (supports row index for repeated buttons) ───
    async def _find_button(self, page: Page, text: str, row: int = 0):
        if not text:
            return None
        # If row specified, find buttons inside table rows
        if row > 0:
            rows = await page.query_selector_all("tr")
            # row is 1-based occurrence, not DOM index
            matched = 0
            for tr in rows:
                btns = await tr.query_selector_all("button")
                for btn in btns:
                    try:
                        bt = (await btn.inner_text()).strip()
                        vis = await btn.is_visible()
                        if text in bt and vis:
                            matched += 1
                            if matched == row:
                                return btn
                    except:
                        continue
            print(f"    → Row {row} button '{text}' not found (only {matched} matches)")
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
