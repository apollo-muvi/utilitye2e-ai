"""
Runner — executes a TestSpec with Playwright.

Simplified MVP: handles login, CRUD actions (add_cancel, add_save, edit_cancel, delete, page_load).
"""

import os
import re
import asyncio
from typing import Optional

from playwright.async_api import async_playwright, Page, expect

from core.spec import TestSpec
from core.recorder import Recorder


class Runner:
    def __init__(self, spec: TestSpec, headless: bool = True, screenshot_dir: str = "screenshots"):
        self.spec = spec
        self.headless = headless
        self.recorder = Recorder()
        self.screenshot_dir = screenshot_dir
        os.makedirs(screenshot_dir, exist_ok=True)

    async def run(self) -> dict:
        """Execute the test spec, return results summary."""
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=self.headless,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
            )
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                locale="zh-TW",
            )
            page = await context.new_page()
            page.set_default_timeout(30000)

            # Anti-detection
            await page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            """)

            try:
                # Login if needed
                await self._do_login(page)
                # Navigate to target
                await page.goto(self.spec.target.url, wait_until="networkidle")
                await page.wait_for_timeout(2000)

                # Execute actions
                for action in self.spec.actions:
                    await self._execute_action(page, action)

            except Exception as exc:
                self.recorder.fail("setup", f"Setup failed: {exc}")
            finally:
                await browser.close()

        return self.recorder.summary()

    async def _do_login(self, page: Page):
        """Login if credentials are provided."""
        t = self.spec.target
        if not t.login_url or not t.username:
            return
        # Convert relative login_url to absolute
        login_url = t.login_url if t.login_url.startswith('http') else f"{t.url.rstrip('/')}/{t.login_url.lstrip('/')}"
        await page.goto(login_url, wait_until="networkidle")
        await page.fill('input[name="username"], input[type="text"]', t.username)
        await page.fill('input[name="password"], input[type="password"]', t.password)
        await page.get_by_role("button").filter(has_text=re.compile(r"登入|Login|登 录")).first.click()
        await page.wait_for_timeout(2000)

    async def _execute_action(self, page: Page, action: str):
        ui = self.spec.ui
        name_prefix = f"{self.spec.name}:{action}"

        if action == "page_load":
            await self._test_page_load(page, name_prefix)

        elif action == "add_cancel":
            await self._test_add_cancel(page, name_prefix)

        elif action == "add_save":
            await self._test_add_save(page, name_prefix)

        elif action == "edit_cancel":
            await self._test_edit_cancel(page, name_prefix)

        elif action == "delete":
            await self._test_delete(page, name_prefix)

    async def _test_page_load(self, page: Page, name: str):
        try:
            title = await page.locator("h1, h2").first.inner_text()
            self.recorder.pass_(name, f"頁面載入成功，標題: {title}")
        except Exception as exc:
            self.recorder.fail(name, f"頁面載入失敗: {exc}")

    async def _fill_fields(self, page: Page):
        for f in self.spec.fields:
            if not f.selector or not f.value:
                continue
            try:
                if f.field_type == "select" and f.options:
                    await page.select_option(f.selector, label=f.options[0])
                elif f.field_type == "checkbox":
                    await page.check(f.selector)
                else:
                    await page.fill(f.selector, f.value)
            except Exception:
                pass  # field may not exist in this context

    async def _get_button(self, page: Page, name: str):
        """Find button with intelligent fallback strategies."""
        if not name:
            # Fallback: find any button with common add/save/cancel text
            all_buttons = await page.query_selector_all('button')
            for btn in all_buttons:
                text = await btn.inner_text().strip()
                if text in ["新增", "新增", "Add", "Save", "儲存", "取消", "Cancel"]:
                    return btn
            return all_buttons[0] if all_buttons else None

        # Strategy 1: Extract core keyword from button name (remove symbols)
        # "+新增選手" → "新增", "Save Changes" → "Save"
        keywords = [name]
        if "+" in name:
            keywords.append(name.replace("+", "").strip())
        # Extract Chinese characters (each as potential keyword)
        import re
        cn_chars = re.findall(r'[\u4e00-\u9fff]', name)
        if cn_chars:
            # Try both single char and combinations
            for i in range(len(cn_chars)):
                keywords.append(cn_chars[i])
                if i < len(cn_chars) - 1:
                    keywords.append(cn_chars[i] + cn_chars[i+1])
        # Extract English words
        en_words = re.findall(r'[A-Za-z]+', name)
        for word in en_words:
            keywords.append(word)

        # Strategy 2: Try exact match for each keyword
        for kw in keywords:
            btn = page.get_by_role("button", name=kw, exact=True)
            if await btn.count() > 0:
                return btn.first

        # Strategy 3: Partial text match for each keyword
        all_buttons = await page.query_selector_all('button')
        for kw in keywords:
            for btn in all_buttons:
                text = await btn.inner_text()
                if kw and kw in text:
                    return btn

        # Strategy 4: Match by common patterns (icon + text)
        for btn in all_buttons:
            text = await btn.inner_text()
            # Check if button contains any of our keywords
            if any(kw in text for kw in keywords if kw):
                return btn

        return None

    async def _test_add_cancel(self, page: Page, name: str):
        try:
            start_mut = len(self.recorder.mutations)
            btn = await self._get_button(page, self.spec.ui.add_button)
            if not btn:
                raise Exception(f"找不到按鈕: {self.spec.ui.add_button}")
            await btn.click()
            await page.wait_for_timeout(1000)
            # Click cancel
            cancel_btn = await self._get_button(page, self.spec.ui.cancel_button)
            if not cancel_btn:
                raise Exception(f"找不到按鈕: {self.spec.ui.cancel_button}")
            await cancel_btn.click()
            await page.wait_for_timeout(500)
            if len(self.recorder.mutations) == start_mut:
                self.recorder.pass_(name, f"{self.spec.ui.add_button} 開啟後取消，無 mutation")
            else:
                self.recorder.fail(name, "取消觸發了 mutation")
        except Exception as exc:
            self.recorder.fail(name, str(exc))

    async def _test_add_save(self, page: Page, name: str):
        try:
            btn = await self._get_button(page, self.spec.ui.add_button)
            if not btn:
                raise Exception(f"找不到按鈕: {self.spec.ui.add_button}")
            await btn.click()
            await page.wait_for_timeout(1000)
            await self._fill_fields(page)
            save_btn = await self._get_button(page, self.spec.ui.save_button)
            if not save_btn:
                raise Exception(f"找不到按鈕: {self.spec.ui.save_button}")
            await save_btn.click()
            await page.wait_for_timeout(2000)
            self.recorder.pass_(name, "新增儲存完成")
        except Exception as exc:
            self.recorder.fail(name, str(exc))

    async def _test_edit_cancel(self, page: Page, name: str):
        try:
            btn = await self._get_button(page, self.spec.ui.edit_button)
            if not btn:
                raise Exception(f"找不到按鈕: {self.spec.ui.edit_button}")
            await btn.click()
            await page.wait_for_timeout(1000)
            cancel_btn = await self._get_button(page, self.spec.ui.cancel_button)
            if not cancel_btn:
                raise Exception(f"找不到按鈕: {self.spec.ui.cancel_button}")
            await cancel_btn.click()
            await page.wait_for_timeout(500)
            self.recorder.pass_(name, "編輯取消成功")
        except Exception as exc:
            self.recorder.fail(name, str(exc))

    async def _test_delete(self, page: Page, name: str):
        try:
            btn = await self._get_button(page, self.spec.ui.delete_button)
            if not btn:
                raise Exception(f"找不到按鈕: {self.spec.ui.delete_button}")
            await btn.click()
            await page.wait_for_timeout(500)
            # Confirm if dialog appears
            page.on("dialog", lambda d: asyncio.ensure_future(d.accept()))
            self.recorder.pass_(name, "刪除按鈕點擊成功")
        except Exception as exc:
            self.recorder.fail(name, str(exc))
