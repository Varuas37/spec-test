"""Join versioned source annotations to requirements without claiming evidence."""

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath

from .collector import collect_specs

_ID = re.compile(r"[A-Z][A-Z0-9]*-[0-9]+")
_ROLES = {"implements", "verifies"}
_FIELDS = {"spec_id", "role", "file", "line", "symbol", "language"}


@dataclass(frozen=True, order=True)
class TraceLink:
    spec_id: str
    role: str
    file: str
    line: int
    symbol: str
    language: str


def _load_links(path: Path) -> list[TraceLink]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if (
        not isinstance(payload, dict)
        or set(payload) != {"schema_version", "links"}
        or type(payload["schema_version"]) is not int
        or payload["schema_version"] != 1
        or not isinstance(payload["links"], list)
    ):
        raise ValueError(f"{path}: expected trace schema version 1")

    links = []
    seen = set()
    for row in payload["links"]:
        if (
            not isinstance(row, dict)
            or set(row) != _FIELDS
            or any(not isinstance(row[k], str) or not row[k] for k in _FIELDS - {"line"})
            or type(row["line"]) is not int
            or row["line"] < 1
            or not _ID.fullmatch(row["spec_id"])
            or row["role"] not in _ROLES
        ):
            raise ValueError(f"{path}: invalid trace row")
        file = PurePosixPath(row["file"])
        if (
            file.is_absolute()
            or not file.parts
            or ".." in file.parts
            or file.as_posix() != row["file"]
        ):
            raise ValueError(f"{path}: invalid trace source path")
        link = TraceLink(**row)
        key = (link.language, link.file, link.symbol, link.role, link.spec_id)
        if key in seen:
            raise ValueError(f"{path}: duplicate or ambiguous trace for {link.file}::{link.symbol}")
        seen.add(key)
        links.append(link)
    return sorted(links)


def build_trace(specs_dir: Path, index: Path, required: list[str]) -> dict:
    """Report linked locations; no source annotation marks verification as passed."""
    links = _load_links(index)
    requirements = {}
    for spec in collect_specs(specs_dir):
        if spec.id in requirements:
            raise ValueError(f"Duplicate requirement ID: {spec.id}")
        requirements[spec.id] = spec

    rows = {}
    for link in links:
        rows.setdefault(link.spec_id, []).append(link)
    ids = set(required) | set(rows)
    if not ids:
        raise ValueError("No trace links found; use --require ID to guard expected links")
    output = []
    for spec_id in sorted(ids):
        if spec_id not in requirements:
            raise ValueError(f"Unknown requirement ID: {spec_id}")
        spec = requirements[spec_id]
        matches = rows.get(spec_id, [])
        missing = _ROLES - {link.role for link in matches}
        if missing:
            raise ValueError(f"{spec_id}: missing trace roles: {', '.join(sorted(missing))}")
        implementations = {
            (link.language, link.file, link.symbol) for link in matches if link.role == "implements"
        }
        if any(
            (link.language, link.file, link.symbol) in implementations
            for link in matches if link.role == "verifies"
        ):
            raise ValueError(f"{spec_id}: implementation and verification must be separate symbols")
        output.append({
            "spec_id": spec_id,
            "requirement": {"file": spec.source_file.as_posix(), "line": spec.source_line},
            "links": [asdict(link) for link in matches],
        })
    return {"schema_version": 1, "requirements": output}
