# Mock Admin Panel - Local Test Target

## Quick Start

```bash
# Start mock server (runs on port 3002)
cd /home/one/utilitye2e-ai
python3 mock_server.py

# Visit: http://localhost:3002
```

## Features

✓ CRUD operations (Create, Read, Update, Delete)
✓ Modal forms (Add/Edit)
✓ Table listing with pagination-ready structure
✓ Form validation (required fields)
✓ Delete confirmation dialog

## UI Patterns (for AI analysis)

| Element | Selector Pattern |
|---------|-----------------|
| Add button | `button[onclick="openModal()"]` |
| Edit button | `button[onclick="editParent({id})"]` |
| Delete button | `button[onclick="deleteParent({id})"]` |
| Form input | `input[name="field_name"]` |
| Save button | `button[type="submit"]` |
| Cancel button | `button[onclick="closeModal()"]` |
| Table row | `tr[data-id="{id}"]` |

## Test with utilitye2e-ai

Update your `config.yaml`:
```yaml
target:
  base_url: http://localhost:3002
  login_url: ""  # No auth needed for mock
```

Then run:
```bash
utilitye2e-ai analyze -d "測試家長管理的新增、編輯、刪除" -t parents
```
