import pytest

from application.workflows import (
    create_posture_finding_record,
    list_posture_finding_records,
    promote_posture_finding_record,
    render_posture_pack,
)
from core.posture import (
    PosturePack,
    create_posture_finding,
    init_posture_pack_from_dom,
    promote_posture_finding,
    render_posture_markdown,
)


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


def test_create_posture_finding_infers_check_context():
    pack = PosturePack.from_dict(_pack_dict())

    finding = create_posture_finding(
        pack=pack,
        check_id="multi-image-browse",
        finding="Image opens but cannot browse to the next image.",
        user_impact="Parent cannot inspect all attachments from detail view.",
    )

    assert finding.product == "ClassHub"
    assert finding.workflow_id == "parent-images"
    assert finding.check_text == "Multiple images support browsing."
    assert finding.category == "ux expectation"
    assert finding.should_be_automated is True


def test_create_posture_finding_can_override_automation_candidate():
    pack = PosturePack.from_dict(_pack_dict())

    finding = create_posture_finding(
        pack=pack,
        check_id="multi-image-browse",
        finding="Product decision needed before automation.",
        should_be_automated=False,
    )

    assert finding.should_be_automated is False


def test_create_posture_finding_rejects_unknown_check_id():
    pack = PosturePack.from_dict(_pack_dict())

    with pytest.raises(ValueError, match="unknown check id: missing-check"):
        create_posture_finding(pack=pack, check_id="missing-check", finding="Bug")


def test_create_posture_finding_rejects_mismatched_workflow_id():
    pack = PosturePack.from_dict(_pack_dict())

    with pytest.raises(
        ValueError,
        match="check id multi-image-browse belongs to workflow parent-images",
    ):
        create_posture_finding(
            pack=pack,
            workflow_id="other-workflow",
            check_id="multi-image-browse",
            finding="Bug",
        )


def test_create_posture_finding_record_loads_yaml_file(tmp_path):
    path = tmp_path / "pack.yaml"
    path.write_text(
        """
product: Demo
workflows:
  - id: smoke
    title: Smoke
    checks:
      - id: smoke-check
        text: Check the workflow.
""".strip(),
        encoding="utf-8",
    )

    finding = create_posture_finding_record(
        pack_path=str(path),
        check_id="smoke-check",
        finding="Workflow has an unclear empty state.",
        suggested_assertion="Empty state includes recovery action.",
        evidence=["screenshot.png"],
    )

    assert finding.workflow_id == "smoke"
    assert finding.evidence == ["screenshot.png"]
    assert "suggested_assertion: Empty state" in finding.to_yaml()


def test_list_posture_finding_records_loads_and_filters_directory(tmp_path):
    open_finding = create_posture_finding(
        pack=PosturePack.from_dict(_pack_dict()),
        check_id="multi-image-browse",
        finding="Image cannot browse multiple attachments.",
    )
    closed_finding = create_posture_finding(
        pack=PosturePack.from_dict(_pack_dict()),
        workflow_id="parent-images",
        finding="Empty state is unclear.",
        status="closed",
        should_be_automated=False,
    )
    (tmp_path / "open.yaml").write_text(open_finding.to_yaml(), encoding="utf-8")
    (tmp_path / "closed.yml").write_text(closed_finding.to_yaml(), encoding="utf-8")

    findings = list_posture_finding_records(str(tmp_path))

    assert [finding.finding for finding in findings] == [
        "Empty state is unclear.",
        "Image cannot browse multiple attachments.",
    ]
    assert [
        finding.finding
        for finding in list_posture_finding_records(str(tmp_path), status="open")
    ] == ["Image cannot browse multiple attachments."]
    assert [
        finding.finding
        for finding in list_posture_finding_records(
            str(tmp_path), automation_candidates=True
        )
    ] == ["Image cannot browse multiple attachments."]


def test_list_posture_finding_records_can_read_single_file(tmp_path):
    finding = create_posture_finding(
        pack=PosturePack.from_dict(_pack_dict()),
        workflow_id="parent-images",
        finding="Single file finding.",
    )
    path = tmp_path / "finding.yaml"
    path.write_text(finding.to_yaml(), encoding="utf-8")

    findings = list_posture_finding_records(str(path))

    assert len(findings) == 1
    assert findings[0].finding == "Single file finding."


def test_promote_posture_finding_uses_suggested_assertion():
    finding = create_posture_finding(
        pack=PosturePack.from_dict(_pack_dict()),
        check_id="multi-image-browse",
        finding="Image cannot browse multiple attachments.",
        missing_expectation="Multiple images can be browsed.",
        suggested_assertion="Verify image viewer exposes next navigation.",
        evidence=["image-viewer.png"],
    )

    candidate = promote_posture_finding(finding)

    assert candidate.product == "ClassHub"
    assert candidate.assertion == "Verify image viewer exposes next navigation."
    assert candidate.source_finding == "Image cannot browse multiple attachments."
    assert candidate.workflow_id == "parent-images"
    assert candidate.check_id == "multi-image-browse"
    assert candidate.expected_behavior == "Multiple images can be browsed."
    assert candidate.evidence == ["image-viewer.png"]


def test_promote_posture_finding_requires_automation_candidate_without_force():
    finding = create_posture_finding(
        pack=PosturePack.from_dict(_pack_dict()),
        workflow_id="parent-images",
        finding="Back path is confusing.",
        should_be_automated=False,
    )

    with pytest.raises(ValueError, match="not marked as automation candidate"):
        promote_posture_finding(finding)

    candidate = promote_posture_finding(finding, force=True)

    assert candidate.assertion == "Verify: Back path is confusing."


def test_promote_posture_finding_record_loads_yaml_file(tmp_path):
    finding = create_posture_finding(
        pack=PosturePack.from_dict(_pack_dict()),
        check_id="multi-image-browse",
        finding="Image cannot browse multiple attachments.",
    )
    path = tmp_path / "finding.yaml"
    path.write_text(finding.to_yaml(), encoding="utf-8")

    candidate = promote_posture_finding_record(
        finding_path=str(path),
        assertion="Verify gallery navigation exists.",
        assertion_type="ui",
        priority="high",
    )

    assert candidate.assertion == "Verify gallery navigation exists."
    assert candidate.priority == "high"
    assert "source_finding: Image cannot browse" in candidate.to_yaml()


def test_init_posture_pack_from_nav_dom():
    """init should create workflows from navItems and links."""
    dom = {
        "navItems": [{"text": "Dashboard"}, {"text": "Settings"}],
        "links": [{"text": "Dashboard"}, {"text": "Profile"}],
        "buttons": [{"text": "Save"}],
        "inputs": [{"label": "Username"}, {"label": "Password"}],
    }
    pack = init_posture_pack_from_dom(product="TestApp", dom=dom, url="http://x")
    assert pack.product == "TestApp"
    # Dashboard deduped across navItems + links, so: Dashboard, Settings, Profile
    titles = [w.title for w in pack.workflows if w.id != "forms-and-buttons"]
    assert "Dashboard" in titles
    assert "Settings" in titles
    assert "Profile" in titles
    # form workflow should exist
    form_wf = [w for w in pack.workflows if w.id == "forms-and-buttons"]
    assert len(form_wf) == 1
    form_checks = form_wf[0].checks
    assert any("Username" in c.text for c in form_checks)
    assert any("Save" in c.text for c in form_checks)
    errors = pack.validate()
    assert errors == []


def test_init_posture_pack_empty_dom():
    """init with empty DOM should still produce a valid generic pack."""
    pack = init_posture_pack_from_dom(product="EmptyApp", dom={}, url="http://x")
    assert pack.product == "EmptyApp"
    assert len(pack.workflows) >= 1
    errors = pack.validate()
    assert errors == []


def test_init_posture_pack_cjk_unique_ids():
    """CJK nav labels should produce unique hashed IDs, not all 'item'."""
    dom = {
        "navItems": [
            {"text": "教師"}, {"text": "家長"}, {"text": "管理"},
        ],
    }
    pack = init_posture_pack_from_dom(product="CJKApp", dom=dom, url="http://x")
    ids = [w.id for w in pack.workflows if w.id != "forms-and-buttons"]
    assert len(ids) == len(set(ids)), f"duplicate IDs: {ids}"
    assert all(w.id != "item" for w in pack.workflows), "fallback 'item' slug leaked"
    errors = pack.validate()
    assert errors == []
