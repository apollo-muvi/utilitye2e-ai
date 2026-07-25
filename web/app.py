"""
Flask Web App — SPA for AI Dialog + Spec editing + Test execution.
"""

import os
import asyncio
import json
import tempfile

from flask import Flask, render_template, jsonify, request
from flask_cors import CORS

from config import load_config
from adapters.schema import create_schema_adapter
from adapters.llm import create_llm_adapter
from ai.analyzer import Analyzer
from core.spec import TestSpec
from core.runner import Runner


def create_app(config: dict = None) -> Flask:
    if config is None:
        config = load_config()

    template_dir = os.path.join(os.path.dirname(__file__), "templates")
    static_dir = os.path.join(os.path.dirname(__file__), "static")
    app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)
    CORS(app)
    app.secret_key = os.getenv("SECRET_KEY", "dev-key")

    # Store config on app for access in routes
    app.config["APP_CONFIG"] = config

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/api/config")
    def get_config():
        llm_cfg = config.get("llm", {})
        schema_cfg = config.get("schema", {})
        return jsonify({
            "llm_adapter": llm_cfg.get("adapter", "openrouter"),
            "llm_model": llm_cfg.get("model", ""),
            "schema_adapter": schema_cfg.get("adapter", "postgres"),
            "base_url": config.get("target", {}).get("base_url", ""),
        })

    @app.route("/api/tables")
    def list_tables():
        try:
            schema = create_schema_adapter(config["schema"])
            tables = schema.get_tables()
            return jsonify({"tables": tables})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/tables/<table>/columns")
    def table_columns(table):
        try:
            schema = create_schema_adapter(config["schema"])
            cols = schema.get_columns(table)
            return jsonify({"columns": [c.to_dict() for c in cols]})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @app.route("/api/ai/analyze", methods=["POST"])
    def ai_analyze():
        data = request.json
        print(f"\n=== AI ANALYZE DEBUG ===")
        print(f"Input: description='{data.get('description', '')[:100]}...', table='{data.get('table', '')}', url_path='{data.get('url_path', '')}'")
        try:
            print(f"→ Creating schema adapter...")
            schema = create_schema_adapter(config["schema"])
            print(f"→ Creating LLM adapter...")
            llm = create_llm_adapter(config["llm"])
            print(f"→ Creating analyzer...")
            analyzer = Analyzer(llm, schema)
            print(f"→ Calling analyzer.generate()...")
            spec = analyzer.generate(
                description=data["description"],
                table=data.get("table", ""),
                base_url=config["target"]["base_url"],
                login_url=config["target"].get("login_url", ""),
                username=config["target"].get("username", ""),
                password=config["target"].get("password", ""),
                url_path=data.get("url_path", ""),
            )
            print(f"✓ Analysis complete: {spec.name} with {len(spec.fields)} fields")
            print(f"=== END DEBUG ===\n")
            return jsonify({"spec": spec.to_dict(), "spec_json": spec.to_json()})
        except Exception as e:
            print(f"✗ ERROR: {e}")
            print(f"=== END DEBUG (FAILED) ===\n")
            import traceback
            traceback.print_exc()
            return jsonify({"error": str(e)}), 500

    @app.route("/api/ai/run", methods=["POST"])
    def ai_run():
        data = request.json
        print(f"\n=== TEST RUN DEBUG ===")
        print(f"Spec: {data.get('spec', {}).get('name', 'unknown')}")
        print(f"Actions: {data.get('spec', {}).get('actions', [])}")
        print(f"Target URL: {data.get('spec', {}).get('target', {}).get('url', '')}")
        try:
            spec = TestSpec.from_dict(data["spec"])
            print(f"→ Creating runner (headless={not data.get('headed', False)})...")
            runner = Runner(spec, headless=not data.get("headed", False))
            print(f"→ Running tests...")
            summary = asyncio.run(runner.run())
            print(f"✓ Test run complete: passed={summary.get('passed', 0)}, failed={summary.get('failed', 0)}")
            print(f"=== END DEBUG ===\n")
            return jsonify({
                "summary": summary,
                "results": [
                    {"name": r.name, "status": r.status, "detail": r.detail}
                    for r in runner.recorder.results
                ],
            })
        except Exception as e:
            print(f"✗ ERROR: {e}")
            print(f"=== END DEBUG (FAILED) ===\n")
            import traceback
            traceback.print_exc()
            return jsonify({"error": str(e)}), 500

    return app
