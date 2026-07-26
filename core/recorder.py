"""
Recorder — test result recorder.

Collects pass/fail/skip results and mutations during test execution.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional


@dataclass
class TestResult:
    name: str
    status: str          # pass | fail | skip
    detail: str = ""
    screenshot: Optional[str] = None


@dataclass
class Recorder:
    results: List[TestResult] = field(default_factory=list)
    mutations: List[Dict] = field(default_factory=list)

    def pass_(self, name: str, detail: str = "") -> None:
        self.results.append(TestResult(name, "pass", detail))

    def fail(self, name: str, detail: str = "", screenshot: str = "") -> None:
        self.results.append(TestResult(name, "fail", detail, screenshot))

    def skip(self, name: str, detail: str = "") -> None:
        self.results.append(TestResult(name, "skip", detail))

    def record_mutation(self, data: Dict) -> None:
        self.mutations.append(data)

    @property
    def passed(self) -> int:
        return sum(1 for r in self.results if r.status == "pass")

    @property
    def failed(self) -> int:
        return sum(1 for r in self.results if r.status == "fail")

    @property
    def skipped(self) -> int:
        return sum(1 for r in self.results if r.status == "skip")

    def summary(self) -> Dict:
        return {
            "total": len(self.results),
            "passed": self.passed,
            "failed": self.failed,
            "skipped": self.skipped,
            "mutations": len(self.mutations),
            "results": [{"label": r.name, "status": r.status, "detail": r.detail} for r in self.results],
        }
