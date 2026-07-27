#!/bin/bash
cd /home/apollo/utilitye2e-ai
source venv/bin/activate
export PYTHONPATH=/home/apollo/utilitye2e-ai
export PLAYWRIGHT_BROWSERS_PATH=/home/apollo/.cache/ms-playwright
python3 web/app.py
