"""
Page crawler — extracts DOM structure for AI analysis.

Launches headless Playwright, navigates to the page,
extracts all interactive elements (buttons, form inputs, tables)
so the LLM can analyze the actual page structure.
"""

import asyncio
import json
import os
from typing import Dict, Any, List, Optional


async def _crawl_page(url: str, login_url: str = "", username: str = "", password: str = "") -> Dict[str, Any]:
    """Crawl a page and extract DOM structure."""
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
            executable_path=os.path.expanduser("~/.cache/ms-playwright/chromium_headless_shell-1228/chrome-linux/headless_shell"),
        )
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            locale="zh-TW",
        )
        page = await context.new_page()
        page.set_default_timeout(15000)

        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        """)

        # Login if needed
        if login_url and username:
            try:
                print(f"  → Login: {login_url}")
                await page.goto(login_url, wait_until="networkidle")
                await page.wait_for_timeout(2000)

                # Fill username (try name attr first, then type=text, then placeholder)
                u_sel = 'input[name="username"]'
                if not await page.locator(u_sel).count():
                    u_sel = 'input[type="text"]'
                if not await page.locator(u_sel).count():
                    u_sel = 'input[placeholder*="帳號"]'
                await page.locator(u_sel).first.fill(username)
                await page.wait_for_timeout(300)

                # Fill password
                p_sel = 'input[name="password"]'
                if not await page.locator(p_sel).count():
                    p_sel = 'input[type="password"]'
                await page.locator(p_sel).first.fill(password)
                await page.wait_for_timeout(300)

                # Click login button
                await page.get_by_role("button", name="登入").click()
                await page.wait_for_timeout(3000)
            except Exception as e:
                print(f"  → Login failed: {e}")

        # Navigate to target page
        await page.goto(url, wait_until="networkidle")
        await page.wait_for_timeout(2000)

        # SPA support: Wait for content to render
        # Check if page appears to be an SPA (empty main container, many scripts)
        is_spa = await page.evaluate("""
            () => {
                const main = document.getElementById('main-container');
                return main && main.children.length === 0;
            }
        """)

        if is_spa:
            # Wait for SPA to render content
            try:
                await page.wait_for_selector("#main-container > *", timeout=10000)
                await page.wait_for_timeout(1000)  # Extra buffer for animations
            except Exception:
                # Fallback: wait for any content to appear
                await page.wait_for_timeout(3000)

        # Extract DOM info via JavaScript
        extract_js = """() => {
            const result = { buttons: [], forms: [], inputs: [], links: [], tables: [], tableRows: [] };
            const seenBtns = {};

            // Detect buttons inside table rows with row context
            document.querySelectorAll('tr').forEach((tr, rowIdx) => {
                const cells = tr.querySelectorAll('th, td');
                if (!cells.length) return;
                // Get row label (first cell text)
                const rowLabel = (cells[0].textContent || '').trim().slice(0, 30);
                const rowBtns = [];
                tr.querySelectorAll('button').forEach(btn => {
                    const text = (btn.textContent || '').trim();
                    if (text && text.length < 50) {
                        rowBtns.push(text);
                        // Global button list with row info
                        const key = text;
                        if (!seenBtns[key]) seenBtns[key] = 0;
                        seenBtns[key]++;
                        result.buttons.push({ text, row: rowIdx, rowLabel, occurrence: seenBtns[key], isRepeated: false });
                    }
                });
                if (rowBtns.length) {
                    result.tableRows.push({ index: rowIdx, label: rowLabel, buttons: rowBtns });
                }
            });

            // Non-table buttons
            document.querySelectorAll('button').forEach(btn => {
                if (btn.closest('tr')) return; // skip table buttons (already captured)
                const text = (btn.textContent || '').trim();
                if (text && text.length < 50) {
                    result.buttons.push({ text, row: 0, rowLabel: '', occurrence: 1, isRepeated: false });
                }
            });

            // Mark repeated buttons
            const counts = {};
            result.buttons.forEach(b => { counts[b.text] = (counts[b.text]||0) + 1; });
            result.buttons.forEach(b => { if (counts[b.text] > 1) b.isRepeated = true; });

            document.querySelectorAll('input, select, textarea').forEach(inp => {
                const label = (() => {
                    if (inp.id) { const lbl = document.querySelector('label[for="' + inp.id + '"]'); if (lbl) return lbl.textContent.trim(); }
                    const parent = inp.closest('.form-group, .form-field, label, .field');
                    if (parent) { const lbl = parent.querySelector('label'); if (lbl) return lbl.textContent.trim(); }
                    return '';
                })();
                result.inputs.push({
                    tag: inp.tagName.toLowerCase(), type: inp.type || '', name: inp.name || '',
                    id: inp.id || '', placeholder: inp.placeholder || '', label: label,
                    className: inp.className || '',
                    options: inp.tagName === 'SELECT' ? [...inp.options].map(o => o.textContent.trim()).slice(0, 10) : [],
                });
            });
            document.querySelectorAll('table thead th').forEach(th => {
                const text = (th.textContent || '').trim();
                if (text) result.tables.push(text);
            });
            const h1 = document.querySelector('h1'); const h2 = document.querySelector('h2');
            result.title = h1 ? h1.textContent.trim() : h2 ? h2.textContent.trim() : '';
            return result;
        }"""

        dom_info = await page.evaluate(extract_js)

        # ── Deep scan: click each button → fill form if revealed → save → collect new buttons ──
        # Generic DOM diff approach: no hardcoded keywords.
        seen_texts = {b["text"] for b in dom_info.get("buttons", [])}
        skip = {"登出", "Logout", "Sign out", "☰"}

        for btn_info in list(dom_info.get("buttons", [])):
            btn_text = btn_info["text"]
            if btn_text in skip:
                continue
            try:
                btn = page.locator(f'button:has-text("{btn_text}")').first
                if not await btn.is_visible():
                    continue
                print(f"  → Deep scan: clicking [{btn_text}]...")
                await btn.click()
                await page.wait_for_timeout(2000)

                # Check if click revealed a form (new inputs appeared)
                dom_after = await page.evaluate(extract_js)
                new_inputs = dom_after.get("inputs", [])

                if new_inputs:
                    print(f"    Form revealed ({len(new_inputs)} inputs), filling...")
                    # Fill all visible text inputs generically
                    for inp_el in await page.query_selector_all('input:not([type="hidden"]):not([type="submit"]):not([type="button"]), textarea'):
                        tag = await inp_el.evaluate("e => e.tagName.toLowerCase()")
                        itype = await inp_el.evaluate("e => e.type")
                        if tag == "select" or itype == "select":
                            try: await inp_el.select_option(index=1)
                            except: pass
                            continue
                        ph = await inp_el.get_attribute('placeholder') or ''
                        val = "test_" + (ph[:10] if ph else "input")
                        if itype in ("email",):
                            val = "test@test.com"
                        elif itype in ("tel", "number"):
                            val = "0912345678"
                        elif itype in ("password",):
                            continue
                        try: await inp_el.fill(val)
                        except: pass
                    # Fill selects
                    for sel_el in await page.query_selector_all('select'):
                        try: await sel_el.select_option(index=1)
                        except: pass

                    # Find & click a submit button in the new DOM
                    for b2 in dom_after.get("buttons", []):
                        if b2["text"] in skip:
                            continue
                        if b2["text"] in seen_texts:
                            continue
                        # Heuristic: submit buttons often last, click first new non-cancel button
                        if "取消" in b2["text"] or "Cancel" in b2["text"]:
                            continue
                        try:
                            sub_btn = page.locator(f'button:has-text("{b2["text"]}")').first
                            if await sub_btn.is_visible():
                                print(f"    Clicking [{b2['text']}] to submit...")
                                await sub_btn.click()
                                await page.wait_for_timeout(3000)
                                break
                        except: pass

                # Final snapshot after interaction
                dom_final = await page.evaluate(extract_js)
                for b3 in dom_final.get("buttons", []):
                    if b3["text"] not in seen_texts:
                        dom_info["buttons"].append(b3)
                        seen_texts.add(b3["text"])
                        print(f"    + Found: {b3['text']}")

                # Reload to reset state
                await page.goto(url, wait_until="networkidle")
                await page.wait_for_timeout(2000)
            except Exception as e:
                print(f"    ✗ {e}")
                try:
                    await page.goto(url, wait_until="networkidle")
                    await page.wait_for_timeout(2000)
                except: pass

        await browser.close()
        return dom_info


def crawl_page(url: str, login_url: str = "", username: str = "", password: str = "") -> Dict[str, Any]:
    """Sync wrapper for _crawl_page."""
    return asyncio.run(_crawl_page(url, login_url, username, password))
