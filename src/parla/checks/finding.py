"""One reported problem. See `specs/checks.md#finding`."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Severity = Literal["error", "warning", "probe", "resolved"]


@dataclass(frozen=True)
class Finding:
    file: str  # relative to parla/
    line: int
    severity: Severity
    id: str
    message: str

    def format(self) -> str:
        return f"{self.file}:{self.line}: {self.severity} {self.id}: {self.message}"


class CheckFailed(Exception):
    """A check reported an error finding; nothing was built."""

    def __init__(self, findings: list[Finding]):
        self.findings = findings
        super().__init__("\n".join(f.format() for f in findings if f.severity == "error"))
