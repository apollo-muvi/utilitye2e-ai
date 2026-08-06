"""Browser wait helpers for SPA-style UI updates."""

import json
import time
from typing import Any, Dict, List

PENDING_SELECTOR = (
    "[aria-busy='true'], "
    "[disabled][type='submit'], "
    ".loading, "
    ".spinner, "
    ".button-spinner, "
    "[class*='loading'], "
    "[class*='spinner']"
)


def summarize_settle_state(states: List[Dict[str, Any]]) -> Dict[str, int]:
    """Aggregate per-frame settle state into a small deterministic summary."""
    summary = {"elements": 0, "text_length": 0, "pending": 0}
    for state in states:
        summary["elements"] += int(state.get("elements", 0) or 0)
        summary["text_length"] += int(state.get("text_length", 0) or 0)
        summary["pending"] += int(state.get("pending", 0) or 0)
    return summary


async def collect_settle_state(page) -> List[Dict[str, Any]]:
    """Collect lightweight visible DOM state across page frames."""
    states = []
    for frame in page.frames:
        if not frame.url or frame.url == "about:blank":
            continue
        try:
            raw = await frame.evaluate(
                """(pendingSelector) => {
                    const visible = (el) => {
                        const rect = el.getBoundingClientRect();
                        const style = getComputedStyle(el);
                        return rect.width > 0
                            && rect.height > 0
                            && style.display !== 'none'
                            && style.visibility !== 'hidden';
                    };
                    const elements = [...document.querySelectorAll('*')].filter(visible).length;
                    const textLength = (document.body?.innerText || '').trim().length;
                    const pending = [...document.querySelectorAll(pendingSelector)]
                        .filter(visible).length;
                    return JSON.stringify({ elements, text_length: textLength, pending });
                }""",
                PENDING_SELECTOR,
            )
            states.append(json.loads(raw))
        except Exception:
            continue
    return states


async def wait_for_ui_settle(
    page,
    *,
    timeout_ms: int = 3000,
    poll_ms: int = 250,
    stable_polls: int = 2,
) -> Dict[str, int]:
    """Wait until a SPA has no visible pending indicators and DOM state is stable.

    This helper is intentionally best-effort. If networkidle is unavailable or
    the UI never fully stabilizes before the timeout, callers still get the
    latest observed state and can continue with existing fallback behavior.
    """
    try:
        await page.wait_for_load_state("networkidle", timeout=min(timeout_ms, 1500))
    except Exception:
        pass

    deadline = time.monotonic() + (timeout_ms / 1000)
    last_summary = None
    stable_count = 0

    while True:
        summary = summarize_settle_state(await collect_settle_state(page))
        if summary["pending"] == 0 and summary == last_summary:
            stable_count += 1
            if stable_count >= stable_polls:
                return summary
        else:
            stable_count = 0
        last_summary = summary

        if time.monotonic() >= deadline:
            return summary
        await page.wait_for_timeout(poll_ms)
