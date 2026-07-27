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

        # Login: go directly to login URL
        if login_url and username:
            try:
                print(f"  → Login: {login_url}")
                await page.goto(login_url, wait_until="networkidle")
                await page.wait_for_timeout(2000)

                # Fill login form (placeholder-based SPA forms)
                u_sel = 'input[placeholder*="帳號"], input[placeholder*="account"], input[type="text"]'
                await page.locator(u_sel).first.fill(username)
                await page.wait_for_timeout(300)

                p_sel = 'input[type="password"]'
                await page.locator(p_sel).first.fill(password)
                await page.wait_for_timeout(300)

                await page.get_by_role("button", name="登入").click()
                await page.wait_for_timeout(3000)
                print(f"  → Logged in: {page.url}")
            except Exception as e:
                print(f"  → Login failed: {e}")

        # SPA-aware navigation: after login we're already on the SPA.
        # Doing page.goto(url) would reload the entire app and the router
        # resets to the home page, losing the deep-link target.
        # Instead, navigate within the SPA using client-side routing.
        from urllib.parse import urlparse
        target_path = urlparse(url).path  # e.g. /t/{tenant}/ctb/users

        if target_path and target_path != "/":
            # SPA navigation: expand sidebar groups + click target link in one JS call
            navigated = False
            try:
                clicked = await page.evaluate("""(path) => {
                    // Expand all collapsed sidebar groups
                    document.querySelectorAll('[class*="sidebar-divider"]').forEach(el => {
                        if (el.textContent.includes('\u25b8')) el.click();
                    });
                    // Small delay then click target link
                    return new Promise(resolve => {
                        setTimeout(() => {
                            const links = document.querySelectorAll('a[href]');
                            for (const a of links) {
                                if (a.getAttribute('href').indexOf(path) !== -1) {
                                    a.click();
                                    resolve(true);
                                    return;
                                }
                            }
                            resolve(false);
                        }, 800);
                    });
                }""", target_path)
                if clicked:
                    await page.wait_for_timeout(3000)
                    if target_path in page.url:
                        print(f"  → SPA nav: {page.url}")
                        navigated = True
                    else:
                        print(f"  → Link clicked but URL unchanged ({page.url})")
            except Exception as e:
                print(f"  → SPA nav failed ({e})")

            if not navigated:
                print(f"  → Fallback goto (may reset to home)")
                await page.goto(url, wait_until="networkidle")
                await page.wait_for_timeout(2000)
        else:
            await page.goto(url, wait_until="networkidle")
            await page.wait_for_timeout(2000)

        # Wait for SPA content to render
        try:
            await page.wait_for_selector("#main-container > *", timeout=10000)
            await page.wait_for_timeout(1000)
        except Exception:
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

        # ── Deep scan: click non-destructive buttons → record form structure (no submit) ──
        seen_texts = {b["text"] for b in dom_info.get("buttons", [])}
        skip = {"登出", "Logout", "Sign out", "☰"}
        destructive = {"刪除", "delete", "remove", "移除", "清除", "clear"}

        for btn_info in list(dom_info.get("buttons", [])):
            btn_text = btn_info["text"]
            if btn_text in skip:
                continue
            if any(d in btn_text.lower() for d in destructive):
                continue
            try:
                btn = page.locator(f'button:has-text("{btn_text}")').first
                if not await btn.is_visible():
                    continue
                if not await btn.is_enabled():
                    continue
                print(f"  → Deep scan: clicking [{btn_text}]...")
                await btn.click()
                await page.wait_for_timeout(2000)

                # Check if click revealed a form (new inputs appeared)
                dom_after = await page.evaluate(extract_js)
                new_inputs = dom_after.get("inputs", [])

                if new_inputs:
                    print(f"    Form revealed ({len(new_inputs)} inputs), recording structure (no submit)")

                    # Record form structure — do NOT fill or submit
                    for inp in new_inputs:
                        if inp not in dom_info["inputs"]:
                            dom_info["inputs"].append(inp)
                    for b2 in dom_after.get("buttons", []):
                        if b2["text"] not in seen_texts:
                            dom_info["buttons"].append(b2)
                            seen_texts.add(b2["text"])

                    # Close the form (click cancel/close) to restore page state
                    for close_text in ["取消", "Cancel", "關閉", "Close", "✕"]:
                        try:
                            close_btn = page.locator(f'button:has-text("{close_text}")').first
                            if await close_btn.is_visible():
                                await close_btn.click()
                                await page.wait_for_timeout(1000)
                                break
                        except:
                            pass

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
