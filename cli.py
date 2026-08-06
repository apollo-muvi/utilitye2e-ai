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
import argparse
import json

# Ensure project root is on path when running from source
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from application.workflows import (
    analyze_test_spec,
    build_analyzer,
    create_posture_finding_record,
    init_posture_pack,
    list_posture_finding_records,
    promote_posture_finding_record,
    render_posture_pack,
    run_test_spec,
)
from config import load_config
from adapters.schema import create_schema_adapter
from core.spec import TestSpec


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
        if c.is_pk:
            flags.append("PK")
        if not c.nullable:
            flags.append("NOT NULL")
        flag_str = f" [{', '.join(flags)}]" if flags else ""
        print(f"  {c.name:30s} {c.data_type:20s}{flag_str}")


def cmd_analyze(args, config):
    analyzer = build_analyzer(config)
    print(f"Generating spec for: {args.description}")
    print(f"LLM: {analyzer.llm.name}\n")

    spec = analyze_test_spec(
        config=config,
        description=args.description,
        target_url=args.url,
        login_url=args.login_url,
        username=args.username,
        password=args.password,
        analyzer=analyzer,
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

    result = run_test_spec(spec, headed=args.headed)
    summary = result.summary

    print(f"\n{'='*50}")
    print(
        f"Results: {summary['passed']} passed, {summary['failed']} failed, {summary['skipped']} skipped"
    )
    print(f"{'='*50}")

    for r in result.results:
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


def cmd_posture(args, config):
    if args.posture_command == "init":
        cmd_posture_init(args, config)
        return
    if args.posture_command == "render":
        cmd_posture_render(args, config)
        return
    if args.posture_command == "finding" and args.finding_command == "create":
        cmd_posture_finding_create(args, config)
        return
    if args.posture_command == "finding" and args.finding_command == "list":
        cmd_posture_finding_list(args, config)
        return
    if args.posture_command == "finding" and args.finding_command == "promote":
        cmd_posture_finding_promote(args, config)
        return
    raise ValueError(f"Unsupported posture command: {args.posture_command}")


def cmd_posture_init(args, config):
    pack, warnings = init_posture_pack(
        product=args.product,
        url=args.url,
        login_url=args.login_url,
        username=args.username,
        password=args.password,
    )
    import yaml

    output = yaml.safe_dump(pack.to_dict(), allow_unicode=True, sort_keys=False)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Posture pack saved to: {args.output}")
        print(f"  {len(pack.workflows)} workflows, "
              f"{sum(len(w.checks) for w in pack.workflows)} checks")
        if warnings:
            print()
            for w in warnings:
                print(f"  WARNING: {w}")
        return
    print(output, end="")


def cmd_posture_render(args, config):
    worksheet = render_posture_pack(args.pack)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(worksheet)
        print(f"Posture worksheet saved to: {args.output}")
        return
    print(worksheet, end="")


def cmd_posture_finding_create(args, config):
    should_be_automated = None
    if args.automation_candidate:
        should_be_automated = True
    elif args.no_automation:
        should_be_automated = False

    finding = create_posture_finding_record(
        pack_path=args.pack,
        finding=args.finding,
        workflow_id=args.workflow_id,
        check_id=args.check_id,
        user_impact=args.impact,
        missing_expectation=args.missing_expectation,
        should_be_automated=should_be_automated,
        suggested_assertion=args.suggested_assertion,
        suggested_checklist_update=args.suggested_checklist_update,
        evidence=args.evidence,
        owner=args.owner,
        status=args.status,
    )
    output = finding.to_yaml()
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Posture finding saved to: {args.output}")
        return
    print(output, end="")


def cmd_posture_finding_list(args, config):
    findings = list_posture_finding_records(
        path=args.path,
        status=args.status,
        automation_candidates=args.automation_candidates,
        recursive=args.recursive,
    )
    if args.format == "json":
        print(
            json.dumps(
                [finding.to_dict() for finding in findings],
                ensure_ascii=False,
                indent=2,
            )
        )
        return
    if args.format == "yaml":
        print(
            yaml_dump_all([finding.to_dict() for finding in findings]),
            end="",
        )
        return
    print(render_findings_table(findings))


def cmd_posture_finding_promote(args, config):
    candidate = promote_posture_finding_record(
        finding_path=args.finding_file,
        assertion=args.assertion,
        assertion_type=args.assertion_type,
        priority=args.priority,
        force=args.force,
    )
    output = candidate.to_yaml()
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Posture assertion candidate saved to: {args.output}")
        return
    print(output, end="")


def yaml_dump_all(rows):
    import yaml

    return yaml.safe_dump(rows, allow_unicode=True, sort_keys=False)


def render_findings_table(findings):
    if not findings:
        return "No posture findings found."

    headers = ["status", "auto", "workflow", "check", "finding"]
    rows = []
    for finding in findings:
        rows.append(
            [
                finding.status,
                "yes" if finding.should_be_automated else "no",
                finding.workflow_id,
                finding.check_id,
                finding.finding,
            ]
        )

    widths = [
        max(len(str(row[index])) for row in [headers] + rows)
        for index in range(len(headers))
    ]
    lines = [
        "  ".join(header.ljust(widths[index]) for index, header in enumerate(headers)),
        "  ".join("-" * width for width in widths),
    ]
    for row in rows:
        lines.append(
            "  ".join(str(cell).ljust(widths[index]) for index, cell in enumerate(row))
        )
    return "\n".join(lines)


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
    p_posture = sub.add_parser("posture", help="Posture review utilities")
    posture_sub = p_posture.add_subparsers(dest="posture_command", required=True)
    p_posture_init = posture_sub.add_parser(
        "init", help="Crawl a URL and auto-generate a posture pack"
    )
    p_posture_init.add_argument("--url", required=True, help="Target URL to crawl")
    p_posture_init.add_argument("--product", required=True, help="Product name")
    p_posture_init.add_argument("--login-url", default="")
    p_posture_init.add_argument("--username", default="")
    p_posture_init.add_argument("--password", default="")
    p_posture_init.add_argument("--output", "-o", default="")
    p_posture_render = posture_sub.add_parser(
        "render", help="Render a posture pack as a manual worksheet"
    )
    p_posture_render.add_argument("--pack", "-p", required=True)
    p_posture_render.add_argument("--output", "-o", default="")
    p_posture_finding = posture_sub.add_parser(
        "finding", help="Create and manage posture findings"
    )
    finding_sub = p_posture_finding.add_subparsers(
        dest="finding_command", required=True
    )
    p_finding_create = finding_sub.add_parser(
        "create", help="Create a structured posture finding"
    )
    p_finding_create.add_argument("--pack", "-p", required=True)
    p_finding_create.add_argument("--finding", required=True)
    p_finding_create.add_argument("--workflow-id", default="")
    p_finding_create.add_argument("--check-id", default="")
    p_finding_create.add_argument("--impact", default="")
    p_finding_create.add_argument("--missing-expectation", default="")
    automation_group = p_finding_create.add_mutually_exclusive_group()
    automation_group.add_argument("--automation-candidate", action="store_true")
    automation_group.add_argument("--no-automation", action="store_true")
    p_finding_create.add_argument("--suggested-assertion", default="")
    p_finding_create.add_argument("--suggested-checklist-update", default="")
    p_finding_create.add_argument("--evidence", action="append", default=[])
    p_finding_create.add_argument("--owner", default="")
    p_finding_create.add_argument("--status", default="open")
    p_finding_create.add_argument("--output", "-o", default="")
    p_finding_list = finding_sub.add_parser(
        "list", help="List structured posture findings"
    )
    p_finding_list.add_argument("--path", "-p", required=True)
    p_finding_list.add_argument("--status", default="")
    p_finding_list.add_argument("--automation-candidates", action="store_true")
    p_finding_list.add_argument("--recursive", action="store_true")
    p_finding_list.add_argument(
        "--format",
        choices=["table", "json", "yaml"],
        default="table",
    )
    p_finding_promote = finding_sub.add_parser(
        "promote", help="Promote a finding into an assertion candidate"
    )
    p_finding_promote.add_argument("--finding-file", "-f", required=True)
    p_finding_promote.add_argument("--assertion", default="")
    p_finding_promote.add_argument("--assertion-type", default="ui")
    p_finding_promote.add_argument("--priority", default="medium")
    p_finding_promote.add_argument("--force", action="store_true")
    p_finding_promote.add_argument("--output", "-o", default="")
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
        "posture": cmd_posture,
        "web": cmd_web,
    }
    cmds[args.command](args, config)


if __name__ == "__main__":
    main()
