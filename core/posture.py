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

    Groups navigation items into workflows and generates generic checks
    for each (page-loads, key-elements-present).  The user is expected to
    refine the generated pack — this just removes the blank-page problem.
    """
    import re

    import hashlib

    def _slug(text: str) -> str:
        """Slug that handles CJK by hashing when no ascii remains."""
        slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
        if slug:
            return slug
        # CJK or other non-ascii: hash for uniqueness
        return hashlib.md5(text.encode("utf-8")).hexdigest()[:8]

    def _dedupe(items: List[Dict[str, Any]], key: str) -> List[Dict[str, Any]]:
        seen = set()
        result = []
        for item in items:
            val = item.get(key, "").strip()
            if val and val not in seen:
                seen.add(val)
                result.append(item)
        return result

    # --- collect candidate nav labels from multiple DOM sources ---
    # skip obvious utility / footer / header noise
    NOISE_LABELS = {
        "logout", "sign out", "signout", "login", "sign in", "signin",
        "reboot", "cancel", "ok", "apply", "save", "delete", "edit",
        "close", "back", "next", "previous", "submit", "reset",
        "home", "help", "support", "faq", "feedback",
        "manual", "utility", "product registration",
        "english", "繁體中文", "简体中文", "日本語",
        "on", "off", "go", "yes", "no",
        # action buttons commonly mistaken for navigation
        "新增", "建立", "刪除", "修改", "編輯", "儲存", "取消",
        "確認", "送出", "載入", "匯出", "匯入", "搜尋",
        "發布", "publish", "create", "update", "remove",
        "建立家長並產生邀請碼", "重新產生邀請碼",
        "邀請班級內全部家長", "匯出文字備份", "刪除選取",
        "顯示密碼", "choose files", "no file chosen",
    }

    def _is_noise(text: str) -> bool:
        low = text.lower().strip()
        if low in NOISE_LABELS:
            return True
        # pure version numbers like "9.0.0.4.386_9794"
        if re.match(r"^[\d._]+$", low):
            return True
        return False

    nav_labels: List[str] = []
    for source_key in ("navItems", "links"):
        for item in dom.get(source_key, []):
            if isinstance(item, dict):
                text = item.get("text", "").strip()
            else:
                text = str(item).strip()
            if text and 2 <= len(text) <= 40 and not _is_noise(text):
                nav_labels.append(text)

    # fall back to buttons if no nav items found
    if not nav_labels:
        for btn in dom.get("buttons", []):
            text = btn.get("text", "").strip() if isinstance(btn, dict) else ""
            if text and 2 <= len(text) <= 30 and not _is_noise(text):
                nav_labels.append(text)

    # dedupe preserving order
    seen_labels = set()
    unique_labels = []
    for label in nav_labels:
        key = label.lower()
        if key not in seen_labels:
            seen_labels.add(key)
            unique_labels.append(label)

    # --- build workflows ---
    workflows: List[PostureWorkflow] = []
    if unique_labels:
        for label in unique_labels[:20]:  # cap at 20 to keep pack manageable
            slug = _slug(label)
            workflow = PostureWorkflow(
                id=f"{slug}",
                title=label,
                role="User",
                entry_point=f"{label} menu item",
                checks=[
                    PostureCheck(
                        id=f"{slug}-page-loads",
                        text=f'"{label}" page loads without error',
                        category="navigation",
                    ),
                    PostureCheck(
                        id=f"{slug}-content-visible",
                        text=f'"{label}" page shows expected content',
                        category="status",
                    ),
                ],
            )
            workflows.append(workflow)
    else:
        # no navigation discovered — create a single generic workflow
        workflows.append(
            PostureWorkflow(
                id="page-overview",
                title="Page Overview",
                role="User",
                entry_point=url or "Target URL",
                checks=[
                    PostureCheck(
                        id="page-loads",
                        text="Page loads without error",
                        category="navigation",
                    ),
                    PostureCheck(
                        id="key-elements-present",
                        text="Key interactive elements are present and visible",
                        category="status",
                    ),
                ],
            )
        )

    # --- add a form-checks workflow if inputs/buttons exist ---
    inputs = _dedupe(dom.get("inputs", []), "label")
    buttons = _dedupe(dom.get("buttons", []), "text")
    if inputs or buttons:
        form_checks: List[PostureCheck] = []
        for inp in inputs[:8]:
            label = inp.get("label") or inp.get("placeholder") or inp.get("name") or ""
            if label:
                slug = _slug(label)
                form_checks.append(
                    PostureCheck(
                        id=f"form-{slug}-editable",
                        text=f'"{label}" field is editable and accepts input',
                        category="form",
                    )
                )
        for btn in buttons[:6]:
            text = btn.get("text", "").strip() if isinstance(btn, dict) else ""
            if text:
                slug = _slug(text)
                form_checks.append(
                    PostureCheck(
                        id=f"btn-{slug}-works",
                        text=f'"{text}" button responds when clicked',
                        category="form",
                        automation_candidate=True,
                    )
                )
        if form_checks:
            workflows.append(
                PostureWorkflow(
                    id="forms-and-buttons",
                    title="Forms and Buttons",
                    role="User",
                    entry_point="Any page with form fields or action buttons",
                    checks=form_checks,
                )
            )

    return PosturePack(
        product=product,
        version="auto-generated",
        purpose=f"Auto-generated posture review pack for {product}. "
        "Refine workflows and checks before use.",
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
