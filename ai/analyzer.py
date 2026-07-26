"""
AI Analyzer v2 — uses the Page Inspector's element map instead of guessing CSS selectors.

Flow:
  1. Crawl page → get rich element map
  2. Pass element map to LLM
  3. LLM picks elements from the map and produces an action plan
  4. Action plan references elements by their ID → executor uses their locators
"""

import json
from typing import Any, Dict, Optional

from .page_inspector import crawl_page
from .prompts import SYSTEM_PROMPT_V2, USER_PROMPT_TEMPLATE_V2


class PageAnalyzer:
    """Analyze a page's DOM via Playwright and AI."""

    def __init__(self):
        self.last_inspection: Dict[str, Any] = {}

    def inspect(
        self,
        url: str,
        login_url: str = "",
        username: str = "",
        password: str = "",
        wait_for_selector: str = "",
    ) -> Dict[str, Any]:
        """Inspect the page and return the element map."""
        result = crawl_page(url, login_url, username, password, wait_for_selector)
        self.last_inspection = result
        return result

    def summarize(self, inspection: Optional[Dict[str, Any]] = None) -> str:
        """Create a concise page summary for LLM consumption."""
        data = inspection or self.last_inspection
        if not data:
            return "No page data."

        lines = []
        lines.append(f"# Page: {data.get('title', '')}")
        lines.append(f"URL: {data.get('url', '')}")
        lines.append("")

        # Add page structure
        for h in data.get("headings", []):
            indent = "  " if h["level"] == "h2" else ""
            indent = "    " if h["level"] == "h3" else indent
            lines.append(f"{indent}## {h['text']}")

        lines.append("")
        lines.append("## Interactive Elements")
        lines.append("")

        for el in data.get("elements", []):
            parts = [f"[{el['id']}]"]
            parts.append(f"<{el['tag']}>")

            if el.get("role"):
                parts.append(f"role={el['role']}")
            if el.get("type"):
                parts.append(f"type={el['type']}")
            if el.get("name"):
                parts.append(f"name={el['name']}")
            if el.get("label"):
                parts.append(f"label=\"{el['label']}\"")
            if el.get("text"):
                parts.append(f"text=\"{el['text']}\"")
            if el.get("placeholder"):
                parts.append(f"placeholder=\"{el['placeholder']}\"")
            if el.get("data_testid"):
                parts.append(f"data-testid={el['data_testid']}")
            if el.get("options"):
                parts.append(f"options={el['options'][:5]}{'...' if len(el['options']) > 5 else ''}")
            if el.get("required"):
                parts.append("required")
            if not el["is_visible"]:
                parts.append("HIDDEN")

            lines.append("  " + " ".join(parts))

        lines.append("")
        lines.append(f"Total: {data.get('total_elements', 0)} elements")

        return "\n".join(lines)

    def generate_plan(
        self,
        llm_chat_fn,
        goal: str,
        page_summary: str,
    ) -> Dict[str, Any]:
        """Ask AI to produce an action plan using element IDs from the map."""
        prompt = USER_PROMPT_TEMPLATE_V2.format(goal=goal, page_summary=page_summary)
        raw = llm_chat_fn(SYSTEM_PROMPT_V2, prompt, temperature=0.2)

        # Extract JSON from response
        import re
        text = re.sub(r"^```(?:json)?\s*", "", raw.strip())
        text = re.sub(r"\s*```$", "", text)
        match = re.search(r"\{[\s\S]*\}", text)
        if not match:
            raise ValueError(f"No JSON found in LLM response:\n{raw[:500]}")

        return json.loads(match.group())