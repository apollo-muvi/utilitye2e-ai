"""
AI Fallback Locator — when all config strategies fail, ask LLM to produce one.
"""

import json
from typing import Dict, Optional

from .prompts import LOCATOR_FALLBACK_PROMPT
from adapters.llm.base import LLMAdapter


async def ai_resolve_locator(el_attrs: Dict, llm: LLMAdapter) -> Optional[str]:
    """Ask the LLM to produce a single locator string from raw element attrs.

    el_attrs: raw attributes extracted from DOM (no classification).
    Returns: a locator string like 'get_by_role:button:name=送出' or None.
    """
    el_json = json.dumps(el_attrs, ensure_ascii=False, indent=2)

    try:
        raw = llm.chat(
            system_prompt=LOCATOR_FALLBACK_PROMPT,
            user_prompt=f"Element attributes:\n{el_json}",
            temperature=0.1,
        )
    except Exception as e:
        print(f"  ⚠ AI locator fallback error: {e}")
        return None

    loc_str = raw.strip()
    # Strip markdown fences if present
    if loc_str.startswith("```"):
        loc_str = loc_str.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

    # Basic validation — must start with a known prefix or be CSS
    valid_prefixes = (
        "get_by_test_id:", "get_by_role:", "get_by_label:",
        "get_by_placeholder:", "get_by_text:", "get_by_title:", "css:",
    )
    if not loc_str.startswith(valid_prefixes):
        # Treat as raw CSS
        loc_str = f"css:{loc_str}"

    return loc_str
