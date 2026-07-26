"""
AI Analyzer — converts natural language + page DOM into a TestSpec.

Flow: NL description + DOM crawl → LLM → JSON → TestSpec
"""

import json
import re
from typing import Optional

from adapters.llm.base import LLMAdapter
from core.spec import TestSpec
from .prompts import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE


class Analyzer:
    """Generate TestSpec from natural language + DOM via LLM."""

    def __init__(self, llm: LLMAdapter, schema=None):
        self.llm = llm
        self.schema = schema  # kept for backward compat, unused in v2

    def generate(
        self,
        description: str,
        target_url: str = "",
        login_url: str = "",
        username: str = "",
        password: str = "",
        selected_elements: list = None,
    ) -> TestSpec:
        # Crawl the page to get real DOM structure
        dom_json = "[]"
        if target_url:
            try:
                print(f"  → Crawling DOM: {target_url}")
                from .page_crawler import crawl_page
                dom_info = crawl_page(
                    url=target_url,
                    login_url=login_url,
                    username=username,
                    password=password,
                )
                dom_json = json.dumps(dom_info, ensure_ascii=False, indent=2)
                btn_count = len(dom_info.get("buttons", []))
                print(f"  → DOM crawl complete: {btn_count} buttons found")
            except Exception as e:
                dom_json = json.dumps({"error": f"Crawl failed: {e}"}, ensure_ascii=False)
                print(f"  → DOM crawl failed: {e}")

        # Build prompt
        selected_str = "（使用者未選取特定元件，請分析全部 DOM）"
        if selected_elements:
            selected_str = json.dumps(selected_elements, ensure_ascii=False, indent=2)

        user_prompt = USER_PROMPT_TEMPLATE.format(
            description=description,
            target_url=target_url,
            dom_json=dom_json,
            login_url=login_url,
            selected_elements=selected_str,
        )

        # Call LLM
        print("  → Calling LLM for step generation...")
        raw_response = self.llm.chat(SYSTEM_PROMPT, user_prompt, temperature=0.2)

        # Parse JSON
        spec_dict = self._extract_json(raw_response)

        # Inject credentials
        target = spec_dict.get("target", {})
        if username:
            target["username"] = username
        if password:
            target["password"] = password
        if not target.get("url") and target_url:
            target["url"] = target_url

        # Build and validate
        spec = TestSpec.from_dict(spec_dict)
        errors = spec.validate()
        if errors:
            raise ValueError(f"Invalid spec generated: {errors}")

        print(f"  → Spec: {spec.name} with {len(spec.steps)} steps")
        return spec

    @staticmethod
    def _extract_json(text: str) -> dict:
        """Extract JSON from LLM response, handling markdown fences."""
        text = re.sub(r'^```(?:json)?\s*', '', text.strip())
        text = re.sub(r'\s*```$', '', text)
        match = re.search(r'\{[\s\S]*\}', text)
        if not match:
            raise ValueError(f"No JSON found in LLM response:\n{text[:500]}")
        return json.loads(match.group())
