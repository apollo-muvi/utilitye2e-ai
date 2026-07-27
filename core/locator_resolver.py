"""
Locator Resolver — config-driven locator builder + AI fallback.

This replaces the old hardcoded _build_locator() in executor.py.
Strategy definitions live in config/locator_strategies.yaml.
"""

import os
import yaml
from typing import Any, Dict, List, Optional


class LocatorStrategy:
    """One selector strategy parsed from YAML."""

    def __init__(self, d: Dict):
        self.name: str = d.get("name", "")
        self.priority: int = d.get("priority", 99)
        self.attrs: List[str] = d.get("attrs", [])
        self.prefix: str = d.get("prefix", "css")
        self.value_from: str = d.get("value_from", "attr_value")
        self.value_template: Optional[str] = d.get("value_template")
        self.role_from: Optional[str] = d.get("role_from")
        self.condition: Optional[str] = d.get("condition")

    def to_js_dict(self) -> Dict:
        """Serialize for injection into browser-side JS."""
        return {
            "name": self.name,
            "attrs": self.attrs,
            "prefix": self.prefix,
            "value_from": self.value_from,
            "value_template": self.value_template,
            "role_from": self.role_from,
            "condition": self.condition,
            "priority": self.priority,
        }


class AIFallbackConfig:
    def __init__(self, d: Dict):
        self.enabled: bool = d.get("enabled", False)
        self.extract_attrs: List[str] = d.get("extract_attrs", [])
        self.expected_format: str = d.get("expected_format", "")


class LocatorResolver:
    """Build Playwright locators from strategy strings. No hardcoded prefix dispatch."""

    # Maps config prefix → a function(page, value, extra) -> Playwright Locator
    # Registered at class level; extensible without touching executor code.
    _dispatch = {}

    def __init__(self, strategies: List[LocatorStrategy], ai_fallback: AIFallbackConfig):
        self._strategies = sorted(strategies, key=lambda s: s.priority)
        self._ai_fallback = ai_fallback

    @classmethod
    def from_yaml(cls, path: str = "") -> "LocatorResolver":
        if not path:
            path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "config", "locator_strategies.yaml",
            )
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        strategies = [LocatorStrategy(s) for s in data.get("strategies", [])]
        ai_fb = AIFallbackConfig(data.get("ai_fallback", {}))
        return cls(strategies, ai_fb)

    def get_strategies_js(self) -> str:
        """JSON-serialized strategies for browser-side JS injection."""
        import json
        return json.dumps([s.to_js_dict() for s in self._strategies])

    def get_ai_fallback_config(self) -> AIFallbackConfig:
        return self._ai_fallback

    # ── Phase 1: config-driven ──────────────────────────────────

    def build_locator(self, loc_str: str, page) -> Any:
        """Convert a locator string → Playwright Locator, dispatch-driven.

        No if/elif chain. The prefix maps to a handler via _dispatch table.
        """
        prefix, sep, value = loc_str.partition(":")
        if not sep:
            # Bare CSS selector — last-resort
            return page.locator(loc_str)

        handler = self._dispatch.get(prefix)
        if handler is None:
            return page.locator(loc_str)  # unknown prefix → try as CSS
        return handler(page, value)

    # ── Phase 2: AI fallback ────────────────────────────────────

    async def resolve_via_ai(self, el_attrs: Dict, page, llm=None) -> Optional[Any]:
        """If all config locators failed, ask AI to produce one.

        Returns a Playwright Locator or None.
        """
        if not self._ai_fallback.enabled or llm is None:
            return None
        from ai.locator_ai import ai_resolve_locator
        loc_str = await ai_resolve_locator(el_attrs, llm)
        if not loc_str:
            return None
        try:
            loc = self.build_locator(loc_str, page)
            if await loc.count() > 0:
                return loc
        except Exception:
            pass
        return None


# ============================================================
# Dispatch table — each prefix → handler function.
# Add a new prefix = register one function. No class changes.
# ============================================================

def _register(prefix: str):
    def decorator(fn):
        LocatorResolver._dispatch[prefix] = fn
        return fn
    return decorator


@_register("get_by_test_id")
def _test_id(page, value: str):
    return page.get_by_test_id(value)


@_register("get_by_role")
def _role(page, value: str):
    # value format: "button:name=送出" or just "button"
    parts = value.split(":", 1)
    role = parts[0]
    opts = {}
    if len(parts) > 1 and "name=" in parts[1]:
        opts["name"] = parts[1].replace("name=", "", 1)
    return page.get_by_role(role, **opts)


@_register("get_by_label")
def _label(page, value: str):
    return page.get_by_label(value)


@_register("get_by_placeholder")
def _placeholder(page, value: str):
    return page.get_by_placeholder(value)


@_register("get_by_text")
def _text(page, value: str):
    return page.get_by_text(value, exact=False)


@_register("get_by_title")
def _title(page, value: str):
    return page.get_by_title(value)


@_register("css_id")
def _css_id(page, value: str):
    return page.locator(f"#{value}")


@_register("css_attr")
def _css_attr(page, value: str):
    # value is already a full attribute selector like [data-cy="submit"]
    return page.locator(value)


@_register("css")
def _css(page, value: str):
    return page.locator(value)
