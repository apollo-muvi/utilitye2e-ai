import json

from core.spec import TestSpec


def _spec_dict():
    return {
        "name": "Demo",
        "target": {"url": "https://example.test"},
        "steps": [
            {
                "button": "新增",
                "desc": "Create item",
                "fill_fields": [{"name": "name", "label": "名稱", "value": "測試"}],
            }
        ],
    }


def test_from_dict_does_not_mutate_input():
    data = _spec_dict()

    spec = TestSpec.from_dict(data)

    assert spec.steps[0].fill_fields[0].label == "名稱"
    assert data["steps"][0]["fill_fields"] == [
        {"name": "name", "label": "名稱", "value": "測試"}
    ]


def test_from_file_loads_json_spec(tmp_path):
    path = tmp_path / "spec.json"
    path.write_text(json.dumps(_spec_dict(), ensure_ascii=False), encoding="utf-8")

    spec = TestSpec.from_file(str(path))

    assert spec.name == "Demo"
    assert spec.target.url == "https://example.test"
    assert spec.steps[0].button == "新增"
