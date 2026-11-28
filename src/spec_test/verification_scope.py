"""Explicit scope decisions; they do not change any verification result."""

import tomllib
from pathlib import Path

from .types import SpecStatus, VerificationReport


def reviewed_gaps(path: Path, report: VerificationReport) -> dict[str, str]:
    """Validate declarations against the whole report, not an ID-filtered run.

    Only a missing-evidence requirement can be deferred here. A failure or
    inconclusive run must still block; a passing row must leave the gap list.
    """
    with path.open("rb") as stream:
        data = tomllib.load(stream)
    if (
        set(data) != {"schema_version", "deferred"}
        or type(data["schema_version"]) is not int
        or data["schema_version"] != 1
        or not isinstance(data["deferred"], list)
    ):
        raise ValueError(f"{path}: expected schema_version = 1 and a deferred list")
    by_id = {result.spec.id: result for result in report.results}
    if not by_id or len(by_id) != len(report.results):
        raise ValueError(f"{path}: scoped verification requires nonempty, unique requirement IDs")

    gaps: dict[str, str] = {}
    for row in data["deferred"]:
        if (
            not isinstance(row, dict)
            or set(row) != {"ids", "reason"}
            or not isinstance(row["reason"], str)
            or not row["reason"].strip()
            or not isinstance(row["ids"], list)
            or not row["ids"]
            or any(not isinstance(spec_id, str) for spec_id in row["ids"])
        ):
            raise ValueError(f"{path}: each deferred group needs explicit IDs and a reason")
        for spec_id in row["ids"]:
            if spec_id in gaps or spec_id not in by_id:
                raise ValueError(f"{path}: duplicate or unknown deferred ID {spec_id!r}")
            result = by_id[spec_id]
            if result.status != SpecStatus.PENDING or result.evidence:
                raise ValueError(f"{path}: {spec_id} is not an unverified item with no evidence")
            gaps[spec_id] = row["reason"]
    if not any(result.status == SpecStatus.PASSING for result in by_id.values()):
        raise ValueError(f"{path}: scoped verification requires at least one passing requirement")
    return gaps
