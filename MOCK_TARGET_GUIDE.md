# Universal Mock Admin Panel - Complete

## Three Core Pages (Domain-Independent)

| Page | URL | Purpose | Field Types | Actions |
|------|-----|---------|-------------|---------|
| **Users** | `/` or `/page/users` | User management CRUD | Text, Email, Select, Status toggle | Add, Edit, Delete, Toggle status |
| **Settings** | `/page/settings` | System configuration | Text, Number, Checkbox, Textarea | Save, Reset |
| **Logs** | `/page/logs` | System logs (read-only) | Read-only table | Filter by type |

---

## Field Types Covered

| Type | Where Used | Example |
|------|-----------|---------|
| **Text** | All pages | Username, Email, Site name |
| **Email** | Users | Email input |
| **Select (single)** | Users, Logs | Role dropdown, Log type filter |
| **Number** | Settings | Max users, Session timeout |
| **Checkbox/Toggle** | Settings | Enable registration |
| **Textarea** | Settings (future) | Allowed IPs |
| **Status Badge** | Users, Logs | Active/Inactive, Success/Failed |
| **Date/Time** | Logs | Timestamp display |

---

## Action Types for TestSpec

```python
VALID_ACTIONS = [
    # Users page
    "page_load",        # Verify page loads
    "add_cancel",       # Open user modal, cancel, no save
    "add_save",         # Add user, verify in table
    "edit_cancel",      # Edit user, cancel, original preserved
    "edit_save",        # Edit user, verify updated
    "delete",           # Delete user, confirm removal
    "toggle_status",    # Toggle active/inactive

    # Settings page
    "save_settings",    # Save form changes
    "reset_settings",   # Reset to defaults

    # Logs page
    "filter_logs",      # Filter by action type
    "view_logs",        # View log entries (read-only)
]
```

---

## UI Patterns (for AI Analysis)

### Common Elements

| Element | Selector Pattern | Pages |
|---------|-----------------|-------|
| Navigation | `.sidebar .nav-item` | All |
| Add button | `button:has-text("Add User")` | Users |
| Edit button | `button:has-text("Edit")` | Users |
| Delete button | `button:has-text("Delete")` | Users |
| Save button | `button:has-text("Save")` | Settings |
| Cancel button | `button:has-text("Cancel")` | Users modal |
| Table rows | `tbody tr` | Users, Logs |
| Form inputs | `input[name="field_name"]` | All |
| Select dropdowns | `select[name="field_name"]` | All |
| Toggle switch | `.toggle input[type="checkbox"]` | Settings |

### Page-Specific Patterns

**Users Page:**
```css
/* User table row */
#users-table tbody tr[data-id="{id}"]

/* User status toggle */
button:has-text("Toggle")

/* User modal */
#user-modal
```

**Settings Page:**
```css
/* Settings form */
#settings-form

/* Form sections */
.form-section

/* Save/Reset buttons */
button:has-text("Save Changes")
button:has-text("Reset")
```

**Logs Page:**
```css
/* Logs table */
#logs-table tbody tr

/* Filter dropdown */
#log-filter
```

---

## API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/users` | List users |
| POST | `/api/users` | Create user |
| PUT | `/api/users/{id}` | Update user |
| DELETE | `/api/users/{id}` | Delete user |
| POST | `/api/users/{id}/toggle` | Toggle status |
| GET | `/api/settings` | Get settings |
| POST | `/api/settings` | Save settings |
| GET | `/api/logs` | List logs (with ?type= filter) |

---

## Quick Start

```bash
# Start mock server
cd /home/one/utilitye2e-ai
python3 mock_server.py

# Visit pages
# Users:     http://localhost:3002/
# Settings:  http://localhost:3002/page/settings
# Logs:      http://localhost:3002/page/logs
```

---

## What This Achieves

✓ **Universal patterns** - Works for any admin panel (router, SaaS, CMS)
✓ **Field type coverage** - 8+ input types
✓ **Action variety** - CRUD + read-only + filters + toggles
✓ **Domain-independent** - No TutorBot dependencies
✓ **Realistic UI** - Sidebar navigation, modals, status badges

---

## Testing utilitye2e-ai

### Test 1: Users CRUD
```bash
cd /home/one/utilitye2e-ai
/home/one/utilitye2e/venv/bin/python3 -c "
from ai.analyzer import Analyzer
from adapters.llm import create_llm_adapter
from adapters.schema import create_schema_adapter
from config import load_config

cfg = load_config()
analyzer = Analyzer(create_llm_adapter(cfg['llm']), create_schema_adapter(cfg['schema']))
spec = analyzer.generate(
    '測試用戶管理的新增、編輯、刪除和狀態切換',
    'users',
    'http://localhost:3002/'
)
print(spec.to_json())
"
```

### Test 2: Settings Form
```bash
# Test settings save action
```

### Test 3: Logs Filter
```bash
# Test log filtering
```
