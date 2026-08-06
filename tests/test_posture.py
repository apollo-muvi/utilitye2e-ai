import pytest

from application.workflows import (
    create_posture_finding_record,
    init_posture_pack,
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
    """init should create workflows from navItems and links, buttons go to REVIEW."""
    dom = {
        "navItems": [{"text": "Dashboard"}, {"text": "Settings"}],
        "links": [{"text": "Dashboard"}, {"text": "Profile"}],
        "buttons": [{"text": "Save"}],
        "inputs": [{"label": "Username"}, {"label": "Password"}],
    }
    pack = init_posture_pack_from_dom(product="TestApp", dom=dom, url="http://x")
    assert pack.product == "TestApp"
    titles = [w.title for w in pack.workflows]
    # navItems become workflows
    assert "Dashboard" in titles
    assert "Settings" in titles
    # links deduped against navItems, new ones become workflows
    assert "Profile" in titles
    # buttons go to REVIEW, not their own workflows
    review_wf = [w for w in pack.workflows if w.id == "review-buttons"]
    assert len(review_wf) == 1
    assert any("Save" in c.text for c in review_wf[0].checks)
    # form inputs become their own workflow
    form_wf = [w for w in pack.workflows if w.id == "forms-and-inputs"]
    assert len(form_wf) == 1
    assert any("Username" in c.text for c in form_wf[0].checks)
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
    """CJK nav labels should produce unique hashed IDs."""
    dom = {
        "navItems": [
            {"text": "教師"}, {"text": "家長"}, {"text": "管理"},
        ],
    }
    pack = init_posture_pack_from_dom(product="CJKApp", dom=dom, url="http://x")
    ids = [w.id for w in pack.workflows if w.id != "forms-and-inputs"]
    assert len(ids) == len(set(ids)), f"duplicate IDs: {ids}"
    assert all(w.id != "item" for w in pack.workflows), "fallback 'item' slug leaked"
    errors = pack.validate()
    assert errors == []


def test_init_posture_pack_no_hardcoded_noise():
    """init must NOT filter by hardcoded labels — version numbers only."""
    dom = {
        "navItems": [
            {"text": "Logout"}, {"text": "9.0.0.4.386_9794"},
            {"text": "Dashboard"},
        ],
        "buttons": [{"text": "Save"}, {"text": "Delete"}],
    }
    pack = init_posture_pack_from_dom(product="NoHardcode", dom=dom, url="http://x")
    nav_titles = [w.title for w in pack.workflows if w.id != "review-buttons"]
    # Logout is a valid navItem source — must NOT be hardcoded-filtered
    assert "Logout" in nav_titles, "Logout was hardcoded-filtered (shouldn't be)"
    # pure version numbers ARE filtered (structural noise)
    assert "9.0.0.4.386_9794" not in nav_titles
    # buttons go to REVIEW regardless of their text
    review = [w for w in pack.workflows if "review" in w.id]
    assert len(review) == 1
    review_texts = " ".join(c.text for c in review[0].checks)
    assert "Save" in review_texts


def test_init_posture_pack_placeholder_name_inputs():
    """Inputs with only placeholder/name (no label) must not be silently dropped."""
    dom = {
        "inputs": [
            {"placeholder": "Email"},
            {"name": "password"},
            {"id": "search-box"},
        ],
    }
    pack = init_posture_pack_from_dom(product="FormApp", dom=dom, url="http://x")
    form_wf = [w for w in pack.workflows if "forms" in w.id]
    assert len(form_wf) == 1, "form workflow missing"
    texts = " ".join(c.text for c in form_wf[0].checks)
    assert "Email" in texts, "placeholder-only input dropped"
    assert "password" in texts, "name-only input dropped"
    assert "search-box" in texts, "id-only input dropped"


def test_init_posture_pack_no_duplicate_ids():
    """Labels that slug identically must produce unique workflow and check IDs."""
    dom = {
        "navItems": [
            {"text": "Settings"},
            {"text": "settings"},
            {"text": "Settings!"},
        ],
    }
    pack = init_posture_pack_from_dom(product="SlugApp", dom=dom, url="http://x")
    all_ids = []
    for w in pack.workflows:
        all_ids.append(w.id)
        all_ids.extend(c.id for c in w.checks)
    assert len(all_ids) == len(set(all_ids)), f"duplicate IDs: {all_ids}"


def test_init_posture_pack_thin_crawl_warning():
    """init_posture_pack should warn when crawl yields very few elements."""
    from application.workflows import init_posture_pack
    from unittest.mock import patch

    thin_dom = {
        "buttons": [{"text": "Log in"}],
        "inputs": [{"placeholder": "Username"}, {"placeholder": "Password"}],
    }

    with patch("application.workflows.discover_page") as mock_discover:
        from application.workflows import DiscoveryResult
        mock_discover.return_value = DiscoveryResult(
            elements=[], title="Login", dom=thin_dom,
        )
        pack, warnings = init_posture_pack(
            product="Router",
            url="http://192.168.1.1",
            username="admin",
            password="admin",
        )
    assert len(warnings) > 0
    assert any("few elements" in w.lower() or "login" in w.lower() for w in warnings)


def test_init_posture_pack_rich_crawl_no_warning():
    """init_posture_pack should NOT warn when crawl yields plenty of elements."""
    from application.workflows import init_posture_pack
    from unittest.mock import patch

    rich_dom = {
        "navItems": [{"text": "Dashboard"}, {"text": "Settings"}, {"text": "Profile"}],
        "links": [{"text": "Help"}, {"text": "About"}],
        "buttons": [{"text": "Save"}, {"text": "Cancel"}],
        "inputs": [{"label": "Name"}, {"label": "Email"}],
    }

    with patch("application.workflows.discover_page") as mock_discover:
        from application.workflows import DiscoveryResult
        mock_discover.return_value = DiscoveryResult(
            elements=[], title="Dashboard", dom=rich_dom,
        )
        pack, warnings = init_posture_pack(
            product="App",
            url="http://localhost:3001",
            username="admin",
            password="admin",
        )
    assert warnings == [], f"unexpected warnings: {warnings}"
