import json
import subprocess

import pytest
import quality


@pytest.fixture
def repo(tmp_path, monkeypatch):
    def git(*args):
        return subprocess.check_output(["git", *args], cwd=tmp_path)

    git("init", "-q")
    git("config", "user.name", "Synthetic Test")
    git("config", "user.email", "synthetic@example.invalid")
    git("commit", "--allow-empty", "-qm", "base")
    git("branch", "baseline")
    monkeypatch.setattr(quality, "ROOT", tmp_path)
    monkeypatch.setattr(quality, "git", git)
    return git


def write(name, body):
    path = quality.ROOT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body)


def commit(git):
    git("add", ".")
    git("commit", "-qm", "synthetic change")


def spec():
    return {
        "goal": "Retain the fill list on timeout",
        "excluded": ["Live orders"],
        "research": {"needed": False, "findings": []},
        "decision": {
            "status": "existing",
            "outcome": "Retain fills on timeout",
            "reason": "First demo acceptance requires it",
        },
        "contract": "Return the existing error and preserve the fill list",
        "scope": {"react": ["apps/web/src/"]},
        "acceptance": [
            {"scenario": "Timeout", "expected": "Fills visible", "verification": "npm test"}
        ],
    }


def test_source_change_requires_a_spec(repo):
    write("apps/web/src/example.jsx", "synthetic\n")
    commit(repo)
    with pytest.raises(ValueError, match=r"apps/web/src/example.jsx"):
        quality.check_spec_change("baseline", "HEAD")


def test_committed_spec_covers_changed_paths(repo):
    write("apps/web/src/example.jsx", "synthetic\n")
    write("specs/timeout.json", json.dumps(spec()))
    commit(repo)
    quality.check_spec_change("baseline", "HEAD")
    write("services/research/research/new.py", "synthetic\n")
    commit(repo)
    with pytest.raises(ValueError, match=r"services/research/research/new.py"):
        quality.check_spec_change("baseline", "HEAD")


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda record: record["decision"].update(status="pending"), "decision.status"),
        (lambda record: record["research"].update(needed=True), "research.findings"),
        (lambda record: record["scope"].update(react=["services/research/"]), "scope.react"),
    ],
)
def test_worker_start_rejects_unready_spec(repo, mutate, message):
    record = spec()
    mutate(record)
    write("specs/timeout.json", json.dumps(record))
    with pytest.raises(ValueError, match=message):
        quality.worker_start("specs/timeout.json", "react")


def test_worker_start_shows_only_its_assigned_paths(repo, capsys):
    record = spec()
    record["scope"]["java"] = ["services/trading/src/"]
    write("specs/timeout.json", json.dumps(record))
    quality.worker_start("specs/timeout.json", "react")
    message = capsys.readouterr().out
    assert "apps/web/src/" in message
    assert "services/trading/src/" not in message
    assert "Fills visible" in message


def test_old_spec_does_not_cover_new_change(repo):
    write("specs/timeout.json", json.dumps(spec()))
    commit(repo)
    repo("branch", "-f", "baseline")
    write("apps/web/src/new.jsx", "synthetic\n")
    commit(repo)
    with pytest.raises(ValueError, match=r"apps/web/src/new.jsx"):
        quality.check_spec_change("baseline", "HEAD")


def test_upstream_only_change_does_not_need_branch_spec(repo):
    repo("branch", "feature")
    write("apps/web/src/upstream.jsx", "synthetic\n")
    commit(repo)
    repo("branch", "-f", "baseline")
    repo("checkout", "-q", "feature")
    write("docs/example.md", "synthetic\n")
    commit(repo)
    quality.check_spec_change("baseline", "HEAD")


def test_confirmed_research_flows_into_worker_handoff(repo, capsys):
    record = spec()
    record["research"] = {
        "needed": True,
        "findings": [
            {
                "url": "https://example.org/contract",
                "observation": "A timeout can be handled separately",
                "application": "Preserve independent fills",
                "limits": "The service may still be unavailable",
            }
        ],
    }
    record["decision"]["status"] = "confirmed"
    write("specs/timeout.json", json.dumps(record))
    quality.worker_start("specs/timeout.json", "react")
    output = capsys.readouterr().out
    assert "https://example.org/contract" in output
    assert "Preserve independent fills" in output
    assert "confirmed" in output


def test_uncommitted_spec_cannot_cover_committed_changes(repo):
    write("apps/web/src/example.jsx", "synthetic\n")
    commit(repo)
    write("specs/timeout.json", json.dumps(spec()))
    with pytest.raises(ValueError, match=r"apps/web/src/example.jsx"):
        quality.check_spec_change("baseline", "HEAD")
