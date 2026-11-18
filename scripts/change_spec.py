import json
import re
from pathlib import PurePosixPath
from urllib.parse import urlsplit

OWNER_ROOTS = {
    "react": "apps/web/",
    "java": "services/trading/",
    "python": "services/research/",
    "root": "contracts/",
}
SPEC_PATH = re.compile(r"specs/[a-z0-9][a-z0-9-]*\.json")


def require(condition, field, expectation):
    if not condition:
        raise ValueError(f"{field}: {expectation}")


def text(value, field):
    require(isinstance(value, str) and value.strip(), field, "record a nonempty value")


def mapping(value, field):
    require(isinstance(value, dict), field, "expected an object")
    return value


def items(value, field, *, allow_empty=False):
    require(isinstance(value, list), field, "expected a list")
    require(allow_empty or value, field, "record at least one entry")
    return value


def validate_scope(scope):
    mapping(scope, "scope")
    require(scope, "scope", "assign at least one owner")
    for owner, paths in scope.items():
        field = f"scope.{owner}"
        require(owner in OWNER_ROOTS, field, "unknown owner")
        for path in items(paths, field):
            text(path, field)
            normalized = path.rstrip("/")
            require(
                path.startswith(OWNER_ROOTS[owner])
                and path == normalized + ("/" if path.endswith("/") else "")
                and PurePosixPath(normalized).as_posix() == normalized
                and ".." not in PurePosixPath(normalized).parts
                and not any(character in path for character in "*?[]\\\0\n\r"),
                field,
                f"use files or directories under {OWNER_ROOTS[owner]}",
            )


def validate_research(research):
    mapping(research, "research")
    needed = research.get("needed")
    require(isinstance(needed, bool), "research.needed", "choose true or false")
    findings = items(research.get("findings"), "research.findings", allow_empty=not needed)
    for finding in findings:
        mapping(finding, "research.findings")
        for key in ("url", "observation", "application", "limits"):
            text(finding.get(key), f"research.findings.{key}")
        url = urlsplit(finding["url"])
        require(
            url.scheme == "https" and url.hostname and not url.username and not url.password,
            "research.findings.url",
            "use a public HTTPS source without credentials",
        )


def read_spec(path, contents):
    require(SPEC_PATH.fullmatch(path), path, "use specs/<change-id>.json")
    try:
        record = mapping(json.loads(contents), "spec")
        text(record.get("goal"), "goal")
        for value in items(record.get("excluded"), "excluded", allow_empty=True):
            text(value, "excluded")
        validate_research(record.get("research"))
        decision = mapping(record.get("decision"), "decision")
        require(
            decision.get("status") in ("confirmed", "existing"),
            "decision.status",
            "record the confirmed or existing decision before worker start",
        )
        for key in ("outcome", "reason"):
            text(decision.get(key), f"decision.{key}")
        text(record.get("contract"), "contract")
        validate_scope(record.get("scope"))
        for case in items(record.get("acceptance"), "acceptance"):
            mapping(case, "acceptance")
            for key in ("scenario", "expected", "verification"):
                text(case.get(key), f"acceptance.{key}")
    except ValueError as error:
        raise ValueError(f"{path}: {error}") from error
    return record


def covers(scope, name):
    return any(
        name.startswith(path) if path.endswith("/") else name == path
        for paths in scope.values()
        for path in paths
    )
