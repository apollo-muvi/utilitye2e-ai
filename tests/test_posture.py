import pytest

from application.workflows import render_posture_pack
from core.posture import PosturePack, render_posture_markdown


def _pack_dict():
    return {
        "product": "ClassHub",
        "version": "2026-08-06",
        "purpose": "Review missing assertions.",
        "roles": ["Parent", "Teacher"],
        "workflows": [
            {
                "id": "parent-images",
                "title": "Parent images",
                "role": "Parent",
                "entry_point": "Contact book detail",
                "checks": [
                    "Single image opens.",
                    {
                        "id": "multi-image-browse",
                        "text": "Multiple images support browsing.",
                        "category": "ux expectation",
                        "automation_candidate": True,
                    },
                ],
            }
        ],
        "invariants": [
            {
                "id": "same-date",
                "text": "Same record, same date logic",
                "question": "Do list and detail match?",
            }
        ],
        "release_gate": ["Known-risk suite passes."],
        "finding_template": ["Finding", "Suggested assertion"],
    }


def test_posture_pack_from_dict_accepts_string_and_object_checks():
    pack = PosturePack.from_dict(_pack_dict())

    assert pack.product == "ClassHub"
    assert pack.workflows[0].checks[0].id == "parent-images-1"
    assert pack.workflows[0].checks[0].text == "Single image opens."
    assert pack.workflows[0].checks[1].id == "multi-image-browse"
    assert pack.workflows[0].checks[1].automation_candidate is True
    assert pack.validate() == []


def test_render_posture_markdown_includes_workflows_and_metadata():
    markdown = render_posture_markdown(PosturePack.from_dict(_pack_dict()))

    assert "# ClassHub Posture Review Worksheet" in markdown
    assert "- [ ] Parent" in markdown
    assert "### Parent images" in markdown
    assert "`multi-image-browse` Multiple images support browsing." in markdown
    assert "(ux expectation, automation candidate)" in markdown
    assert "`same-date` Same record, same date logic" in markdown
    assert "Finding:" in markdown


def test_render_posture_pack_validates_required_fields(tmp_path):
    path = tmp_path / "pack.yaml"
    path.write_text("product: Demo\nworkflows: []\n", encoding="utf-8")

    with pytest.raises(ValueError, match="at least one workflow is required"):
        render_posture_pack(str(path))


def test_render_posture_pack_loads_yaml_file(tmp_path):
    path = tmp_path / "pack.yaml"
    path.write_text(
        """
product: Demo
workflows:
  - id: smoke
    title: Smoke
    checks:
      - Check the workflow.
""".strip(),
        encoding="utf-8",
    )

    assert "`smoke-1` Check the workflow." in render_posture_pack(str(path))
