#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"
source venv/bin/activate
export PYTHONPATH="$SCRIPT_DIR"
python3 web/app.py
