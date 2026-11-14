import io
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import quality


class QualityTests(unittest.TestCase):
    def test_private_paths(self):
        for name in [
            "data/fills.csv",
            "secrets/auth.json",
            ".env",
            ".env.prod",
            "a/client.key",
            ".local/notes.md",
            ".agents/skills/a.md",
            "runs/a.json",
            "a/a.sqlite-wal",
        ]:
            with self.subTest(name=name), self.assertRaises(ValueError):
                quality.check_content(name, b"synthetic\n")

    def test_public_sources(self):
        for name in [
            "harness/sample.json",
            "tests/fixtures/fills.csv",
            ".env.example",
            "uv.lock",
            "docs/ADR.md",
        ]:
            self.assertFalse(quality.forbidden_path(name))

    def test_invalid_json(self):
        with self.assertRaises(ValueError):
            quality.check_content("harness/a.json", b"not json\n")

    def test_missing_scanner_blocks(self):
        with (
            patch.object(quality.shutil, "which", return_value=None),
            patch.object(quality.Path, "is_file", return_value=False),
            self.assertRaises(RuntimeError),
        ):
            quality.scan_content(b"synthetic")

    def test_push_requires_refs(self):
        with patch("sys.stdin", io.StringIO("")), self.assertRaises(RuntimeError):
            quality.push()

    def test_first_push_range(self):
        self.assertEqual(quality.history_range("a" * 40, "0" * 40), "a" * 40)
        self.assertEqual(quality.history_range("a" * 40, "b" * 40), "b" * 40 + ".." + "a" * 40)

    def test_push_reads_all_refs(self):
        sha = "a" * 40
        refs = f"refs/heads/a {sha} refs/heads/a {'0' * 40}\n" * 2
        with (
            patch("sys.stdin", io.StringIO(refs)),
            patch.object(
                quality, "git", side_effect=[sha.encode(), sha.encode(), sha.encode(), b""]
            ),
            patch.object(quality, "audit_revision") as audit,
            patch.object(quality, "check") as check,
        ):
            quality.push()
            self.assertEqual(audit.call_count, 2)
            check.assert_called_once()

    def test_forced_staged_private_path(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q", directory], check=True)
            (root / ".gitignore").write_text(".env\n")
            (root / ".env").write_text("synthetic\n")
            subprocess.run(["git", "-C", directory, "add", "-f", ".env"], check=True)
            original = quality.git
            with (
                patch.object(quality, "git", side_effect=lambda *args: original(*args, cwd=root)),
                self.assertRaisesRegex(ValueError, "Forbidden staged"),
            ):
                quality.staged()

    def test_deleted_private_file_in_history(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q", directory], check=True)

            def git(*args):
                return quality.git(*args, cwd=root)

            git("config", "user.name", "Synthetic Test")
            git("config", "user.email", "synthetic@example.invalid")
            (root / ".env").write_text("synthetic\n")
            git("add", ".env")
            git("commit", "-qm", "synthetic fixture")
            git("rm", "-q", ".env")
            git("commit", "-qm", "remove fixture")
            original = quality.git
            with (
                patch.object(quality, "git", side_effect=lambda *args: original(*args, cwd=root)),
                self.assertRaisesRegex(ValueError, "Forbidden historical"),
            ):
                quality.audit_revision("HEAD", "--all")

    def test_scanner_failure_blocks(self):
        with (
            patch.object(quality, "require_gitleaks"),
            patch.object(
                quality.subprocess, "run", side_effect=subprocess.CalledProcessError(1, "gitleaks")
            ),
            self.assertRaises(subprocess.CalledProcessError),
        ):
            quality.scan_content(b"synthetic")

    def test_staged_blob_not_working_tree_is_scanned(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q", directory], check=True)
            (root / "sample.txt").write_text("staged synthetic marker\n")
            subprocess.run(["git", "-C", directory, "add", "sample.txt"], check=True)
            (root / "sample.txt").write_text("different working copy\n")
            original = quality.git
            with (
                patch.object(quality, "git", side_effect=lambda *args: original(*args, cwd=root)),
                patch.object(quality, "scan_content") as scan,
            ):
                quality.staged()
                scan.assert_called_once_with(b"staged synthetic marker\n")

    def test_private_comment_and_link_rejected(self):
        for text in ["# Generated by " + "Codex\n", "[notes](" + ".local/notes.md)\n"]:
            with self.subTest(text=text), self.assertRaises(ValueError):
                quality.check_content("docs/example.md", text.encode())
        quality.check_content("docs/example.md", b"# Codex runner\nTechnical dependency.\n")

    @unittest.skipUnless(
        shutil.which("gitleaks") or (quality.ROOT / ".local/bin/gitleaks").is_file(),
        "Gitleaks integration requires the installed scanner",
    )
    def test_real_scanner_rejects_synthetic_secret(self):
        synthetic = "token = ghp_" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8"
        with self.assertRaises(subprocess.CalledProcessError):
            quality.scan_content(synthetic.encode())
        quality.scan_content(b"Synthetic SAMPLE: buy 2 shares at 100.00")
