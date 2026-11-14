import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import setup_dev


class SetupTests(unittest.TestCase):
    def test_exclusions_and_native_hook_without_overwriting_other_hooks(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q", directory], check=True)
            source = root / "scripts/hooks/pre-push"
            source.parent.mkdir(parents=True)
            source.write_text((setup_dev.ROOT / "scripts/hooks/pre-push").read_text())
            original = subprocess.run

            def run(command, **kwargs):
                if command[0] == "uv":
                    return subprocess.CompletedProcess(command, 0)
                return original(command, **kwargs)

            with (
                patch.object(setup_dev, "ROOT", root),
                patch.object(setup_dev.subprocess, "run", side_effect=run),
            ):
                setup_dev.main()
                setup_dev.main()
                excludes = (root / ".git/info/exclude").read_text()
                self.assertEqual(excludes.count("/.local/"), 1)
                for name in [".local/notes.md", ".agents/skills/a/SKILL.md"]:
                    original(["git", "check-ignore", "-q", name], cwd=root, check=True)
                hook = root / ".git/hooks/pre-push"
                self.assertEqual(hook.read_text(), source.read_text())
                hook.write_text("#!/bin/sh\nexit 0\n")
                with self.assertRaises(RuntimeError):
                    setup_dev.main()
