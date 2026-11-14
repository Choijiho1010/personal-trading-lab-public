"""Install local Git exclusions and deterministic hooks."""

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=ROOT, check=True)
    location = subprocess.check_output(
        ["git", "rev-parse", "--git-path", "info/exclude"], cwd=ROOT, text=True
    ).strip()
    exclude = ROOT / location
    exclude.parent.mkdir(parents=True, exist_ok=True)
    current = exclude.read_text() if exclude.exists() else ""
    rules = ["/.local/", "/.agents/", "/.codex/", "/.superpowers/"]
    missing = [rule for rule in rules if rule not in current.splitlines()]
    if missing:
        with exclude.open("a") as stream:
            stream.write("\n" + "\n".join(missing) + "\n")
    subprocess.run(
        ["uv", "run", "--frozen", "pre-commit", "install", "--hook-type", "pre-commit"],
        cwd=ROOT,
        check=True,
    )
    hooks = subprocess.check_output(
        ["git", "rev-parse", "--git-path", "hooks"], cwd=ROOT, text=True
    ).strip()
    target = ROOT / hooks / "pre-push"
    body = (ROOT / "scripts/hooks/pre-push").read_text()
    if target.exists() and target.read_text() != body:
        raise RuntimeError("Existing pre-push hook differs; merge it manually")
    target.write_text(body)
    target.chmod(0o755)
    print("Installed pre-commit and pre-push hooks")


if __name__ == "__main__":
    main()
