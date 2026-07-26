"""
Page Inspector — crawls a web page and builds a rich interactive element map.

Key difference from v1:
  Instead of extracting flat lists and asking the LLM to guess CSS selectors,
  the Inspector uses Playwright's built-in locator strategies to compute
  MULTIPLE reliable locators per element, ranked by reliability.

  The LLM PICKs elements from the map — it doesn't GUESS selectors.
"""

import asyncio
import re
from typing import Any, Dict, List, Optional, Tuple


async def inspect_page(
    url: str,
    login_url: str = "",
    username: str = "",
    password: str = "",
    wait_for_selector: str = "",
) -> Dict[str, Any]:
    """Navigate to a page and build a rich interactive element map.

    Returns:
        {
            "url": str,
            "title": str,
            "elements": [
                {
                    "id": int,           # unique element id
                    "tag": str,          # button | input | select | textarea | a
                    "role": str,         # ARIA role for Playwright get_by_role
                    "type": str,         # input type (text, checkbox, submit...)
                    "name": str,         # name attribute (for form fields)
                    "label": str,        # associated label text
                    "text": str,         # visible text content
                    "placeholder": str,
                    "aria_label": str,
                    "data_testid": str,
                    "locators": [str],   # Playwright locator strings, ranked
                    "is_visible": bool,
                    "options": [str],    # for select elements
                }
            ],
            "structure": {              # page section hierarchy
                "headings": [...],
                "sections": [...],
            }
        }
    """
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ],
        )
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            locale="zh-TW",
        )
        page = await context.new_page()
        page.set_default_timeout(20000)

        # Anti-detection
        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        """)

        load_state = "domcontentloaded"

        # Login if needed
        if login_url and username:
            try:
                await page.goto(login_url, wait_until=load_state, timeout=15000)
                await page.wait_for_timeout(1500)

                # Multi-step login: check for tenant page first
                tenant_input = page.get_by_placeholder("輸入租戶 ID")
                if await tenant_input.count() > 0:
                    await tenant_input.fill(username)
                    await page.get_by_role("button", name="進入").click()
                    await page.wait_for_timeout(2000)

                # Fill credentials (works for both tenant-login and direct-login)
                for acct in [page.get_by_placeholder("帳號"), page.locator('input[name="username"]')]:
                    try:
                        await acct.fill("admin")
                        break
                    except Exception:
                        pass

                for pwd in [page.get_by_placeholder("密碼"), page.locator('input[name="password"], input[type="password"]')]:
                    try:
                        await pwd.fill(password)
                        break
                    except Exception:
                        pass

                login = page.get_by_role("button").filter(has_text=re.compile(r"登入"))
                if await login.count() > 0:
                    await login.first.click()
                    await page.wait_for_timeout(2000)
            except Exception:
                pass

        # Navigate to target
        try:
            await page.goto(url, wait_until=load_state, timeout=20000)
        except Exception:
            pass
        # Wait for the page to settle
        try:
            await page.wait_for_load_state("networkidle", timeout=5000)
        except Exception:
            pass  # network may never idle on some pages
        if wait_for_selector:
            try:
                await page.wait_for_selector(wait_for_selector, timeout=10000)
            except Exception:
                pass
        await page.wait_for_timeout(1500)

        # Extract rich element data via JavaScript
        result = await page.evaluate("""() => {
            const elements = [];
            let nextId = 1;

            // Helper: compute locator strategies for an element
            function computeLocators(el) {
                const locs = [];

                // 1) data-testid (most reliable, if present)
                const tid = el.getAttribute('data-testid') || el.getAttribute('data-test-id');
                if (tid) {
                    locs.push(`[data-testid="${tid}"]`);
                    locs.push(`get_by_test_id:${tid}`);
                }

                // 2) id attribute (reliable if it exists and is reasonably unique)
                if (el.id && el.id.length > 2) {
                    locs.push(`#${CSS.escape(el.id)}`);
                }

                // 3) ARIA label
                const ariaLabel = el.getAttribute('aria-label');
                if (ariaLabel) {
                    locs.push(`get_by_role:${el.role || el.tagName.toLowerCase()}:name=${ariaLabel}`);
                    locs.push(`[aria-label="${ariaLabel.replace(/"/g, '\\"')}"]`);
                }

                // 4) Label association (for form inputs)
                if (el.id) {
                    const label = document.querySelector(`label[for="${el.id}"]`);
                    if (label) {
                        locs.push(`get_by_label:${label.textContent.trim()}`);
                    }
                }

                // 5) Name attribute (for form elements)
                if (el.name) {
                    // Use the most specific selector with type if available
                    const tag = el.tagName.toLowerCase();
                    if (el.type && el.type !== 'text') {
                        locs.push(`${tag}[name="${el.name}"][type="${el.type}"]`);
                    }
                    locs.push(`${tag}[name="${el.name}"]`);
                }

                // 6) Placeholder
                if (el.placeholder) {
                    locs.push(`get_by_placeholder:${el.placeholder}`);
                    locs.push(`${el.tagName.toLowerCase()}[placeholder="${el.placeholder.replace(/"/g, '\\"')}"]`);
                }

                // 7) Visible text content (for buttons/links)
                const text = (el.textContent || '').trim();
                if (text && text.length < 60 && !el.name && !el.placeholder) {
                    if (el.role === 'button' || el.tagName === 'BUTTON' || el.tagName === 'A') {
                        locs.push(`get_by_role:button:name=${text}`);
                        locs.push(`get_by_text:${text}`);
                    }
                }

                return locs;
            }

            // Helper: find the closest label text (walks up parent chain)
            function findLabel(el) {
                // Check aria-labelledby
                const labelledby = el.getAttribute('aria-labelledby');
                if (labelledby) {
                    const lbl = document.getElementById(labelledby);
                    if (lbl) return lbl.textContent.trim();
                }
                // Check parent label
                let parent = el.parentElement;
                for (let i = 0; i < 5 && parent; i++) {
                    const lbl = parent.querySelector('label');
                    if (lbl) return lbl.textContent.trim();
                    parent = parent.parentElement;
                }
                // Check preceding label in same form-group
                const group = el.closest('.form-group, .field, .input-group, .mb-3, [class*="field"]');
                if (group) {
                    const lbl = group.querySelector('label');
                    if (lbl) return lbl.textContent.trim();
                }
                return '';
            }

            // ── Collect all buttons ──
            document.querySelectorAll('button, a[role="button"], input[type="submit"], input[type="button"]').forEach(el => {
                const text = (el.textContent || el.value || '').trim().substring(0, 60);
                if (!text && !(el.getAttribute('aria-label'))) return;

                const rect = el.getBoundingClientRect();
                const isVisible = rect.width > 0 && rect.height > 0;

                elements.push({
                    id: nextId++,
                    tag: el.tagName.toLowerCase(),
                    type: el.type || '',
                    role: el.getAttribute('role') || (el.tagName === 'BUTTON' ? 'button' : ''),
                    name: el.name || '',
                    text: text,
                    aria_label: el.getAttribute('aria-label') || '',
                    data_testid: el.getAttribute('data-testid') || el.getAttribute('data-test-id') || '',
                    locators: computeLocators(el),
                    is_visible: isVisible,
                    category: 'action',  // clickable element
                });
            });

            // ── Collect form inputs (text, select, textarea, checkbox, radio) ──
            document.querySelectorAll('input:not([type="hidden"]):not([type="submit"]):not([type="button"]), select, textarea').forEach(el => {
                const label = findLabel(el);
                const options = el.tagName === 'SELECT'
                    ? [...el.options].map(o => o.textContent.trim()).filter(Boolean)
                    : [];

                elements.push({
                    id: nextId++,
                    tag: el.tagName.toLowerCase(),
                    type: el.type || '',
                    role: el.getAttribute('role') || '',
                    name: el.name || '',
                    label: label,
                    text: '',
                    placeholder: el.placeholder || '',
                    aria_label: el.getAttribute('aria-label') || '',
                    data_testid: el.getAttribute('data-testid') || el.getAttribute('data-test-id') || '',
                    locators: computeLocators(el),
                    is_visible: true,
                    category: 'input',
                    options: options,
                    required: el.required || false,
                });
            });

            // ── Collect links (navigational) ──
            document.querySelectorAll('a[href]:not([role="button"])').forEach(el => {
                const text = (el.textContent || '').trim().substring(0, 60);
                if (!text) return;

                elements.push({
                    id: nextId++,
                    tag: 'a',
                    type: '',
                    role: 'link',
                    name: '',
                    text: text,
                    placeholder: '',
                    aria_label: el.getAttribute('aria-label') || '',
                    data_testid: el.getAttribute('data-testid') || el.getAttribute('data-test-id') || '',
                    locators: computeLocators(el),
                    is_visible: true,
                    category: 'nav',
                    href: el.getAttribute('href') || '',
                });
            });

            // Collect page headings for structure
            const headings = [];
            document.querySelectorAll('h1, h2, h3').forEach(h => {
                const text = (h.textContent || '').trim();
                if (text) headings.push({ level: h.tagName.toLowerCase(), text: text });
            });

            return {
                url: document.location.href,
                title: document.title,
                elements: elements,
                headings: headings,
                total_elements: elements.length,
            };
        }""")

        await browser.close()
        return result


def crawl_page(
    url: str,
    login_url: str = "",
    username: str = "",
    password: str = "",
    wait_for_selector: str = "",
) -> Dict[str, Any]:
    """Sync wrapper for inspect_page."""
    return asyncio.run(
        inspect_page(url, login_url, username, password, wait_for_selector)
    )