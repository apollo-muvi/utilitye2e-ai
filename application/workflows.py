"""Use-case workflows shared by HTTP routes and CLI commands."""

import asyncio
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import urlparse

from adapters.llm import create_llm_adapter
from adapters.schema import create_schema_adapter
from ai.analyzer import Analyzer
from core.recorder import TestResult
from core.spec import TestSpec

Crawler = Callable[..., Dict[str, Any]]


@dataclass
class DiscoveryResult:
    elements: List[Dict[str, Any]]
    title: str
    dom: Dict[str, Any]


@dataclass
class RunResult:
    summary: Dict[str, Any]
    results: List[TestResult]


def derive_login_url(target_url: str, login_url: str = "") -> str:
    """Use explicit login_url, or derive it from a /t/{tenant}/ target path."""
    if login_url:
        return login_url

    parsed = urlparse(target_url)
    parts = parsed.path.split("/")
    if "t" in parts:
        idx = parts.index("t")
        if idx + 1 < len(parts):
            return f"{parsed.scheme}://{parsed.netloc}/t/{parts[idx + 1]}/login"
    return ""


def build_selectable_elements(dom: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Build the UI-selectable element list from crawler DOM output."""
    elements = []
    skip_labels = {"☰", "登出", "Logout", "Sign out", "取消", "儲存", "Cancel", "Save"}
    seen_labels = set()

    for btn in dom.get("buttons", []):
        text = btn.get("text", "").strip()
        if not text or len(text) >= 40 or text in skip_labels:
            continue
        if text in seen_labels:
            continue
        seen_labels.add(text)
        element = {"type": "button", "label": text, "text": text}
        if btn.get("rowIndex", 0) > 0:
            element["row"] = btn["rowIndex"]
            element["rowLabel"] = btn.get("rowLabel", "")
        elements.append(element)

    for inp in dom.get("inputs", []):
        label = inp.get("label") or inp.get("placeholder") or inp.get("name") or ""
        if label and label not in seen_labels:
            seen_labels.add(label)
            elements.append(
                {
                    "type": "input",
                    "label": label,
                    "text": f"{inp.get('tag', 'input')}: {label}",
                }
            )

    for header in dom.get("tableHeaders", []):
        if header and header not in seen_labels:
            seen_labels.add(header)
            elements.append(
                {"type": "column", "label": header, "text": f"column: {header}"}
            )

    return elements


def discover_page(
    target_url: str,
    login_url: str = "",
    username: str = "",
    password: str = "",
    crawler: Optional[Crawler] = None,
) -> DiscoveryResult:
    """Crawl a target page and return selectable elements for analysis."""
    if crawler is None:
        from ai.page_crawler import crawl_page

        crawler = crawl_page

    resolved_login_url = derive_login_url(target_url, login_url)
    dom = crawler(
        url=target_url,
        login_url=resolved_login_url,
        username=username,
        password=password,
    )
    return DiscoveryResult(
        elements=build_selectable_elements(dom),
        title=dom.get("title", ""),
        dom=dom,
    )


def build_analyzer(config: Dict[str, Any]) -> Analyzer:
    """Create the analyzer and its configured adapters."""
    schema = create_schema_adapter(config["schema"])
    llm = create_llm_adapter(config["llm"])
    return Analyzer(llm, schema)


def analyze_test_spec(
    config: Dict[str, Any],
    description: str,
    target_url: str = "",
    login_url: str = "",
    username: str = "",
    password: str = "",
    selected_elements: Optional[List[Dict[str, Any]]] = None,
    analyzer: Optional[Analyzer] = None,
) -> TestSpec:
    """Generate a TestSpec from user intent and page context."""
    analyzer = analyzer or build_analyzer(config)
    return analyzer.generate(
        description=description,
        target_url=target_url,
        login_url=derive_login_url(target_url, login_url),
        username=username,
        password=password,
        selected_elements=selected_elements or [],
    )


async def run_test_spec_async(spec: TestSpec, headed: bool = False) -> RunResult:
    """Execute a TestSpec and return both summary and detailed recorder results."""
    from core.runner import Runner

    runner = Runner(spec, headless=not headed)
    summary = await runner.run()
    return RunResult(summary=summary, results=runner.recorder.results)


def run_test_spec(spec: TestSpec, headed: bool = False) -> RunResult:
    """Synchronous wrapper for CLI and Flask routes."""
    return asyncio.run(run_test_spec_async(spec, headed=headed))
