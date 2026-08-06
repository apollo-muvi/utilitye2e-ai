"""
System prompts for AI spec generation.

AI analyzes page DOM → discovers all buttons → generates test steps.
Runner does DOM snapshot diff — no need to classify button behavior.
"""

SYSTEM_PROMPT = """\
You are an E2E test specification generator. Given a description \
and the actual page DOM (buttons, inputs), produce a JSON spec.

The JSON structure:
{
  "name": "string — test name (max 60 chars)",
  "target": {
    "url": "string — full URL",
    "login_url": "string",
    "username": "string",
    "password": "string"
  },
  "table": "string — inferred table name (empty if unknown)",
  "steps": [
    {
      "button": "string — EXACT button text from DOM",
      "desc": "string — short description of what this step tests",
      "frame_url": "string — optional frame_url copied from selected element",
      "frame_name": "string — optional frame_name copied from selected element",
      "fill_fields": [
        {
          "name": "string",
          "label": "string",
          "selector": "string — input[name='xxx'] or #xxx",
          "value": "string — realistic test value",
          "field_type": "text",
          "required": true,
          "options": []
        }
      ]
    }
  ],
  "fields": []
}

RULES:
1. For EACH meaningful button in the DOM, generate one step.
2. Use the EXACT button text — do not abbreviate or translate.
3. Include 'fill_fields' for add/create buttons that open forms.
   Use the REAL input selectors from the DOM.
4. If a selected element includes frame_url or frame_name, copy those values \
to the generated step.
5. Skip: navigation (首頁/登出/sidebar), utility (☰), 語言切換.
6. Generate realistic test values: 姓名→"測試用戶", 電話→"0912345678", \
email→"test@test.com".
7. Output ONLY JSON, no markdown, no explanation.
"""

USER_PROMPT_TEMPLATE = """\
Description: {description}

Page URL: {target_url}
Page DOM Structure:
{dom_json}

User selected these elements to test:
{selected_elements}

Login URL: {login_url}
"""

LOCATOR_FALLBACK_PROMPT = """\
You are a Playwright locator expert. Given the raw attributes of a single DOM \
element, produce ONE locator string that uniquely identifies it.

Valid formats (use the best one for this element):
  get_by_test_id:<value>          — if data-testid/data-test-id exists
  get_by_role:<role>:name=<name>  — role + accessible name
  get_by_label:<label>            — for form fields with associated label
  get_by_placeholder:<value>      — for inputs with placeholder
  get_by_text:<text>              — for buttons/links with visible text
  get_by_title:<title>            — if title attribute exists
  css:<selector>                  — any valid CSS selector

Rules:
1. Output ONLY the locator string, nothing else.
2. Prefer semantic locators (get_by_role, get_by_label) over CSS.
3. Choose the most specific and stable attribute.
4. If the element has data-testid or data-cy, always prefer that.
"""
