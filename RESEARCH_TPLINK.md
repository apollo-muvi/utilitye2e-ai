# TP-Link Router GUI - Research Findings

## Target Analysis

**URL**: https://emulator.tp-link.com/Archer_AX11000v2_US_simulator/#wirelessBasic

## Architecture Pattern: SPA (Single Page Application)

### Initial HTML (Server-rendered)
```html
<!DOCTYPE html>
<html>
<head>
    <title>Opening...</title>
    <!-- Many JS files loaded -->
</head>
<body>
    <div id="main-container"></div>  <!-- Empty! Content rendered by JS -->
</body>
</html>
```

### Dynamic Rendering
- **Framework**: Custom jQuery-based framework (`$.su.*`)
- **Content**: All UI rendered via JavaScript
- **Navigation**: Hash-based routing (`#wirelessBasic`)

## Page Crawler Results (Current)

| Metric | Result | Issue |
|--------|--------|-------|
| Page title | Empty | Set by JS after load |
| Buttons found | 0 | Rendered by JS |
| Inputs found | 35 (fake) | Only language selector |
| Tables found | 0 | Rendered by JS |

## Challenge Identified

**Problem**: The current `page_crawler.py` extracts DOM immediately after page load, but SPAs render content **asynchronously** via JavaScript.

**What the crawler sees**:
```javascript
<div id="main-container"></div>  <!-- Empty -->
```

**What the user sees** (after JS renders):
```javascript
<div id="main-container">
    <button>Save</button>
    <input name="ssid" />
    <!-- ... full UI ... -->
</div>
```

## Solutions for utilitye2e-ai

### Option 1: Wait for SPA rendering (Quick fix)
```python
# In page_crawler.py
await page.goto(url, wait_until="networkidle")
await page.wait_for_timeout(3000)  # Add explicit wait
# Also wait for specific elements
await page.wait_for_selector("#main-container > *", timeout=10000)
```

### Option 2: Wait for specific selectors (Better)
```python
# Wait until main-container has children
await page.wait_for_function(
    "document.querySelector('#main-container').children.length > 0"
)
```

### Option 3: Detect SPA pattern (Advanced)
```python
# Check if content is JS-rendered
is_spa = await page.evaluate("""
    () => {
        const main = document.getElementById('main-container');
        return main && main.children.length === 0 &&
               document.scripts.length > 5;  // Heuristic
    }
""")
```

## Real Router GUI Patterns (for AI training)

Based on TP-Link simulator:

### Common UI Elements
1. **Sidebar navigation** (left menu)
2. **Main content area** (right panel)
3. **Save/Apply buttons** (top right)
4. **Form sections** (grouped settings)
5. **Help tooltips** (icon buttons)

### Selector Strategies
| Element | TP-Link Pattern | Generic Pattern |
|---------|----------------|-----------------|
| Save button | `button:has-text("Save")` | `button[type="submit"]` |
| Input fields | `input[name="field_name"]` | `input[data-field]` |
| Sections | `.panel-title` | `h2, h3, .section` |
| Tabs | `.tab-item` | `[role="tab"]` |

## Recommendation

**For utilitye2e-ai MVP**:
1. Add `wait_for_selector()` to `page_crawler.py`
2. Test against both mock target (static) and TP-Link (SPA)
3. Document SPA handling in prompts

**This makes utilitye2e-ai robust for both**:
- Simple static pages (like our mock)
- Complex SPAs (like router GUIs)
