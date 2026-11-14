"""Check the bootstrap and its synthetic input without external calls."""

import json
from pathlib import Path

from ask import validate_response

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = (
    "AGENTS.md",
    "README.md",
    "docs/ADR.md",
    "docs/RUBRIC.md",
    "harness/judge.md",
    "harness/sample.json",
    "harness/answer.schema.json",
    "scripts/ask.py",
    "phases/index.json",
    ".gitignore",
    "pyproject.toml",
    ".pre-commit-config.yaml",
    ".github/workflows/quality.yml",
    "scripts/quality.py",
    "scripts/setup_dev.py",
    "scripts/hooks/pre-push",
    "docs/development-quality.md",
)


def main():
    for filename in REQUIRED:
        assert (ROOT / filename).is_file(), filename
    for filename in ("phases/index.json", "harness/sample.json", "harness/answer.schema.json"):
        json.loads((ROOT / filename).read_text())
    for filename in ("scripts/ask.py", "scripts/validate.py"):
        compile((ROOT / filename).read_text(), filename, "exec")

    phases = json.loads((ROOT / "phases/index.json").read_text())["phases"]
    assert len({phase["id"] for phase in phases}) == len(phases)
    assert all(phase.get("exit") and phase.get("status") for phase in phases)
    assert {"bootstrap", "ledger", "graph", "live"} <= {phase["id"] for phase in phases}

    success = '{"type":"turn.completed"}'
    answer = '{"answer":"합성 답변","evidence_ids":["fill-1"]}'
    assert validate_response(success, answer, {"fill-1"})["evidence_ids"] == ["fill-1"]
    for events, allowed_ids in [
        ('{"type":"turn.failed"}', {"fill-1"}),
        (success, set()),
        ("{}", {"fill-1"}),
    ]:
        try:
            validate_response(events, answer, allowed_ids)
        except ValueError:
            continue
        raise AssertionError("Invalid run or evidence was accepted")
    print("PASS scaffold, phase records, synthetic Codex success and rejection cases")


if __name__ == "__main__":
    main()
