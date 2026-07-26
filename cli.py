"""
CLI entry point.

Usage:
    utilitye2e-ai tables                         # List DB tables
    utilitye2e-ai columns --table parents        # Show table columns
    utilitye2e-ai analyze --description "..." --table parents  # AI generate spec
    utilitye2e-ai run --spec spec.json           # Execute spec
    utilitye2e-ai web                            # Start Web UI
"""

import sys
import os
import asyncio
import argparse
import json

# Ensure project root is on path when running from source
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import load_config
from adapters.schema import create_schema_adapter
from adapters.llm import create_llm_adapter
from ai.analyzer import Analyzer
from core.spec import TestSpec
from core.runner import Runner


def cmd_tables(args, config):
    schema = create_schema_adapter(config["schema"])
    tables = schema.get_tables()
    print(f"Found {len(tables)} tables:\n")
    for t in tables:
        print(f"  {t}")


def cmd_columns(args, config):
    schema = create_schema_adapter(config["schema"])
    cols = schema.get_columns(args.table)
    print(f"Table: {args.table} ({len(cols)} columns)\n")
    for c in cols:
        flags = []
        if c.is_pk: flags.append("PK")
        if not c.nullable: flags.append("NOT NULL")
        flag_str = f" [{', '.join(flags)}]" if flags else ""
        print(f"  {c.name:30s} {c.data_type:20s}{flag_str}")


def cmd_analyze(args, config):
    schema = create_schema_adapter(config["schema"])
    llm = create_llm_adapter(config["llm"])
    analyzer = Analyzer(llm, schema)

    print(f"Generating spec for: {args.description}")
    print(f"LLM: {llm.name}\n")

    spec = analyzer.generate(
        description=args.description,
        target_url=args.url,
        login_url=args.login_url,
        username=args.username,
        password=args.password,
    )

    output = args.output or f"spec_{args.table}.json"
    with open(output, "w", encoding="utf-8") as f:
        f.write(spec.to_json())
    print(f"Spec saved to: {output}\n")
    print(spec.to_json())


def cmd_run(args, config):
    spec = TestSpec.from_file(args.spec)
    print(f"Running: {spec.name}")
    print(f"Steps: {len(spec.steps)}\n")

    runner = Runner(spec, headless=not args.headed)
    summary = asyncio.run(runner.run())

    print(f"\n{'='*50}")
    print(f"Results: {summary['passed']} passed, {summary['failed']} failed, {summary['skipped']} skipped")
    print(f"{'='*50}")

    for r in runner.recorder.results:
        status_icon = {"pass": "✓", "fail": "✗", "skip": "−"}[r.status]
        print(f"  {status_icon} {r.name}: {r.detail}")

    sys.exit(1 if summary["failed"] > 0 else 0)


def cmd_web(args, config):
    from web.app import create_app
    app = create_app(config)
    app.run(
        host=config["web"]["host"],
        port=config["web"]["port"],
        debug=config["web"]["debug"],
    )


def main():
    parser = argparse.ArgumentParser(
        prog="utilitye2e-ai",
        description="AI-powered E2E test generator",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("tables", help="List DB tables")
    p_cols = sub.add_parser("columns", help="Show table columns")
    p_cols.add_argument("--table", required=True)
    p_analyze = sub.add_parser("analyze", help="AI-generate a test spec")
    p_analyze.add_argument("--description", "-d", required=True)
    p_analyze.add_argument("--url", required=True, help="Target URL")
    p_analyze.add_argument("--login-url", default="", help="Login URL")
    p_analyze.add_argument("--username", default="")
    p_analyze.add_argument("--password", default="")
    p_analyze.add_argument("--table", "-t", default="")
    p_analyze.add_argument("--output", "-o", default="")
    p_run = sub.add_parser("run", help="Execute a test spec")
    p_run.add_argument("--spec", "-s", required=True)
    p_run.add_argument("--headed", action="store_true", help="Show browser")
    sub.add_parser("web", help="Start Web UI")

    # config file option on top-level
    parser.add_argument("--config", default="config.yaml")

    args = parser.parse_args()
    config = load_config(args.config)

    cmds = {
        "tables": cmd_tables,
        "columns": cmd_columns,
        "analyze": cmd_analyze,
        "run": cmd_run,
        "web": cmd_web,
    }
    cmds[args.command](args, config)


if __name__ == "__main__":
    main()
