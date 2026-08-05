from application.workflows import (
    build_selectable_elements,
    derive_login_url,
    discover_page,
)


def test_derive_login_url_prefers_explicit_url():
    assert (
        derive_login_url("https://example.test/t/acme/dashboard", "https://login.test")
        == "https://login.test"
    )


def test_derive_login_url_from_tenant_path():
    assert (
        derive_login_url("https://example.test/t/acme/dashboard")
        == "https://example.test/t/acme/login"
    )


def test_build_selectable_elements_filters_duplicates_and_skipped_labels():
    dom = {
        "buttons": [
            {"text": "新增", "context": "standalone"},
            {"text": "新增", "context": "standalone"},
            {"text": "Save", "context": "standalone"},
            {
                "text": "編輯",
                "context": "table-row",
                "rowIndex": 2,
                "rowLabel": "Alice",
            },
        ],
        "inputs": [
            {"label": "名稱", "tag": "input"},
            {"placeholder": "新增", "tag": "input"},
        ],
        "tableHeaders": ["狀態", "名稱"],
    }

    assert build_selectable_elements(dom) == [
        {"type": "button", "label": "新增", "text": "新增"},
        {
            "type": "button",
            "label": "編輯",
            "text": "編輯",
            "row": 2,
            "rowLabel": "Alice",
        },
        {"type": "input", "label": "名稱", "text": "input: 名稱"},
        {"type": "column", "label": "狀態", "text": "column: 狀態"},
    ]


def test_discover_page_uses_injected_crawler():
    calls = []

    def crawler(**kwargs):
        calls.append(kwargs)
        return {"title": "Demo", "buttons": [{"text": "新增"}]}

    result = discover_page(
        target_url="https://example.test/t/acme/home",
        username="user",
        password="pass",
        crawler=crawler,
    )

    assert calls == [
        {
            "url": "https://example.test/t/acme/home",
            "login_url": "https://example.test/t/acme/login",
            "username": "user",
            "password": "pass",
        }
    ]
    assert result.title == "Demo"
    assert result.elements == [{"type": "button", "label": "新增", "text": "新增"}]
