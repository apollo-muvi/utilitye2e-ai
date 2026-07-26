"""
UtilityE2E-AI v2 — CLI entry point.

Usage:
    # Inspect a page (show element map)
    utilitye2e-ai inspect --url https://example.com

    # Analyze a page with AI and generate an action plan
    utilitye2e-ai analyze --url https://example.com --goal "新增一個家長"

    # Execute a saved plan
    utilitye2e-ai run --url https://example.com --plan plan.json

    # Full pipeline: inspect → analyze (LLM) → execute
    utilitye2e-ai auto --url https://example.com --goal "新增一個家長"

    # Web UI
    utilitye2e-ai web
"""

import sys
import os
import json
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ai.page_inspector import crawl_page
from ai.analyzer import PageAnalyzer
from core.executor import Executor
from config import load_config


def cmd_inspect(args, config):
    """Inspect a page and show the element map."""
    print(f"Inspecting: {args.url}")
    result = crawl_page(
        url=args.url,
        login_url=args.login_url or config.get("target", {}).get("login_url", ""),
        username=args.username or config.get("target", {}).get("username", ""),
        password=args.password or config.get("target", {}).get("password", ""),
        wait_for_selector=args.wait_for or "",
    )

    print(f"\n{'='*60}")
    print(f"Page: {result.get('title', '')}")
    print(f"URL:  {result.get('url', '')}")
    print(f"Total elements: {result.get('total_elements', 0)}")
    print(f"{'='*60}\n")

    for el in result.get("elements", []):
        desc = []
        if el.get("text"):
            desc.append(f"text=\"{el['text']}\"")
        if el.get("label"):
            desc.append(f"label=\"{el['label']}\"")
        if el.get("name"):
            desc.append(f"name={el['name']}")
        if el.get("aria_label"):
            desc.append(f"aria=\"{el['aria_label']}\"")
        if el.get("placeholder"):
            desc.append(f"placeholder=\"{el['placeholder']}\"")

        icon = "🔘" if el["category"] == "action" else "📝" if el["category"] == "input" else "🔗"
        print(f"  {icon} [{el['id']:3d}] <{el.get('tag','?'):>8}> {' '.join(desc)}")

        locs = el.get("locators", [])
        if locs:
            print(f"          locators: {', '.join(locs[:3])}{'...' if len(locs) > 3 else ''}")

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"\nSaved to: {args.output}")


def cmd_analyze(args, config):
    """Use AI to analyze a page and generate an action plan."""
    from adapters.llm import create_llm_adapter

    llm = create_llm_adapter(config.get("llm", {}))

    print(f"Goal: {args.goal}")
    print(f"Inspecting: {args.url}")
    print(f"LLM: {llm.name}\n")

    analyzer = PageAnalyzer()
    inspection = analyzer.inspect(
        url=args.url,
        login_url=args.login_url or config.get("target", {}).get("login_url", ""),
        username=args.username or config.get("target", {}).get("username", ""),
        password=args.password or config.get("target", {}).get("password", ""),
        wait_for_selector=args.wait_for or "",
    )

    print(f"Found {len(inspection.get('elements', []))} interactive elements")
    print(f"Sending to LLM for analysis...\n", flush=True)

    summary = analyzer.summarize(inspection)
    plan = analyzer.generate_plan(llm.chat, args.goal, summary)

    print(f"{'='*60}")
    print(f"🎯 Goal: {plan.get('goal', '')}")
    print(f"{'='*60}\n")

    for i, step in enumerate(plan.get("steps", []), 1):
        action = step.get("action", "?")
        el_id = step.get("element_id", "-")
        value = step.get("value", "")
        desc = step.get("description", "")
        print(f"  {i}. [{action:>8}] [ID={el_id}] {desc}")
        if value:
            print(f"     value: '{value}'")

    if args.output:
        data = {
            "plan": plan,
            "page_url": args.url,
            "page_title": inspection.get("title", ""),
            "inspection_file": args.output,
        }
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"\nSaved to: {args.output}")


def cmd_run(args, config):
    """Execute a saved plan against a page."""
    plan_path = args.plan
    with open(plan_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    plan = data.get("plan", data)

    # Re-inspect to get fresh element map
    inspect_url = args.url or data.get("page_url", "")
    if not inspect_url:
        inspect_url = plan.get("steps", [{}])[0].get("value", "")

    print(f"Re-inspecting: {inspect_url}")
    inspection = crawl_page(
        url=inspect_url,
        login_url=args.login_url or config.get("target", {}).get("login_url", ""),
        username=args.username or config.get("target", {}).get("username", ""),
        password=args.password or config.get("target", {}).get("password", ""),
    )
    print(f"Found {len(inspection.get('elements', []))} elements")
    print(f"Executing {len(plan.get('steps', []))} steps...\n")

    executor = Executor(inspection, headless=not args.headed)
    results = asyncio_run(executor.execute(plan, output_dir=args.output_dir or "output"))

    print(f"{'='*60}")
    print(f"  ✅ Passed: {results['passed']} / ❌ Failed: {results['failed']}")
    print(f"{'='*60}\n")

    for r in results.get("results", []):
        icon = "✅" if r["status"] == "pass" else "❌"
        print(f"  {icon} {r['step']}")
        if args.verbose:
            print(f"      {r['detail']}")

    return 1 if results["failed"] else 0


def cmd_auto(args, config):
    """Full pipeline: inspect → analyze (LLM) → execute."""
    from adapters.llm import create_llm_adapter

    llm = create_llm_adapter(config.get("llm", {}))

    print(f"════════════════════════════════════")
    print(f"  🔍 Phase 1: Inspect page")
    print(f"════════════════════════════════════\n")

    analyzer = PageAnalyzer()
    inspection = analyzer.inspect(
        url=args.url,
        login_url=args.login_url or config.get("target", {}).get("login_url", ""),
        username=args.username or config.get("target", {}).get("username", ""),
        password=args.password or config.get("target", {}).get("password", ""),
        wait_for_selector=args.wait_for or "",
    )
    print(f"  Found {len(inspection.get('elements', []))} elements on page")
    summary = analyzer.summarize(inspection)

    print(f"\n{'='*60}")
    print(f"  🤖 Phase 2: LLM analysis ({llm.name})")
    print(f"{'='*60}\n")

    plan = analyzer.generate_plan(llm.chat, args.goal, summary)
    for i, step in enumerate(plan.get("steps", []), 1):
        action = step.get("action", "?")
        desc = step.get("description", "")
        print(f"  {i}. [{action:>8}] {desc}")

    if args.dry_run:
        print(f"\n{'='*60}")
        print(f"  🟡 Dry run — not executing")
        print(f"{'='*60}")
        return 0

    print(f"\n{'='*60}")
    print(f"  🚀 Phase 3: Execute")
    print(f"{'='*60}\n")

    executor = Executor(inspection, headless=not args.headed)
    results = asyncio_run(executor.execute(plan, output_dir=args.output_dir or "output"))

    print(f"\n{'='*60}")
    print(f"  ✅ Passed: {results['passed']} / ❌ Failed: {results['failed']}")
    print(f"{'='*60}\n")

    for r in results.get("results", []):
        icon = "✅" if r["status"] == "pass" else "❌"
        print(f"  {icon} {r['step']}: {r['detail']}")

    return 1 if results["failed"] else 0


def cmd_web(args, config):
    """Start the web UI (reuse Flask app)."""
    from web.app import create_app

    app = create_app(config)
    host = config.get("web", {}).get("host", "0.0.0.0")
    port = config.get("web", {}).get("port", 5000)
    print(f"Web UI: http://{host}:{port}")
    app.run(host=host, port=port, debug=config.get("web", {}).get("debug", True))


def asyncio_run(coro):
    """Run an async coroutine, handling event loop conflicts."""
    try:
        import asyncio
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import nest_asyncio
            nest_asyncio.apply()
            return loop.run_until_complete(coro)
        return asyncio.run(coro)
    except RuntimeError:
        import asyncio
        return asyncio.run(coro)


def main():
    parser = argparse.ArgumentParser(
        prog="utilitye2e-ai",
        description="AI-powered page inspector & e2e action executor. Inspects a page with Playwright, "
                    "uses AI to identify elements, then executes actions.",
    )
    parser.add_argument("--config", default="config.yaml", help="Config file path")

    sub = parser.add_subparsers(dest="command", required=True)

    # inspect
    p_inspect = sub.add_parser("inspect", help="Inspect page, show element map")
    p_inspect.add_argument("--url", required=True)
    p_inspect.add_argument("--login-url")
    p_inspect.add_argument("-u", "--username")
    p_inspect.add_argument("-p", "--password")
    p_inspect.add_argument("--wait-for", help="CSS selector to wait for")
    p_inspect.add_argument("-o", "--output", help="Save element map as JSON")

    # analyze
    p_analyze = sub.add_parser("analyze", help="AI-analyze a page and generate action plan")
    p_analyze.add_argument("--url", required=True)
    p_analyze.add_argument("--goal", required=True)
    p_analyze.add_argument("--login-url")
    p_analyze.add_argument("-u", "--username")
    p_analyze.add_argument("-p", "--password")
    p_analyze.add_argument("--wait-for")
    p_analyze.add_argument("-o", "--output", help="Save plan as JSON")

    # run
    p_run = sub.add_parser("run", help="Execute a saved plan against a page")
    p_run.add_argument("--url", help="URL to test (defaults to plan's URL)")
    p_run.add_argument("--plan", required=True, help="Plan JSON file")
    p_run.add_argument("--headed", action="store_true", help="Show browser")
    p_run.add_argument("--login-url")
    p_run.add_argument("-u", "--username")
    p_run.add_argument("-p", "--password")
    p_run.add_argument("--output-dir", default="output")
    p_run.add_argument("-v", "--verbose", action="store_true")

    # auto (full pipeline)
    p_auto = sub.add_parser("auto", help="Full pipeline: inspect → AI analyze → execute")
    p_auto.add_argument("--url", required=True)
    p_auto.add_argument("--goal", required=True)
    p_auto.add_argument("--headed", action="store_true", help="Show browser")
    p_auto.add_argument("--dry-run", action="store_true", help="Skip execution, only show plan")
    p_auto.add_argument("--login-url")
    p_auto.add_argument("-u", "--username")
    p_auto.add_argument("-p", "--password")
    p_auto.add_argument("--wait-for")
    p_auto.add_argument("--output-dir", default="output")

    # web
    sub.add_parser("web", help="Start Web UI")

    args = parser.parse_args()
    config = load_config(args.config)

    cmds = {
        "inspect": cmd_inspect,
        "analyze": cmd_analyze,
        "run": cmd_run,
        "auto": cmd_auto,
        "web": cmd_web,
    }
    exit_code = cmds[args.command](args, config)
    if exit_code:
        sys.exit(exit_code)


if __name__ == "__main__":
    main()