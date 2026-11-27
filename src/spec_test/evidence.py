"""Versioned receipts from verification backends; receipts are not attestations."""

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

KINDS = {"test", "property", "implementation-proof", "model-proof"}
STATUSES = {"passed", "failed", "skipped", "unknown"}


@dataclass(frozen=True)
class Evidence:
    spec_id: str
    kind: str
    runner: str
    name: str
    status: str
    details: object = None

    @property
    def key(self) -> tuple[str, str, str, str]:
        return (self.spec_id, self.kind, self.runner, self.name)


def load_evidence(path: Path) -> list[Evidence]:
    """Read a trusted runner's local receipt. Malformed or empty input is not green."""
    record = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(record, dict)
        or type(record.get("schema_version")) is not int
        or record["schema_version"] != 1
        or not isinstance(record.get("checks"), list)
        or not record["checks"]
    ):
        raise ValueError(f"{path}: expected nonempty evidence schema version 1")
    checks = []
    for row in record["checks"]:
        fields = ("spec_id", "kind", "runner", "name", "status")
        if not isinstance(row, dict) or any(
            not isinstance(row.get(field), str) or not row[field].strip() for field in fields
        ):
            raise ValueError(f"{path}: invalid evidence check")
        if (
            not re.fullmatch(r"[A-Z][A-Z0-9]*-\d+", row["spec_id"])
            or row["kind"] not in KINDS
            or row["status"] not in STATUSES
        ):
            raise ValueError(f"{path}: invalid spec ID, evidence kind or check status")
        checks.append(Evidence(*(row[field] for field in fields), details=row.get("details")))
    require_unique(checks)
    return checks


def require_unique(checks: list[Evidence]) -> None:
    seen = set()
    for check in checks:
        if check.key in seen:
            raise ValueError(f"Duplicate evidence: {check.key}")
        seen.add(check.key)


def write_evidence(path: Path, checks: list[Evidence]) -> None:
    require_unique(checks)
    path.write_text(
        json.dumps({"schema_version": 1, "checks": [asdict(c) for c in checks]}, indent=2)
        + "\n",
        encoding="utf-8",
    )
