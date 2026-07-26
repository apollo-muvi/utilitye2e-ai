#!/bin/bash
# Quick demo: Test utilitye2e-ai against mock target

echo "=== Starting Mock Target ==="
cd /home/one/utilitye2e-ai
/home/one/utilitye2e/venv/bin/python3 mock_server.py &
MOCK_PID=$!
sleep 3

echo "Mock server running on http://localhost:3002 (PID: $MOCK_PID)"
echo ""
echo "=== Testing page_crawler ==="
/home/one/utilitye2e/venv/bin/python3 -c "
from ai.page_crawler import crawl_page
import json
result = crawl_page('http://localhost:3002/')
print('Buttons found:', len(result['buttons']))
print('Inputs found:', len(result['inputs']))
print('Page title:', result.get('title', 'N/A'))
"

echo ""
echo "=== Mock server stopped ==="
kill $MOCK_PID 2>/dev/null
