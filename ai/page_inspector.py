"""
Page Inspector v2 — crawls a web page and builds a rich interactive element map.
"""

import asyncio
import json
import re
from typing import Any, Dict


def _get_strategies_json() -> str:
    """Load locator strategies from YAML, return as JSON string for JS injection."""
    from core.locator_resolver import LocatorResolver
    resolver = LocatorResolver.from_yaml()
    return resolver.get_strategies_js()


async def inspect_page(
    url: str,
    login_url: str = "",
    username: str = "",
    password: str = "",
    wait_for_selector: str = "",
) -> Dict[str, Any]:
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
        )
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            locale="zh-TW",
        )
        page = await context.new_page()
        page.set_default_timeout(20000)

        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        """)

        load_state = "domcontentloaded"

        # Login if needed
        if login_url and username:
            try:
                await page.goto(login_url, wait_until=load_state, timeout=15000)
                await page.wait_for_timeout(1500)

                tenant_input = page.get_by_placeholder("輸入租戶 ID")
                if await tenant_input.count() > 0:
                    await tenant_input.fill(username)
                    await page.get_by_role("button", name="進入").click()
                    await page.wait_for_timeout(2000)

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
        try:
            await page.wait_for_load_state("networkidle", timeout=5000)
        except Exception:
            pass
        if wait_for_selector:
            try:
                await page.wait_for_selector(wait_for_selector, timeout=10000)
            except Exception:
                pass
        await page.wait_for_timeout(1500)

        # Extract element map via JavaScript
        strategies_json = _get_strategies_json()
        result = await page.evaluate("""(strategiesJson) => {
            const strategies = JSON.parse(strategiesJson);
            const elements = [];
            let nextId = 1;

            // ── Data-driven locator engine ──────────────────────
            // No hardcoded selector logic. Everything driven by strategies config.

            function extractAttrValue(el, attrs) {
                for (const a of attrs) {
                    const v = el.getAttribute(a);
                    if (v) return { attr: a, value: v };
                }
                return null;
            }

            function evalCondition(expr, el, value) {
                if (!expr) return true;
                try {
                    const tag = el.tagName.toLowerCase();
                    const role = el.getAttribute('role') || '';
                    return Function('el', 'value', 'tag', 'role',
                        `return (${expr});`
                    )(el, value, tag, role);
                } catch(e) { return false; }
            }

            function extractValue(el, strategy) {
                const vf = strategy.value_from;
                if (vf === 'attr_value') {
                    const r = extractAttrValue(el, strategy.attrs);
                    return r ? r.value : '';
                }
                if (vf === 'text_content') {
                    return (el.textContent || '').trim().substring(0, 60);
                }
                if (vf === 'label_text_for_id') {
                    const id = el.id;
                    if (!id) return '';
                    const lbl = document.querySelector(`label[for="${id}"]`);
                    return lbl ? lbl.textContent.trim() : '';
                }
                return '';
            }

            function formatLocator(strategy, el, value, attr) {
                const p = strategy.prefix;
                const tag = el.tagName.toLowerCase();

                // get_by_test_id:<value>
                if (p === 'get_by_test_id')
                    return `get_by_test_id:${value}`;

                // get_by_role:<role>:name=<name>
                if (p === 'get_by_role') {
                    let role = '';
                    if (strategy.role_from) {
                        try {
                            role = Function('el',
                                `const tag = el.tagName.toLowerCase();
                                 const role = el.getAttribute('role') || '';
                                 return (${strategy.role_from});`
                            )(el);
                        } catch(e) {
                            role = el.getAttribute('role') || tag;
                        }
                    } else {
                        role = el.getAttribute('role') || tag;
                    }
                    return `get_by_role:${role}:name=${value}`;
                }

                // get_by_label:<label>
                if (p === 'get_by_label')
                    return `get_by_label:${value}`;

                // get_by_placeholder:<value>
                if (p === 'get_by_placeholder')
                    return `get_by_placeholder:${value}`;

                // get_by_text:<text>
                if (p === 'get_by_text')
                    return `get_by_text:${value}`;

                // get_by_title:<value>
                if (p === 'get_by_title')
                    return `get_by_title:${value}`;

                // css_id → #<value>
                if (p === 'css_id')
                    return `css_id:${value}`;

                // css_attr → [{attr}="{value}"]  (stored as css:...)
                if (p === 'css_attr') {
                    if (strategy.value_template) {
                        return `css:${strategy.value_template
                            .replace('{value}', value.replace(/"/g, '\\\\"'))
                            .replace('{attr}', attr || strategy.attrs[0])
                            .replace('{tag}', tag)}`;
                    }
                    return `css:[${attr || strategy.attrs[0]}="${value}"]`;
                }

                return '';
            }

            function computeLocators(el) {
                const locs = [];
                for (const s of strategies) {
                    // Check condition first (if defined)
                    // For attr-based strategies, extract value to test condition
                    let value = '';
                    let attr = '';

                    if (s.attrs && s.attrs.length > 0) {
                        const r = extractAttrValue(el, s.attrs);
                        if (!r) continue;
                        value = r.value;
                        attr = r.attr;
                    } else if (s.value_from === 'text_content') {
                        value = (el.textContent || '').trim().substring(0, 60);
                    }

                    if (!value) continue;

                    // Evaluate condition
                    if (!evalCondition(s.condition, el, value)) continue;

                    // For label_text_for_id, value is extracted differently
                    if (s.value_from === 'label_text_for_id') {
                        value = extractValue(el, s);
                        if (!value) continue;
                    }

                    const loc = formatLocator(s, el, value, attr);
                    if (loc) locs.push(loc);
                }

                // Always add a text-based fallback for buttons/links
                const text = (el.textContent || '').trim();
                if (text && text.length < 60 && text.length >= 2) {
                    if (el.role === 'button' || el.tagName === 'BUTTON' || el.tagName === 'A') {
                        const cleanText = text.replace(/^[+\\-*·•\\s]+/, '').trim();
                        if (cleanText && cleanText.length >= 2) {
                            // Avoid duplicates
                            if (!locs.some(l => l.includes(cleanText)))
                                locs.push(`get_by_text:${cleanText}`);
                        }
                    }
                }

                return locs;
            }

            function findLabel(el) {
                const labelledby = el.getAttribute('aria-labelledby');
                if (labelledby) {
                    const lbl = document.getElementById(labelledby);
                    if (lbl) return lbl.textContent.trim();
                }
                let parent = el.parentElement;
                for (let i = 0; i < 5 && parent; i++) {
                    const lbl = parent.querySelector('label');
                    if (lbl) return lbl.textContent.trim();
                    parent = parent.parentElement;
                }
                const group = el.closest('.form-group, .field, .input-group, .mb-3, [class*="field"]');
                if (group) {
                    const lbl = group.querySelector('label');
                    if (lbl) return lbl.textContent.trim();
                }
                return '';
            }

            document.querySelectorAll('button, a[role="button"], input[type="submit"], input[type="button"]').forEach(el => {
                const text = (el.textContent || el.value || '').trim().substring(0, 60);
                if (!text && !(el.getAttribute('aria-label'))) return;
                const rect = el.getBoundingClientRect();
                elements.push({
                    id: nextId++, tag: el.tagName.toLowerCase(),
                    type: el.type || '',
                    role: el.getAttribute('role') || (el.tagName === 'BUTTON' ? 'button' : ''),
                    name: el.name || '', text: text,
                    aria_label: el.getAttribute('aria-label') || '',
                    data_testid: el.getAttribute('data-testid') || el.getAttribute('data-test-id') || '',
                    locators: computeLocators(el),
                    is_visible: rect.width > 0 && rect.height > 0,
                    category: 'action',
                });
            });

            document.querySelectorAll('input:not([type="hidden"]):not([type="submit"]):not([type="button"]), select, textarea').forEach(el => {
                const label = findLabel(el);
                const options = el.tagName === 'SELECT' ? [...el.options].map(o => o.textContent.trim()).filter(Boolean) : [];
                elements.push({
                    id: nextId++, tag: el.tagName.toLowerCase(),
                    type: el.type || '', role: el.getAttribute('role') || '',
                    name: el.name || '', label: label, text: '',
                    placeholder: el.placeholder || '',
                    aria_label: el.getAttribute('aria-label') || '',
                    data_testid: el.getAttribute('data-testid') || el.getAttribute('data-test-id') || '',
                    locators: computeLocators(el), is_visible: true,
                    category: 'input', options: options,
                    required: el.required || false,
                });
            });

            document.querySelectorAll('a[href]:not([role="button"])').forEach(el => {
                const text = (el.textContent || '').trim().substring(0, 60);
                if (!text) return;
                elements.push({
                    id: nextId++, tag: 'a', type: '', role: 'link',
                    name: '', text: text, placeholder: '',
                    aria_label: el.getAttribute('aria-label') || '',
                    data_testid: el.getAttribute('data-testid') || el.getAttribute('data-test-id') || '',
                    locators: computeLocators(el), is_visible: true,
                    category: 'nav',
                    href: el.getAttribute('href') || '',
                });
            });

            const headings = [];
            document.querySelectorAll('h1, h2, h3').forEach(h => {
                const text = (h.textContent || '').trim();
                if (text) headings.push({ level: h.tagName.toLowerCase(), text: text });
            });

            return { elements: elements, headings: headings, total_elements: elements.length };
        }""", strategies_json)

        result["url"] = page.url
        result["title"] = await page.title()
        result["storage_state"] = await context.storage_state()

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