"""
TestSpec — the central contract.

AI generates it, humans edit it, the runner executes it.
Serializable to JSON for save/share/version-control.
"""

import json
from dataclasses import dataclass, field, asdict
from typing import List, Optional


@dataclass
class FieldSpec:
    name: str
    label: str = ""
    selector: str = ""
    value: str = ""
    field_type: str = "text"
    required: bool = False
    options: List[str] = field(default_factory=list)


@dataclass
class TestStep:
    button: str = ""       # Button text to click
    desc: str = ""         # Human-readable description
    fill_fields: List[FieldSpec] = field(default_factory=list)

    def validate(self) -> List[str]:
        errs = []
        if not self.button:
            errs.append("step.button is required")
        return errs


@dataclass
class TargetSpec:
    url: str
    login_url: str = ""
    username: str = ""
    password: str = ""


@dataclass
class TestSpec:
    name: str
    target: TargetSpec
    table: str = ""
    steps: List[TestStep] = field(default_factory=list)
    fields: List[FieldSpec] = field(default_factory=list)

    def validate(self) -> List[str]:
        errs = []
        if not self.name:
            errs.append("name is required")
        if not self.target.url:
            errs.append("target.url is required")
        for i, s in enumerate(self.steps):
            for e in s.validate():
                errs.append(f"step[{i}]: {e}")
        return errs

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self, indent=2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_dict(cls, d: dict) -> "TestSpec":
        target = TargetSpec(**d.get("target", {}))
        fields_ = [FieldSpec(**f) for f in d.get("fields", [])]
        steps_raw = d.get("steps", [])
        steps = []
        for s in steps_raw:
            fill = [FieldSpec(**f) for f in s.pop("fill_fields", [])]
            steps.append(TestStep(**s, fill_fields=fill))
        return cls(name=d["name"], target=target, table=d.get("table",""), steps=steps, fields=fields_)
