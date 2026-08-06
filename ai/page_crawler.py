"""
Page crawler — extracts DOM structure for AI analysis.

Generic version: works with any web page (SPA, traditional, emulator, router admin, etc.)
Supports iframe/frame traversal, generic login detection, and deep scanning.

Features:
  - Auto-detects login forms (password field + submit button) across all frames
  - Traverses iframes recursively
  - Extracts buttons, inputs, selects, tables, links, nav items
  - Deep scan: clicks non-destructive buttons to reveal hidden forms/menus
  - Frame-aware: captures content from nested iframes
"""

import asyncio
import json
import os
from typing import Dict, Any, List, Optional
from urllib.parse import urlparse


# ─── DOM extraction JavaScript (injected into each frame) ───

EXTRACT_JS = """() => {
    const result = { buttons: [], inputs: [], selects: [], tables: [], tableHeaders: [], links: [], navItems: [], text: [] };
    const seenBtns = {};

    // Buttons inside table rows (with row context)
    document.querySelectorAll('tr').forEach((tr, rowIdx) => {
        const cells = tr.querySelectorAll('th, td');
        if (!cells.length) return;
        const rowLabel = (cells[0].textContent || '').trim().slice(0, 40);
        tr.querySelectorAll('button, [role=button], input[type=button], input[type=submit], a[class*=btn], a[class*=Btn]').forEach(btn => {
            const text = (btn.textContent || btn.value || '').trim();
            if (text && text.length < 60) {
                const key = text;
                seenBtns[key] = (seenBtns[key] || 0) + 1;
                result.buttons.push({ text, context: 'table-row', rowLabel, rowIndex: rowIdx });
            }
        });
    });

    // Standalone buttons (not in table)
    document.querySelectorAll('button, [role=button], input[type=button], input[type=submit]').forEach(btn => {
        if (btn.closest('tr')) return;
        const text = (btn.textContent || btn.value || '').trim();
        if (text && text.length < 60) {
            const s = getComputedStyle(btn);
            if (s.display === 'none' || s.visibility === 'hidden') return;
            result.buttons.push({ text, context: 'standalone', id: btn.id || '', className: (btn.className || '').slice(0, 50) });
        }
    });

    // Inputs
    document.querySelectorAll('input, textarea').forEach(inp => {
        const s = getComputedStyle(inp);
        if (s.display === 'none' || s.visibility === 'hidden') return;
        // Find label
        let label = '';
        if (inp.id) {
            const lbl = document.querySelector('label[for="' + inp.id + '"]');
            if (lbl) label = lbl.textContent.trim();
        }
        if (!label) {
            const parent = inp.closest('.form-group, .form-field, .field, label, td, .input-wrap, .widget');
            if (parent) {
                const lbl = parent.querySelector('label, .label, .text-label, [class*=label]');
                if (lbl) label = lbl.textContent.trim();
            }
        }
        if (!label) {
            // Check preceding sibling text
            let prev = inp.previousElementSibling;
            while (prev) {
                const t = (prev.textContent || '').trim();
                if (t && t.length < 40) { label = t; break; }
                prev = prev.previousElementSibling;
            }
        }
        result.inputs.push({
            tag: inp.tagName.toLowerCase(), type: inp.type || '', name: inp.name || '',
            id: inp.id || '', placeholder: inp.placeholder || '', label: label.slice(0, 50),
            className: (inp.className || '').slice(0, 60),
        });
    });

    // Selects
    document.querySelectorAll('select').forEach(sel => {
        const s = getComputedStyle(sel);
        if (s.display === 'none' || s.visibility === 'hidden') return;
        const options = [...sel.options].map(o => o.textContent.trim()).slice(0, 15);
        result.selects.push({ id: sel.id || '', name: sel.name || '', options, className: (sel.className || '').slice(0, 50) });
    });

    // Table headers
    document.querySelectorAll('table thead th').forEach(th => {
        const t = (th.textContent || '').trim();
        if (t) result.tableHeaders.push(t);
    });
    // Table count
    result.tables = document.querySelectorAll('table').length;

    // Links (visible only)
    document.querySelectorAll('a[href]').forEach(a => {
        const s = getComputedStyle(a);
        if (s.display === 'none' || s.visibility === 'hidden') return;
        const text = (a.textContent || '').trim();
        if (text && text.length < 60) {
            result.links.push({ text, href: (a.getAttribute('href') || '').slice(0, 100) });
        }
    });

    // Nav items (common patterns: li in nav, [role=menuitem], sidebar items, dashboard links)
    document.querySelectorAll('nav li, [role=menuitem], .nav-item, .menu-item, .side-item, [class*=nav] li, [class*=menu] li, [class*=sidebar] a, [class*=sidebar] li').forEach(item => {
        const s = getComputedStyle(item);
        if (s.display === 'none' || s.visibility === 'hidden') return;
        const text = (item.textContent || '').trim().slice(0, 50);
        if (text && text.length > 1 && text.length < 50) {
            result.navItems.push({ text, className: (item.className || '').slice(0, 40) });
        }
    });

    // Page title
    const h1 = document.querySelector('h1, h2, h3, [class*=title], [class*=Title]');
    result.title = h1 ? (h1.textContent || '').trim().slice(0, 80) : document.title || '';

    // Visible text snippets (limited)
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    const texts = [];
    let node;
    while (node = walker.nextNode()) {
        const t = (node.textContent || '').trim();
        if (t && t.length > 1 && t.length < 80) {
            const ps = node.parentElement ? getComputedStyle(node.parentElement) : null;
            if (ps && ps.display !== 'none' && ps.visibility !== 'hidden') {
                texts.push(t);
                if (texts.length >= 50) break;
            }
        }
    }
    result.text = texts;

    return result;
}"""


# ─── Frame traversal helpers ───

# ─── Overlay/mask dismissal ───

async def _dismiss_overlays(page) -> None:
    """
    Remove overlay elements that block interaction (loading masks, cookie banners).
    Also detect and handle credential-setup modals that block navigation.
    """
    # 1. Remove loading masks
    overlays_removed = await page.evaluate('''() => {
        let removed = [];
        ['#mask', '.mask', '#loading', '.loading-overlay', '.modal-backdrop'].forEach(sel => {
            document.querySelectorAll(sel).forEach(el => {
                const s = getComputedStyle(el);
                if (s.display !== 'none') {
                    el.style.display = 'none';
                    removed.push(sel);
                }
            });
        });
        // High z-index full-screen overlays (only semi-transparent = loading screens)
        document.querySelectorAll('div, section').forEach(el => {
            if (el.id === 'mask' || el.classList.contains('mask')) return;
            const s = getComputedStyle(el);
            if (s.zIndex && parseInt(s.zIndex) > 900 && s.position === 'fixed' &&
                (s.display === 'block' || s.display === 'flex') &&
                el.offsetWidth > window.innerWidth * 0.8 &&
                el.offsetHeight > window.innerHeight * 0.8) {
                if (parseFloat(s.opacity) < 0.5) {
                    el.style.display = 'none';
                    removed.push('overlay:' + (el.id || el.className.substring(0,20)));
                }
            }
        });
        return removed;
    }''')
    if overlays_removed:
        print(f"  → Removed overlays: {overlays_removed}")

    # 2. Try cookie consent banners
    for selector in [
        '[class*="cookie"] button[class*="accept"]',
        '[class*="cookie"] button[class*="Accept"]',
        'button:has-text("Accept All")', 'button:has-text("Accept all")',
        'button:has-text("接受所有")', 'button:has-text("I Agree")',
    ]:
        try:
            btn = page.locator(selector).first
            if await btn.is_visible(timeout=800):
                await btn.click()
                print(f"  → Dismissed cookie banner")
                await page.wait_for_timeout(500)
                break
        except Exception:
            pass


async def _handle_credential_modal(page, username: str = "admin", password: str = "admin") -> bool:
    """
    Detect and fill credential-setup modals (common on first-load admin interfaces).
    Uses native Playwright actions to trigger framework event handlers properly.
    Returns True if a modal was found and submitted.
    """
    for frame in page.frames:
        if not frame.url or frame.url == 'about:blank':
            continue
        try:
            # Check if any visible password field exists
            pswd_count = await frame.locator('input[type="password"]').count()
            if pswd_count == 0:
                continue

            # Check visibility properly (walk parent chain)
            visible_pswd_indices = []
            for i in range(pswd_count):
                visible = await frame.evaluate(f'''(n) => {{
                    const inputs = document.querySelectorAll('input[type="password"]');
                    const el = inputs[n];
                    if (!el) return false;
                    let p = el;
                    for (let i = 0; i < 10 && p; i++) {{
                        if (getComputedStyle(p).display === 'none' || getComputedStyle(p).visibility === 'hidden') return false;
                        p = p.parentElement;
                    }}
                    return true;
                }}''', i)
                if visible:
                    visible_pswd_indices.append(i)

            if not visible_pswd_indices:
                continue

            print(f"  → Credential modal: {len(visible_pswd_indices)} visible password field(s)")

            # Fill visible text fields (username) using native fill
            text_count = await frame.locator('input[type="text"]').count()
            for i in range(text_count):
                visible = await frame.evaluate(f'''(n) => {{
                    const inputs = document.querySelectorAll('input[type="text"]');
                    const el = inputs[n];
                    if (!el) return false;
                    let p = el;
                    for (let i = 0; i < 10 && p; i++) {{
                        if (getComputedStyle(p).display === 'none') return false;
                        p = p.parentElement;
                    }}
                    return true;
                }}''', i)
                if visible:
                    try:
                        await frame.locator('input[type="text"]').nth(i).fill(username)
                    except Exception:
                        pass

            # Fill visible password fields using native fill
            for idx in visible_pswd_indices:
                try:
                    await frame.locator('input[type="password"]').nth(idx).fill(password)
                except Exception:
                    pass

            # Click submit/confirm button — click the inner span/button-text if present
            # (widget frameworks often bind events on the span, not the button)
            submitted = False
            for selector in [
                '#btn-reset-user span.button-text',
                '#btn-reset-user',
                'button:has-text("Confirm") span.button-text',
                'button:has-text("Confirm")',
                'button:has-text("OK")', 'button:has-text("Save")',
                'button:has-text("Submit")', 'button:has-text("Apply")',
                'button[type="submit"]',
            ]:
                try:
                    btn = frame.locator(selector).first
                    if await btn.count() > 0:
                        await btn.click(force=True)
                        await page.wait_for_timeout(2000)
                        print(f"  → Credential modal submitted via: {selector}")
                        submitted = True
                        break
                except Exception:
                    pass
            return submitted
        except Exception:
            continue
    return False


async def _extract_from_frame(frame) -> Dict[str, Any]:
    """Extract DOM info from a single frame."""
    try:
        return await frame.evaluate(EXTRACT_JS)
    except Exception as e:
        return {"error": str(e), "buttons": [], "inputs": [], "selects": [], "links": []}


async def _extract_all_frames(page) -> List[Dict[str, Any]]:
    """Extract DOM info from page + all nested iframes."""
    results = []
    for frame in page.frames:
        url = frame.url
        if not url or url == 'about:blank':
            continue
        info = await _extract_from_frame(frame)
        info["frameUrl"] = url
        info["frameName"] = frame.name or ""
        results.append(info)
    return results


# ─── Generic login ───

async def _try_login(page, login_url: str, username: str, password: str,
                     tenant_id: str = "") -> bool:
    """
    Generic multi-step login for SaaS and standard login pages.

    SaaS multi-tenant flow (e.g. TutorBot):
      Step 1: text field (tenant ID / org name) + submit → redirect to login page
      Step 2: username + password fields + submit → authenticated

    Standard login:
      Single page with username + password + submit.

    Strategy:
      1. Navigate to login_url, scan visible inputs.
      2. If password field exists → standard login.
      3. If only text field(s) + submit → fill tenant_id (or username), submit, wait for redirect.
      4. Re-scan → if password field now appears → complete standard login.
    """
    try:
        await page.goto(login_url, wait_until="networkidle")
        await page.wait_for_timeout(2000)
    except Exception:
        pass

    MAX_STEPS = 3  # safety: at most 3 pre-auth steps (tenant, captcha, etc.)

    for step_num in range(MAX_STEPS):
        # Find the best frame to work in
        target_frame = None
        for frame in page.frames:
            if not frame.url or frame.url == 'about:blank':
                continue
            try:
                if await frame.locator('input').count() > 0:
                    target_frame = frame
                    break
            except Exception:
                continue
        if not target_frame:
            print("  → No form elements found, cannot login")
            return False

        # Check what inputs are visible
        has_password = await target_frame.locator('input[type="password"]').count() > 0
        visible_text = await target_frame.evaluate('''() => {
            return [...document.querySelectorAll('input[type="text"], input:not([type])')]
                .filter(el => {
                    let p = el;
                    for (let i = 0; i < 10 && p; i++) {
                        if (getComputedStyle(p).display === 'none') return false;
                        p = p.parentElement;
                    }
                    return true;
                }).length;
        }''')

        if has_password:
            # ─── Standard login: fill username + password, submit ───
            print(f"  → Login step {step_num+1}: password field found, completing login")

            # Fill username (first visible text input)
            try:
                text_inputs = target_frame.locator('input[type="text"], input:not([type])')
                for i in range(await text_inputs.count()):
                    try:
                        el = text_inputs.nth(i)
                        visible = await target_frame.evaluate(f'''(n) => {{
                            const inputs = document.querySelectorAll('input[type="text"], input:not([type])');
                            let p = inputs[n];
                            for (let i = 0; i < 10 && p; i++) {{
                                if (getComputedStyle(p).display === 'none') return false;
                                p = p.parentElement;
                            }}
                            return true;
                        }}''', i)
                        if visible:
                            await el.fill(username)
                            break
                    except Exception:
                        pass
            except Exception:
                pass

            # Fill password
            try:
                await target_frame.locator('input[type="password"]').first.fill(password)
            except Exception as e:
                print(f"  → Cannot fill password: {e}")
                return False

            # Submit
            submitted = await _click_submit(target_frame, page)
            if submitted:
                await page.wait_for_timeout(3000)
                print(f"  → Login submitted (url: {page.url[:60]})")
                return True
            return False

        elif visible_text > 0:
            # ─── Pre-auth step: tenant selection, org picker, etc. ───
            fill_value = tenant_id or username
            print(f"  → Login step {step_num+1}: no password field, "
                  f"filling text input as tenant/identifier step")

            try:
                text_inputs = target_frame.locator('input[type="text"], input:not([type])')
                for i in range(await text_inputs.count()):
                    try:
                        el = text_inputs.nth(i)
                        visible = await target_frame.evaluate(f'''(n) => {{
                            const inputs = document.querySelectorAll('input[type="text"], input:not([type])');
                            let p = inputs[n];
                            for (let i = 0; i < 10 && p; i++) {{
                                if (getComputedStyle(p).display === 'none') return false;
                                p = p.parentElement;
                            }}
                            return true;
                        }}''', i)
                        if visible:
                            await el.fill(fill_value)
                            break
                    except Exception:
                        pass
            except Exception:
                pass

            # Submit this step
            submitted = await _click_submit(target_frame, page)
            if submitted:
                await page.wait_for_timeout(3000)
                print(f"  → Pre-auth step submitted (url: {page.url[:60]})")
                # Loop continues — will re-scan for password field on next page
                continue
            else:
                # No submit button found — maybe just press Enter
                try:
                    await target_frame.locator('input[type="text"]').first.press("Enter")
                    await page.wait_for_timeout(3000)
                    print(f"  → Pre-auth submitted via Enter (url: {page.url[:60]})")
                    continue
                except Exception:
                    print("  → Cannot proceed past pre-auth step")
                    return False

        else:
            # No visible inputs at all — maybe already logged in?
            print(f"  → No login form found (step {step_num+1}), may already be authenticated")
            return step_num > 0  # True if we completed at least one step

    print("  → Exceeded max login steps")
    return False


async def _login_for_crawl(
    page,
    url: str,
    login_url: str,
    username: str,
    password: str,
    tenant_id: str = "",
) -> bool:
    """Authenticate crawler pages through the canonical auth boundary."""
    if not username:
        return False

    from core.auth import login_page
    from core.spec import TargetSpec

    return await login_page(
        page,
        TargetSpec(
            url=url,
            login_url=login_url,
            username=username,
            password=password,
        ),
        tenant_id=tenant_id,
    )


def _already_at_crawl_entry_after_login(
    logged_in: bool, login_url: str, url: str
) -> bool:
    """Return true when login already left the page at the crawl entry point."""
    if not logged_in:
        return False
    if not login_url:
        return True
    return login_url.rstrip("/") == url.rstrip("/")


async def _click_submit(frame, page) -> bool:
    """Try multiple strategies to click a submit/login button."""
    for selector in [
        'button[type="submit"]',
        'input[type="submit"]',
        'button:has-text("Login")', 'button:has-text("Sign in")', 'button:has-text("Log in")',
        'button:has-text("登入")', 'button:has-text("登录")', 'button:has-text("登錄")',
        'button:has-text("進入")', 'button:has-text("进入")', 'button:has-text("Next")',
        'button:has-text("下一步")', 'button:has-text("繼續")', 'button:has-text("继续")',
        'button:has-text("OK")', 'button:has-text("ok")', 'button:has-text("確認")',
        'button:has-text("Confirm")', 'button:has-text("Submit")',
        '[class*=login] button', '[class*=Login] button', '[class*=submit] button',
        'a[class*=btn][class*=login]', 'a[class*=Btn][class*=Login]',
    ]:
        try:
            btn = frame.locator(selector).first
            if await btn.count() > 0:
                try:
                    if await btn.is_visible(timeout=800):
                        await btn.click()
                        return True
                except Exception:
                    # Try force click
                    await btn.click(force=True)
                    return True
        except Exception:
            continue
    return False


# ─── Generic deep scan ───

DESTRUCTIVE_WORDS = {"delete", "remove", "drop", "clear", "reset", "reboot", "logout", "sign out",
                     "刪除", "移除", "清除", "重置", "登出", "重啟"}
SKIP_WORDS = {"logout", "sign out", "reboot", "exit", "登出", "重啟"}


def _is_destructive(text: str) -> bool:
    lower = text.lower()
    return any(d in lower for d in DESTRUCTIVE_WORDS)


def _is_skip(text: str) -> bool:
    lower = text.lower()
    return any(s.lower() in lower for s in SKIP_WORDS)


DEEP_SCAN_MAX_BUTTONS = 10  # safety limit


async def _deep_scan(page, frames_data: List[Dict]) -> List[Dict]:
    """
    Click non-destructive buttons to reveal hidden forms/menus.
    Records new inputs/buttons without submitting.
    Deduplicates by button text to avoid clicking the same label N times.
    """
    extra_results = []
    seen_texts = set()

    # Collect unique candidate buttons from all frames
    candidates = []
    for frame_idx, frame_data in enumerate(frames_data):
        frame = page.frames[frame_idx] if frame_idx < len(page.frames) else page.main_frame
        for btn in frame_data.get("buttons", []):
            text = btn.get("text", "")
            if not text or text in seen_texts:
                continue
            if _is_skip(text) or _is_destructive(text):
                continue
            # Skip generic dialog buttons
            if text in ("OK", "Yes", "No", "Confirm", "Save", "Finish"):
                continue
            seen_texts.add(text)
            candidates.append((frame, text, frame_data))
            if len(candidates) >= DEEP_SCAN_MAX_BUTTONS:
                break
        if len(candidates) >= DEEP_SCAN_MAX_BUTTONS:
            break

    for frame, text, frame_data in candidates:
        try:
            locator = frame.locator(f'button:has-text("{text}")').first
            if not await locator.is_visible(timeout=1000):
                continue
            if not await locator.is_enabled(timeout=1000):
                continue

            print(f"  → Deep scan: [{text}]")
            await locator.click()
            await page.wait_for_timeout(2000)

            after = await _extract_from_frame(frame)
            new_inputs = [i for i in after.get("inputs", [])
                          if i not in frame_data.get("inputs", [])]
            new_btns = [b for b in after.get("buttons", [])
                        if b.get("text") not in {x["text"] for x in frame_data.get("buttons", [])}]

            if new_inputs or new_btns:
                print(f"    Revealed: {len(new_inputs)} inputs, {len(new_btns)} buttons")
                extra_results.append({
                    "trigger": text,
                    "frameUrl": frame_data.get("frameUrl", ""),
                    "newInputs": new_inputs,
                    "newButtons": new_btns,
                    "newSelects": [s for s in after.get("selects", [])
                                   if s not in frame_data.get("selects", [])],
                })

            # Close any dialog/modal
            for close_text in ["Cancel", "Close", "✕", "取消", "關閉", "No"]:
                try:
                    close_btn = frame.locator(f'button:has-text("{close_text}")').first
                    if await close_btn.is_visible(timeout=500):
                        await close_btn.click()
                        await page.wait_for_timeout(1000)
                        break
                except Exception:
                    pass

        except Exception:
            pass

    return extra_results


# ─── Main crawl function ───

async def _navigate_step(page, frame, label: str) -> bool:
    """
    Navigate one step: click an element whose text matches `label`.
    Tries: exact li match → span.button-text → role=menuitem → a → generic text.
    Uses force=True to bypass overlay interception.
    """
    selectors = [
        f'li:has-text("{label}")',
        f'span.button-text:has-text("{label}")',
        f'[role=menuitem]:has-text("{label}")',
        f'.nav-item:has-text("{label}")',
        f'a:has-text("{label}")',
    ]
    for sel in selectors:
        loc = frame.locator(sel).first
        if await loc.count() > 0:
            try:
                await loc.click(force=True)
                return True
            except Exception:
                pass
    return False


async def _crawl_page(url: str, login_url: str = "", username: str = "", password: str = "",
                      deep_scan: bool = False, max_nav_depth: int = 0,
                      nav_steps: list = None, tenant_id: str = "") -> Dict[str, Any]:
    """
    Crawl a page and extract full DOM structure.

    Two modes:
    1. TARGETED: nav_steps=["Advanced", "Network"] → navigate step-by-step to
       a specific page, analyze ONLY that page. No full-site exploration.
       Avoids EPIPE crashes from clicking too many elements.
    2. BROAD: max_nav_depth > 0 → explore up to N nav items from the index page.

    Args:
        url: Target page URL (usually the index/entry page).
        nav_steps: Ordered list of nav labels to click, e.g. ["Advanced", "Network"].
                   If provided, crawls ONLY the destination page.
        deep_scan: Click non-destructive buttons to find hidden forms (only when
                   nav_steps is not provided).
        max_nav_depth: Max nav items to explore from index (only when nav_steps
                       is not provided).
    """
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
        )
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            locale="en-US",
            ignore_https_errors=True,
        )
        page = await context.new_page()
        page.set_default_timeout(15000)

        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        """)

        # Phase 1: Login if needed
        logged_in = await _login_for_crawl(
            page,
            url=url,
            login_url=login_url,
            username=username,
            password=password,
            tenant_id=tenant_id,
        )

        # Phase 2: Navigate to entry URL
        # Skip if login already entered the target page or an inline-login app.
        if _already_at_crawl_entry_after_login(logged_in, login_url, url):
            print(f"→ Already on target page after login (url: {page.url[:60]})")
        else:
            print(f"→ Navigate: {url}")
            try:
                await page.goto(url, wait_until="networkidle")
            except Exception:
                try:
                    await page.goto(url, wait_until="domcontentloaded")
                except Exception as e:
                    print(f"  → Navigation warning: {e}")
        await page.wait_for_timeout(3000)

        # Phase 2b: Dismiss overlays + handle credential modals
        # Skip credential modal if we just attempted SaaS login and are still on a login page
        await _dismiss_overlays(page)
        on_login_page = '/login' in page.url.lower() or 'login' in page.url.lower()
        if logged_in and on_login_page:
            print("  → Skipping credential modal (SaaS login page detected)")
        else:
            await _handle_credential_modal(page, username or "admin", password or "admin")
            await _dismiss_overlays(page)

        # ─── TARGETED MODE: navigate to specific page ───
        if nav_steps:
            main_frame = page.main_frame
            for step_label in nav_steps:
                clicked = await _navigate_step(page, main_frame, step_label)
                if clicked:
                    print(f"  → Nav step: [{step_label}]")
                    await page.wait_for_timeout(3000)
                    await _dismiss_overlays(page)
                else:
                    print(f"  → Nav step FAILED: [{step_label}]")

            # Extract ONLY the destination page
            print(f"→ Extracting destination page: {nav_steps[-1]}")
            frames_data = await _extract_all_frames(page)

            await browser.close()
            return {
                "url": url,
                "navSteps": nav_steps,
                "title": frames_data[0].get("title", "") if frames_data else "",
                "frames": frames_data,
            }

        # ─── BROAD MODE: explore from index ───
        print("→ Extracting DOM structure...")
        frames_data = await _extract_all_frames(page)

        # Phase 4: Explore nav items
        nav_explored = []
        if max_nav_depth > 0:
            nav_candidates = []
            main_frame = page.main_frame
            for item in frames_data:
                # Standard nav items (li, menuitem, etc.)
                for nav in item.get("navItems", []):
                    text = nav.get("text", "")
                    if text and not _is_destructive(text) and not _is_skip(text):
                        if text not in nav_candidates:
                            nav_candidates.append(text)
                # SPA-style: buttons that act as navigation (e.g. 聯絡簿使用, 學員管理)
                for btn in item.get("buttons", []):
                    text = btn.get("text", "")
                    if text and not _is_destructive(text) and not _is_skip(text):
                        # Only include buttons that look like navigation (longer text, no form actions)
                        if len(text) > 1 and text not in nav_candidates:
                            nav_candidates.append(text)

            for nav_text in nav_candidates[:max_nav_depth]:
                try:
                    clicked = await _navigate_step(page, main_frame, nav_text)
                    if clicked:
                        print(f"  → Nav explore: [{nav_text}]")
                        await page.wait_for_timeout(3000)
                        await _dismiss_overlays(page)
                        await _handle_credential_modal(page, username or "admin", password or "admin")

                        after_frames = await _extract_all_frames(page)
                        after_data = after_frames[0] if after_frames else {}
                        nav_explored.append({
                            "navItem": nav_text,
                            "title": after_data.get("title", ""),
                            "inputs": after_data.get("inputs", []),
                            "buttons": [b["text"] for b in after_data.get("buttons", [])],
                            "selects": after_data.get("selects", []),
                            "tableHeaders": after_data.get("tableHeaders", []),
                        })
                except Exception:
                    pass

        # Phase 5: Deep scan
        deep_results = []
        if deep_scan:
            print("→ Deep scanning...")
            current_frames = await _extract_all_frames(page)
            deep_results = await _deep_scan(page, current_frames)

        await browser.close()

        return {
            "url": url,
            "title": frames_data[0].get("title", "") if frames_data else "",
            "frames": frames_data,
            "navExplored": nav_explored,
            "deepScan": deep_results,
        }


def _flatten_frames(result: Dict[str, Any]) -> Dict[str, Any]:
    """Merge all frame data into top-level keys so consumers don't need to
    know about frames vs. single-page.

    After this, result always has: buttons, inputs, selects, tableHeaders,
    links, navItems (merged + deduplicated from all frames).
    """
    merged = {k: [] for k in ("buttons", "inputs", "selects", "tableHeaders", "links", "navItems")}
    for frame in result.get("frames", []):
        frame_url = frame.get("frameUrl", "")
        frame_name = frame.get("frameName", "")
        for key in merged:
            for item in frame.get(key, []):
                if isinstance(item, dict):
                    enriched = dict(item)
                    enriched.setdefault("frameUrl", frame_url)
                    enriched.setdefault("frameName", frame_name)
                    merged[key].append(enriched)
                else:
                    merged[key].append(item)
    # Deduplicate tableHeaders and links by text/href
    seen_th = set()
    deduped_th = []
    for th in merged["tableHeaders"]:
        if th not in seen_th:
            seen_th.add(th)
            deduped_th.append(th)
    merged["tableHeaders"] = deduped_th

    seen_link = set()
    deduped_links = []
    for link in merged["links"]:
        key = (link.get("text", ""), link.get("href", ""))
        if key not in seen_link:
            seen_link.add(key)
            deduped_links.append(link)
    merged["links"] = deduped_links

    result.update(merged)
    return result


def crawl_page(url: str, login_url: str = "", username: str = "", password: str = "",
               deep_scan: bool = False, max_nav_depth: int = 0,
               nav_steps: list = None, tenant_id: str = "") -> Dict[str, Any]:
    """Sync wrapper for _crawl_page. Adds flattened top-level keys for all consumers."""
    result = asyncio.run(_crawl_page(url, login_url, username, password,
                                     deep_scan, max_nav_depth, nav_steps or [], tenant_id))
    return _flatten_frames(result)
