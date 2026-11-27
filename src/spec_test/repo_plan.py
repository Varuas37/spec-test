"""Build an explainable, non-executing plan from local repository manifests."""

import json
import re
import subprocess
import sys
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath

CONFIG = "spec-test.toml"
_ID = re.compile(r"[a-z][a-z0-9-]*")
_MANAGERS = {"npm": ("package-lock.json", "npm-shrinkwrap.json"),
             "pnpm": ("pnpm-lock.yaml",), "yarn": ("yarn.lock",),
             "bun": ("bun.lock", "bun.lockb")}


@dataclass(frozen=True)
class Check:
    id: str
    language: str
    cwd: str
    argv: list[str]


@dataclass(frozen=True)
class Plan:
    source: str
    checks: list[Check]
    notes: list[str]

    def as_dict(self) -> dict:
        return {"schema_version": 1, **asdict(self)}


def _under(root: Path, path: Path) -> Path:
    actual = (root / path).resolve()
    if not actual.is_relative_to(root):
        raise ValueError(f"Path leaves project root: {path}")
    return actual


def _read_toml(root: Path, file: str) -> dict:
    return tomllib.loads(_under(root, Path(file)).read_text(encoding="utf-8"))


def _configured(root: Path) -> Plan:
    data = _read_toml(root, CONFIG)
    if (
        set(data) != {"schema_version", "checks"}
        or type(data["schema_version"]) is not int
        or data["schema_version"] != 1
        or not isinstance(data["checks"], list)
        or not data["checks"]
    ):
        raise ValueError(f"{CONFIG}: expected schema_version = 1 and nonempty [[checks]]")
    checks = []
    ids = set()
    for row in data["checks"]:
        if (
            not isinstance(row, dict)
            or set(row) != {"id", "language", "cwd", "argv"}
            or any(not isinstance(row[k], str) or not row[k] for k in ("id", "language", "cwd"))
            or not _ID.fullmatch(row["id"])
            or not _ID.fullmatch(row["language"])
            or not isinstance(row["argv"], list) or not row["argv"]
            or any(not isinstance(arg, str) or "\x00" in arg for arg in row["argv"])
            or not row["argv"][0].strip()
        ):
            raise ValueError(f"{CONFIG}: malformed check")
        if row["id"] in ids:
            raise ValueError(f"{CONFIG}: duplicate check id {row['id']}")
        ids.add(row["id"])
        relative = PurePosixPath(row["cwd"])
        if (
            relative.is_absolute() or ".." in relative.parts
            or relative.as_posix() != row["cwd"]
            or ":" in row["cwd"] or "\\" in row["cwd"] or "\x00" in row["cwd"]
            or not _under(root, Path(row["cwd"])).is_dir()
        ):
            raise ValueError(f"{CONFIG}: invalid cwd for {row['id']}")
        argv = row["argv"]
        if argv[0] == "python":
            argv = [sys.executable, *argv[1:]]
        checks.append(Check(row["id"], row["language"], row["cwd"], argv))
    return Plan(CONFIG, checks, [])


def discover(root: Path) -> Plan:
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("Project root is not a directory")
    if (root / CONFIG).exists() or (root / CONFIG).is_symlink():
        return _configured(root)
    checks = []
    notes = []

    pytest_config = any((root / file).is_file() for file in ("pytest.ini", ".pytest.ini"))
    pyproject = root / "pyproject.toml"
    if pyproject.is_file():
        tools = _read_toml(root, "pyproject.toml").get("tool", {})
        pytest_config |= isinstance(tools, dict) and "pytest" in tools
    if pytest_config or (pyproject.is_file() and (root / "tests").is_dir()):
        # Bind the invoking interpreter, not an arbitrary repo executable.
        checks.append(Check("python", "python", ".", [sys.executable, "-m", "pytest"]))
    elif pyproject.is_file():
        notes.append("Python manifest found without pytest configuration or a tests directory.")

    if (root / "Cargo.toml").is_file():
        cargo = _read_toml(root, "Cargo.toml")
        if "workspace" in cargo or "package" in cargo:
            argv = ["cargo", "test"]
            if "workspace" in cargo:
                argv.append("--workspace")
            if (root / "Cargo.lock").is_file():
                argv.append("--locked")
            checks.append(Check("rust", "rust", ".", argv))
        else:
            notes.append("Cargo manifest declares neither a package nor a workspace.")

    if (root / "package.json").is_file():
        package = json.loads(_under(root, Path("package.json")).read_text(encoding="utf-8"))
        if not isinstance(package, dict):
            raise ValueError("package.json: expected an object")
        scripts = package.get("scripts", {})
        declared = package.get("packageManager")
        locks = [manager for manager, files in _MANAGERS.items()
                 if any((root / file).is_file() for file in files)]
        if isinstance(declared, str):
            manager = declared.split("@", 1)[0]
        else:
            manager = locks[0] if len(locks) == 1 else "npm" if not locks else ""
        if not isinstance(scripts, dict) or not isinstance(scripts.get("test"), str) or not scripts["test"].strip():
            notes.append("Node package has no nonempty test script.")
        elif manager not in _MANAGERS:
            notes.append("Node package manager is unknown or ambiguous; configure an explicit check.")
        else:
            typescript = (root / "tsconfig.json").is_file() or any(
                isinstance(package.get(key), dict) and "typescript" in package[key]
                for key in ("dependencies", "devDependencies", "peerDependencies")
            )
            language = "typescript" if typescript else "javascript"
            checks.append(Check(language, language, ".", [manager, "test"]))

    if not checks:
        notes.append(f"No unambiguous test commands found; add {CONFIG} for this project.")
    return Plan("detected", checks, notes)


def write_config(root: Path, plan: Plan) -> Path:
    if not plan.checks:
        raise ValueError("No detected checks to save")
    target = root.resolve(strict=True) / CONFIG
    chunks = ["schema_version = 1\n"]
    for check in plan.checks:
        # Generated configs must be portable across user environments.
        values = asdict(check)
        if plan.source == "detected" and check.language == "python":
            values["argv"] = ["python", *check.argv[1:]]
        chunks.extend(("\n[[checks]]\n", *(f"{key} = {json.dumps(value, ensure_ascii=False)}\n"
                                             for key, value in values.items())))
    with target.open("x", encoding="utf-8") as handle:
        handle.write("".join(chunks))
    return target


def run_checks(root: Path, plan: Plan) -> int:
    """Execute the already authorized argv directly; this is not a sandbox."""
    failed = False
    for check in plan.checks:
        print(f"[{check.id}] {json.dumps(check.argv)}", flush=True)
        try:
            result = subprocess.run(
                check.argv, cwd=_under(root, Path(check.cwd)), shell=False, check=False
            )
            code = result.returncode
        except OSError as exc:
            print(f"[{check.id}] {exc}", file=sys.stderr)
            code = 1
        failed |= code != 0
        print(f"[{check.id}] {'failed' if code else 'passed'}", flush=True)
    return int(failed)
