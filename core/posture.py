"""Posture pack contracts for manual unknown-risk review."""

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import yaml


@dataclass
class PostureCheck:
    id: str
    text: str
    category: str = ""
    automation_candidate: bool = False

    @classmethod
    def from_value(cls, value: Any, prefix: str, index: int) -> "PostureCheck":
        if isinstance(value, str):
            return cls(id=f"{prefix}-{index + 1}", text=value)
        return cls(
            id=value.get("id", f"{prefix}-{index + 1}"),
            text=value["text"],
            category=value.get("category", ""),
            automation_candidate=bool(value.get("automation_candidate", False)),
        )


@dataclass
class PostureWorkflow:
    id: str
    title: str
    role: str = ""
    entry_point: str = ""
    checks: List[PostureCheck] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PostureWorkflow":
        workflow_id = data["id"]
        checks = [
            PostureCheck.from_value(check, workflow_id, index)
            for index, check in enumerate(data.get("checks", []))
        ]
        return cls(
            id=workflow_id,
            title=data.get("title", workflow_id),
            role=data.get("role", ""),
            entry_point=data.get("entry_point", ""),
            checks=checks,
        )


@dataclass
class PostureInvariant:
    id: str
    text: str
    question: str = ""

    @classmethod
    def from_value(cls, value: Any, prefix: str, index: int) -> "PostureInvariant":
        if isinstance(value, str):
            return cls(id=f"{prefix}-{index + 1}", text=value)
        return cls(
            id=value.get("id", f"{prefix}-{index + 1}"),
            text=value["text"],
            question=value.get("question", ""),
        )


@dataclass
class PosturePack:
    product: str
    version: str = ""
    purpose: str = ""
    roles: List[str] = field(default_factory=list)
    workflows: List[PostureWorkflow] = field(default_factory=list)
    invariants: List[PostureInvariant] = field(default_factory=list)
    release_gate: List[str] = field(default_factory=list)
    finding_template: List[str] = field(default_factory=list)

    def validate(self) -> List[str]:
        errors = []
        if not self.product:
            errors.append("product is required")
        if not self.workflows:
            errors.append("at least one workflow is required")
        for workflow in self.workflows:
            if not workflow.checks:
                errors.append(
                    f"workflow[{workflow.id}]: at least one check is required"
                )
            for check in workflow.checks:
                if not check.text:
                    errors.append(
                        f"workflow[{workflow.id}].check[{check.id}]: text is required"
                    )
        return errors

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def find_workflow(self, workflow_id: str) -> PostureWorkflow:
        for workflow in self.workflows:
            if workflow.id == workflow_id:
                return workflow
        raise ValueError(f"unknown workflow id: {workflow_id}")

    def find_check(self, check_id: str) -> Tuple[PostureWorkflow, PostureCheck]:
        for workflow in self.workflows:
            for check in workflow.checks:
                if check.id == check_id:
                    return workflow, check
        raise ValueError(f"unknown check id: {check_id}")

    @classmethod
    def from_file(cls, path: str) -> "PosturePack":
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PosturePack":
        workflows = [
            PostureWorkflow.from_dict(workflow)
            for workflow in data.get("workflows", [])
        ]
        invariants = [
            PostureInvariant.from_value(invariant, "invariant", index)
            for index, invariant in enumerate(data.get("invariants", []))
        ]
        return cls(
            product=data.get("product", ""),
            version=data.get("version", ""),
            purpose=data.get("purpose", ""),
            roles=list(data.get("roles", [])),
            workflows=workflows,
            invariants=invariants,
            release_gate=list(data.get("release_gate", [])),
            finding_template=list(data.get("finding_template", [])),
        )


@dataclass
class PostureFinding:
    product: str
    finding: str
    workflow_id: str = ""
    check_id: str = ""
    check_text: str = ""
    category: str = ""
    user_impact: str = ""
    missing_expectation: str = ""
    should_be_automated: bool = False
    suggested_assertion: str = ""
    suggested_checklist_update: str = ""
    evidence: List[str] = field(default_factory=list)
    owner: str = ""
    status: str = "open"

    def validate(self) -> List[str]:
        errors = []
        if not self.product:
            errors.append("product is required")
        if not self.finding:
            errors.append("finding is required")
        return errors

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_yaml(self) -> str:
        return yaml.safe_dump(
            self.to_dict(),
            allow_unicode=True,
            sort_keys=False,
        )

    @classmethod
    def from_file(cls, path: str) -> "PostureFinding":
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PostureFinding":
        return cls(
            product=data.get("product", ""),
            finding=data.get("finding", ""),
            workflow_id=data.get("workflow_id", ""),
            check_id=data.get("check_id", ""),
            check_text=data.get("check_text", ""),
            category=data.get("category", ""),
            user_impact=data.get("user_impact", ""),
            missing_expectation=data.get("missing_expectation", ""),
            should_be_automated=bool(data.get("should_be_automated", False)),
            suggested_assertion=data.get("suggested_assertion", ""),
            suggested_checklist_update=data.get("suggested_checklist_update", ""),
            evidence=list(data.get("evidence", [])),
            owner=data.get("owner", ""),
            status=data.get("status", "open"),
        )


@dataclass
class PostureAssertionCandidate:
    product: str
    assertion: str
    source_finding: str
    workflow_id: str = ""
    check_id: str = ""
    assertion_type: str = "ui"
    priority: str = "medium"
    status: str = "candidate"
    user_impact: str = ""
    expected_behavior: str = ""
    evidence: List[str] = field(default_factory=list)

    def validate(self) -> List[str]:
        errors = []
        if not self.product:
            errors.append("product is required")
        if not self.assertion:
            errors.append("assertion is required")
        if not self.source_finding:
            errors.append("source_finding is required")
        return errors

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_yaml(self) -> str:
        return yaml.safe_dump(
            self.to_dict(),
            allow_unicode=True,
            sort_keys=False,
        )

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PostureAssertionCandidate":
        return cls(
            product=data.get("product", ""),
            assertion=data.get("assertion", ""),
            source_finding=data.get("source_finding", ""),
            workflow_id=data.get("workflow_id", ""),
            check_id=data.get("check_id", ""),
            assertion_type=data.get("assertion_type", "ui"),
            priority=data.get("priority", "medium"),
            status=data.get("status", "candidate"),
            user_impact=data.get("user_impact", ""),
            expected_behavior=data.get("expected_behavior", ""),
            evidence=list(data.get("evidence", [])),
        )


def init_posture_pack_from_dom(
    product: str,
    dom: Dict[str, Any],
    url: str = "",
) -> PosturePack:
    """Generate a starter posture pack from crawled DOM data.

    Classification is based on DOM source signals, NOT hardcoded labels:
      - navItems → high-confidence navigation → own workflow each
      - links    → medium-confidence → own workflow each
      - buttons  → low-confidence → grouped into a "REVIEW: buttons" workflow
                   so the user decides which are real navigation vs action buttons

    This works for any website without site-specific keyword lists.
    """
    import hashlib
    import re
    from urllib.parse import urljoin, urlparse

    def _slug(text: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
        if slug:
            return slug
        return hashlib.md5(text.encode("utf-8")).hexdigest()[:8]

    def _resolve_input_label(inp: Dict[str, Any]) -> str:
        """Get the best available label for an input, in priority order."""
        return (
            inp.get("label", "").strip()
            or inp.get("placeholder", "").strip()
            or inp.get("name", "").strip()
            or inp.get("id", "").strip()
        )

    # unique ID registry — ensures no collisions across workflows and checks
    _used_ids: set = set()

    def _unique_id(base: str) -> str:
        """Return base if unused, else append -2, -3, ... until unique."""
        candidate = base
        n = 2
        while candidate in _used_ids:
            candidate = f"{base}-{n}"
            n += 1
        _used_ids.add(candidate)
        return candidate

    def _clean_label(text: str) -> str:
        return text.strip()

    def _is_obvious_noise(text: str) -> bool:
        """Only universal structural noise — no site-specific words."""
        low = text.lower().strip()
        if not low:
            return True
        # pure version numbers / build hashes like "9.0.0.4.386_9794"
        if re.match(r"^[\d._-]+$", low):
            return True
        # empty after stripping whitespace-only chars
        if len(low) < 2:
            return True
        if re.search(r"\d+\.\d+(?:\.\d+)?", low) and re.search(
            r"\b(branch|build|version|r\d{4,}|[a-f0-9]{8,})\b", low
        ):
            return True
        return False

    def _is_action_or_session_label(text: str) -> bool:
        low = text.lower().strip()
        action_words = {
            "logout",
            "log out",
            "sign out",
            "reboot",
            "restart",
            "delete",
            "remove",
            "disconnect",
            "reset",
            "submit",
            "save",
            "apply",
            "cancel",
            "close",
            "登出",
            "重啟",
            "重新啟動",
            "刪除",
            "移除",
            "儲存",
            "套用",
            "取消",
            "關閉",
        }
        return low in action_words

    def _is_internal_navigation_href(href: str) -> bool:
        href = href.strip()
        if not href or href.startswith("#"):
            return False
        parsed_href = urlparse(href)
        if parsed_href.scheme and parsed_href.scheme not in {"http", "https"}:
            return False
        if not url:
            return True
        parsed_base = urlparse(url)
        absolute = urlparse(urljoin(url, href))
        if absolute.netloc and parsed_base.netloc:
            return absolute.netloc == parsed_base.netloc
        return True

    def _path_context_label(label: str, href: str) -> str:
        parsed = urlparse(urljoin(url or "http://local/", href))
        parts = [part for part in parsed.path.split("/") if part]
        if "admin" in parts:
            parts = parts[parts.index("admin") + 1 :]
        if len(parts) < 2:
            return label
        parent = parts[-2].replace("-", " ").replace("_", " ").title()
        if parent and parent.lower() not in label.lower():
            return f"{parent} / {label}"
        return label

    def _dedupe(items: List[Any], key: str) -> List[Dict[str, Any]]:
        seen = set()
        result = []
        for item in items:
            if isinstance(item, dict):
                val = item.get(key, "").strip()
            else:
                val = str(item).strip()
            if val and val not in seen:
                seen.add(val)
                result.append(item if isinstance(item, dict) else {key: val})
        return result

    def _make_nav_workflow(label: str) -> PostureWorkflow:
        slug = _unique_id(_slug(label))
        return PostureWorkflow(
            id=slug,
            title=label,
            role="User",
            entry_point=f"{label}",
            checks=[
                PostureCheck(
                    id=_unique_id(f"{slug}-page-loads"),
                    text=f'"{label}" loads without error',
                    category="navigation",
                ),
                PostureCheck(
                    id=_unique_id(f"{slug}-content-visible"),
                    text=f'"{label}" shows expected content',
                    category="status",
                ),
            ],
        )

    # ── classify by source confidence ──
    workflows: List[PostureWorkflow] = []

    # Tier 1: internal links with real hrefs. These are most useful on admin UIs
    # where menu markup may concatenate section names and child labels.
    link_labels: List[str] = []
    link_candidates = []
    seen_link_keys = set()
    for item in dom.get("links", []):
        if not isinstance(item, dict):
            continue
        text = _clean_label(item.get("text", ""))
        href = item.get("href", "")
        if not (text and 2 <= len(text) <= 60):
            continue
        if (
            _is_obvious_noise(text)
            or _is_action_or_session_label(text)
            or not _is_internal_navigation_href(href)
        ):
            continue
        key = (text.lower(), urlparse(urljoin(url or "http://local/", href)).path)
        if key in seen_link_keys:
            continue
        seen_link_keys.add(key)
        link_candidates.append({"text": text, "href": href})

    duplicate_link_texts = {}
    for item in link_candidates:
        key = item["text"].lower()
        duplicate_link_texts[key] = duplicate_link_texts.get(key, 0) + 1
    for item in link_candidates:
        text = item["text"]
        label = (
            _path_context_label(text, item["href"])
            if duplicate_link_texts[text.lower()] > 1
            else text
        )
        if label.lower() not in {existing.lower() for existing in link_labels}:
            link_labels.append(label)

    # Tier 2: navItems are a fallback for pages without usable links.
    nav_labels: List[str] = []
    if not link_labels:
        for item in _dedupe(dom.get("navItems", []), "text"):
            text = _clean_label(item.get("text", ""))
            if (
                text
                and 2 <= len(text) <= 40
                and not _is_obvious_noise(text)
                and not _is_action_or_session_label(text)
            ):
                nav_labels.append(text)

    # create workflows from high-confidence sources
    for label in (link_labels or nav_labels)[:25]:
        workflows.append(_make_nav_workflow(label))

    # Tier 3: buttons (low confidence — could be nav OR action buttons)
    # Group into a REVIEW workflow so the user triages them
    button_labels: List[str] = []
    for item in _dedupe(dom.get("buttons", []), "text"):
        text = _clean_label(item.get("text", ""))
        if text and 2 <= len(text) <= 40 and not _is_obvious_noise(text):
            if text.lower() not in {
                l.lower() for l in nav_labels + link_labels
            } and not _is_action_or_session_label(text):
                button_labels.append(text)

    if button_labels:
        review_checks = [
            PostureCheck(
                id=_unique_id(f"review-btn-{_slug(t)}"),
                text=f'"{t}" — Is this navigation or an action button? '
                f"Keep if it leads to a page; remove if it performs an action.",
                category="review",
            )
            for t in button_labels[:15]
        ]
        workflows.append(
            PostureWorkflow(
                id=_unique_id("review-buttons"),
                title="REVIEW: Buttons (triage needed)",
                role="User",
                entry_point="These buttons were found but could be navigation OR actions. "
                "Decide for each: keep as a workflow, or delete.",
                checks=review_checks,
            )
        )

    # Tier 4: form inputs — dedupe by resolved label (label → placeholder → name → id)
    raw_inputs = dom.get("inputs", [])
    seen_input_labels: set = set()
    inputs: List[Dict[str, Any]] = []
    for inp in raw_inputs:
        if not isinstance(inp, dict):
            continue
        label = _resolve_input_label(inp)
        if label and label.lower() not in seen_input_labels:
            seen_input_labels.add(label.lower())
            inputs.append({**inp, "_resolved_label": label})
    if inputs:
        form_checks: List[PostureCheck] = []
        for inp in inputs[:10]:
            label = inp.get("_resolved_label", "")
            if label:
                slug = _slug(label)
                form_checks.append(
                    PostureCheck(
                        id=_unique_id(f"form-{slug}-editable"),
                        text=f'"{label}" field is editable and accepts input',
                        category="form",
                    )
                )
        if form_checks:
            workflows.append(
                PostureWorkflow(
                    id=_unique_id("forms-and-inputs"),
                    title="Forms and Inputs",
                    role="User",
                    entry_point="Form fields discovered on the page",
                    checks=form_checks,
                )
            )

    # fallback: nothing discovered at all
    if not workflows:
        workflows.append(
            PostureWorkflow(
                id=_unique_id("page-overview"),
                title="Page Overview",
                role="User",
                entry_point=url or "Target URL",
                checks=[
                    PostureCheck(
                        id=_unique_id("page-loads"),
                        text="Page loads without error",
                        category="navigation",
                    ),
                    PostureCheck(
                        id=_unique_id("key-elements-present"),
                        text="Key interactive elements are present and visible",
                        category="status",
                    ),
                ],
            )
        )

    return PosturePack(
        product=product,
        version="auto-generated",
        purpose=f"Auto-generated posture review pack for {product}. "
        "Items marked REVIEW need human triage before use.",
        roles=["User"],
        workflows=workflows,
        invariants=[
            PostureInvariant(
                id="navigation-back-path",
                text="Back path sanity",
                question="After navigating to a page, can the user return without confusion?",
            ),
            PostureInvariant(
                id="error-recovery",
                text="Error recovery",
                question="Do error states offer a recoverable action?",
            ),
        ],
        release_gate=[
            "All REVIEW items triaged: kept as workflow or removed.",
            "All navigation items open without error.",
            "Forms accept input and submit/save works.",
            "No broken or empty pages.",
        ],
    )


def create_posture_finding(
    pack: PosturePack,
    finding: str,
    workflow_id: str = "",
    check_id: str = "",
    user_impact: str = "",
    missing_expectation: str = "",
    should_be_automated: Optional[bool] = None,
    suggested_assertion: str = "",
    suggested_checklist_update: str = "",
    evidence: Optional[List[str]] = None,
    owner: str = "",
    status: str = "open",
) -> PostureFinding:
    """Create a structured finding tied to a posture pack workflow/check."""
    check_text = ""
    category = ""
    inferred_automation = False

    if check_id:
        workflow, check = pack.find_check(check_id)
        if workflow_id and workflow_id != workflow.id:
            raise ValueError(
                f"check id {check_id} belongs to workflow {workflow.id}, not {workflow_id}"
            )
        workflow_id = workflow.id
        check_text = check.text
        category = check.category
        inferred_automation = check.automation_candidate
    elif workflow_id:
        pack.find_workflow(workflow_id)

    finding_record = PostureFinding(
        product=pack.product,
        finding=finding,
        workflow_id=workflow_id,
        check_id=check_id,
        check_text=check_text,
        category=category,
        user_impact=user_impact,
        missing_expectation=missing_expectation,
        should_be_automated=(
            inferred_automation
            if should_be_automated is None
            else bool(should_be_automated)
        ),
        suggested_assertion=suggested_assertion,
        suggested_checklist_update=suggested_checklist_update,
        evidence=evidence or [],
        owner=owner,
        status=status,
    )
    errors = finding_record.validate()
    if errors:
        raise ValueError("; ".join(errors))
    return finding_record


def promote_posture_finding(
    finding: PostureFinding,
    assertion: str = "",
    assertion_type: str = "ui",
    priority: str = "medium",
    force: bool = False,
) -> PostureAssertionCandidate:
    """Promote an automation-ready finding into an assertion candidate."""
    if not finding.should_be_automated and not force:
        raise ValueError(
            "finding is not marked as automation candidate; pass force=True to promote"
        )

    assertion_text = (
        assertion
        or finding.suggested_assertion
        or finding.missing_expectation
        or f"Verify: {finding.finding}"
    )
    candidate = PostureAssertionCandidate(
        product=finding.product,
        assertion=assertion_text,
        source_finding=finding.finding,
        workflow_id=finding.workflow_id,
        check_id=finding.check_id,
        assertion_type=assertion_type,
        priority=priority,
        user_impact=finding.user_impact,
        expected_behavior=finding.missing_expectation,
        evidence=list(finding.evidence),
    )
    errors = candidate.validate()
    if errors:
        raise ValueError("; ".join(errors))
    return candidate


def render_posture_markdown(pack: PosturePack) -> str:
    """Render a posture pack into a manual release worksheet."""
    lines = [f"# {pack.product} Posture Review Worksheet", ""]
    if pack.version:
        lines.extend([f"Version: {pack.version}", ""])
    if pack.purpose:
        lines.extend(["## Purpose", "", pack.purpose.strip(), ""])
    if pack.roles:
        lines.extend(["## Roles", ""])
        lines.extend(f"- [ ] {role}" for role in pack.roles)
        lines.append("")

    lines.extend(["## Workflows", ""])
    for workflow in pack.workflows:
        lines.extend([f"### {workflow.title}", ""])
        if workflow.role:
            lines.append(f"Role: {workflow.role}")
        if workflow.entry_point:
            lines.append(f"Entry point: {workflow.entry_point}")
        if workflow.role or workflow.entry_point:
            lines.append("")
        for check in workflow.checks:
            suffix = ""
            metadata = []
            if check.category:
                metadata.append(check.category)
            if check.automation_candidate:
                metadata.append("automation candidate")
            if metadata:
                suffix = f" ({', '.join(metadata)})"
            lines.append(f"- [ ] `{check.id}` {check.text}{suffix}")
        lines.append("")

    if pack.invariants:
        lines.extend(["## Cross-Screen Invariants", ""])
        for invariant in pack.invariants:
            question = f" — {invariant.question}" if invariant.question else ""
            lines.append(f"- [ ] `{invariant.id}` {invariant.text}{question}")
        lines.append("")

    if pack.release_gate:
        lines.extend(["## Release Gate", ""])
        lines.extend(f"- [ ] {item}" for item in pack.release_gate)
        lines.append("")

    if pack.finding_template:
        lines.extend(["## Finding Template", "", "```text"])
        lines.extend(f"{field}:" for field in pack.finding_template)
        lines.extend(["```", ""])

    return "\n".join(lines).rstrip() + "\n"
