"""Posture pack contract for manual unknown-risk review."""

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List

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
