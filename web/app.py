"""
Flask Web App — SPA for AI Dialog + Spec editing + Test execution.
"""

import os
import io
import sys
import asyncio
import json
import tempfile
from contextlib import contextmanager

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
        return jsonify({
            "llm_adapter": llm_cfg.get("adapter", "openrouter"),
            "llm_model": llm_cfg.get("model", ""),
            "schema_adapter": schema_cfg.get("adapter", "postgres"),
        })

    @app.route("/api/shutdown", methods=["POST"])
    def shutdown():
        import signal, os
        os.kill(os.getpid(), signal.SIGINT)
        return jsonify({"ok": True})

    def _derive_login_url(target_url, login_url=""):
        """Use explicit login_url, or derive from target URL's tenant."""
        if login_url:
            return login_url
        from urllib.parse import urlparse
        parsed = urlparse(target_url)
        parts = parsed.path.split("/")
        if "t" in parts:
            idx = parts.index("t")
            if idx + 1 < len(parts):
                return f"{parsed.scheme}://{parsed.netloc}/t/{parts[idx+1]}/login"
        return ""

    @app.route("/api/ai/discover", methods=["POST"])
    def ai_discover():
        """Pure DOM crawl — no LLM. Returns testable elements list."""
        data = request.json
        with _capture_log() as log_buf:
            try:
                target_url = data.get("target_url", "")
                login_url = _derive_login_url(target_url, data.get("login_url", ""))
                username = data.get("username", "")
                password = data.get("password", "")

                print(f"=== DISCOVER === {target_url}")
                from ai.page_crawler import crawl_page
                dom = crawl_page(url=target_url, login_url=login_url, username=username, password=password)

                # Build selectable element list
                elements = []
                skip_labels = {"☰", "登出", "Logout", "Sign out", "取消", "儲存", "Cancel", "Save"}
                for btn in dom.get("buttons", []):
                    t = btn["text"].strip()
                    if t and len(t) < 40 and t not in skip_labels:
                        el = {"type": "button", "label": t, "text": t}
                        if btn.get("row", 0) > 0:
                            el["row"] = btn["row"]
                            el["occurrence"] = btn.get("occurrence", 1)
                            el["rowLabel"] = btn.get("rowLabel", "")
                            el["isRepeated"] = btn.get("isRepeated", False)
                        elements.append(el)
                # Also include table row structure
                for tr in dom.get("tableRows", []):
                    elements.append({"type": "tableRow", "label": tr.get("label",""), "text": f"行{tr.get('index','')}: {tr.get('label','')} [{', '.join(tr.get('buttons',[]))}]"})
                for inp in dom.get("inputs", []):
                    label = inp.get("label") or inp.get("placeholder") or inp.get("name") or ""
                    if label:
                        elements.append({"type": "input", "label": label, "text": f"{inp.get('tag','input')}: {label}"})
                for th in dom.get("tables", []):
                    elements.append({"type": "column", "label": th, "text": f"column: {th}"})

                title = dom.get("title", "")
                print(f"✓ Found {len(elements)} elements (title={title})")
                return jsonify({"elements": elements, "title": title, "logs": _extract_log(log_buf)})
            except Exception as e:
                import traceback; traceback.print_exc()
                return jsonify({"error": str(e), "logs": _extract_log(log_buf)}), 500

    @app.route("/api/ai/analyze", methods=["POST"])
    def ai_analyze():
        data = request.json
        with _capture_log() as log_buf:
            try:
                print(f"=== AI ANALYZE ===")
                print(f"Input: description='{data.get('description', '')[:100]}'")
                print(f"→ Creating adapters...")
                schema = create_schema_adapter(config["schema"])
                llm = create_llm_adapter(config["llm"])
                analyzer = Analyzer(llm, schema)
                target_url = data.get("target_url", "")
                login_url = _derive_login_url(target_url, data.get("login_url", ""))
                spec = analyzer.generate(
                    description=data["description"],
                    target_url=target_url,
                    login_url=login_url,
                    username=data.get("username", ""),
                    password=data.get("password", ""),
                    selected_elements=data.get("selected_elements", []),
                )
                print(f"✓ Analysis complete: {spec.name} with {len(spec.fields)} fields")
                return jsonify({"spec": spec.to_dict(), "spec_json": spec.to_json(), "logs": _extract_log(log_buf)})
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
                runner = Runner(spec, headless=not data.get("headed", False))
                summary = asyncio.run(runner.run())
                print(f"✓ Done: passed={summary.get('passed', 0)}, failed={summary.get('failed', 0)}")
                return jsonify({
                    "summary": summary,
                    "results": [
                        {"name": r.name, "status": r.status, "detail": r.detail}
                        for r in runner.recorder.results
                    ],
                    "logs": _extract_log(log_buf),
                })
            except Exception as e:
                import traceback
                traceback.print_exc()
                return jsonify({"error": str(e), "logs": _extract_log(log_buf)}), 500

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5001, debug=False)
