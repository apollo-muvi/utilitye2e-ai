"""
Flask Web App — SPA for AI Dialog + Spec editing + Test execution.
"""

import os
import io
import sys
from contextlib import contextmanager

from flask import Flask, render_template, jsonify, request
from flask_cors import CORS

from application.workflows import (
    analyze_test_spec,
    derive_login_url,
    discover_page,
    run_test_spec,
)
from config import load_config
from core.spec import TestSpec


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

    @contextmanager
    def _capture_log():
        """Capture stdout/stderr into a list of log lines."""
        buf = io.StringIO()
        old_out, old_err = sys.stdout, sys.stderr
        sys.stdout = sys.stderr = buf
        try:
            yield buf
        finally:
            sys.stdout, sys.stderr = old_out, old_err

    def _extract_log(buf):
        lines = buf.getvalue().strip().split("\n") if buf.getvalue().strip() else []
        return [l for l in lines if l.strip()]

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/api/config")
    def get_config():
        llm_cfg = config.get("llm", {})
        schema_cfg = config.get("schema", {})
        target_cfg = config.get("target", {})
        return jsonify(
            {
                "llm_adapter": llm_cfg.get("adapter", "openrouter"),
                "llm_model": llm_cfg.get("model", ""),
                "schema_adapter": schema_cfg.get("adapter", "postgres"),
                "target": target_cfg,
            }
        )

    @app.route("/api/shutdown", methods=["POST"])
    def shutdown():
        import signal

        os.kill(os.getpid(), signal.SIGINT)
        return jsonify({"ok": True})

    @app.route("/api/ai/discover", methods=["POST"])
    def ai_discover():
        """Pure DOM crawl — no LLM. Returns testable elements list."""
        data = request.json
        with _capture_log() as log_buf:
            try:
                target_url = data.get("target_url", "")
                login_url = derive_login_url(target_url, data.get("login_url", ""))
                username = data.get("username", "")
                password = data.get("password", "")

                print(f"=== DISCOVER === {target_url}")
                result = discover_page(
                    target_url=target_url,
                    login_url=login_url,
                    username=username,
                    password=password,
                )

                print(f"✓ Found {len(result.elements)} elements (title={result.title})")
                return jsonify(
                    {
                        "elements": result.elements,
                        "title": result.title,
                        "logs": _extract_log(log_buf),
                    }
                )
            except Exception as e:
                import traceback

                traceback.print_exc()
                return jsonify({"error": str(e), "logs": _extract_log(log_buf)}), 500

    @app.route("/api/ai/analyze", methods=["POST"])
    def ai_analyze():
        data = request.json
        with _capture_log() as log_buf:
            try:
                print(f"=== AI ANALYZE ===")
                print(f"Input: description='{data.get('description', '')[:100]}'")
                print(f"→ Creating adapters...")
                target_url = data.get("target_url", "")
                spec = analyze_test_spec(
                    config=config,
                    description=data["description"],
                    target_url=target_url,
                    login_url=data.get("login_url", ""),
                    username=data.get("username", ""),
                    password=data.get("password", ""),
                    selected_elements=data.get("selected_elements", []),
                )
                print(
                    f"✓ Analysis complete: {spec.name} with {len(spec.fields)} fields"
                )
                return jsonify(
                    {
                        "spec": spec.to_dict(),
                        "spec_json": spec.to_json(),
                        "logs": _extract_log(log_buf),
                    }
                )
            except Exception as e:
                import traceback

                traceback.print_exc()
                return jsonify({"error": str(e), "logs": _extract_log(log_buf)}), 500

    @app.route("/api/ai/run", methods=["POST"])
    def ai_run():
        data = request.json
        with _capture_log() as log_buf:
            try:
                spec = TestSpec.from_dict(data["spec"])
                print(f"=== TEST RUN ===")
                print(f"Spec: {spec.name}")
                print(f"Steps: {len(spec.steps)}")
                print(f"Target: {spec.target.url}")
                result = run_test_spec(spec, headed=data.get("headed", False))
                summary = result.summary
                print(
                    f"✓ Done: passed={summary.get('passed', 0)}, "
                    f"failed={summary.get('failed', 0)}"
                )
                return jsonify(
                    {
                        "summary": summary,
                        "results": [
                            {"name": r.name, "status": r.status, "detail": r.detail}
                            for r in result.results
                        ],
                        "logs": _extract_log(log_buf),
                    }
                )
            except Exception as e:
                import traceback

                traceback.print_exc()
                return jsonify({"error": str(e), "logs": _extract_log(log_buf)}), 500

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5001, debug=False)
