import json
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

import ask


class RunnerTests(unittest.TestCase):
    def test_future_evidence_removed(self):
        sample = {
            "question": "q",
            "as_of": "2026-11-13",
            "records": [
                {"id": "present", "date": "2026-11-13", "text": "fact"},
                {"id": "future", "date": "2026-11-14", "text": "future fact"},
            ],
        }
        sample["broker_token"] = "synthetic-private"
        sample["records"][0]["account"] = "synthetic-account"
        result = ask.prepare_sample(sample)
        self.assertNotIn("synthetic-private", json.dumps(result))
        self.assertNotIn("synthetic-account", json.dumps(result))
        self.assertEqual([r["id"] for r in result["records"]], ["present"])
        self.assertNotIn("future fact", json.dumps(result))
        self.assertEqual(len(sample["records"]), 2)

    def test_invalid_responses(self):
        good = '{"type":"turn.completed"}'
        answer = '{"answer":"a","evidence_ids":[]}'
        cases = [
            ('{"type":"turn.failed"}', answer),
            ('{"type":"error"}\n' + good, answer),
            ("{}", answer),
            ("[]", "{}"),
            (good, '{"answer":"a","evidence_ids":["unknown"]}'),
            (good, '{"answer":" ","evidence_ids":[]}'),
            (good, "bad json"),
        ]
        for events, result in cases:
            with self.subTest(events=events, result=result), self.assertRaises(ValueError):
                ask.validate_response(events, result, {"known"})

    def test_insufficient_evidence(self):
        self.assertEqual(
            ask.validate_response(
                '{"type":"turn.completed"}',
                '{"answer":"확인할 수 없습니다","evidence_ids":[]}',
                set(),
            )["evidence_ids"],
            [],
        )

    def test_process_boundary(self):
        calls = []

        def fake_run(command, **kwargs):
            calls.append(command)
            self.assertNotIn("BROKER_TOKEN", kwargs["env"])
            if command[1:3] == ["login", "status"]:
                return subprocess.CompletedProcess(command, 0, "Logged in using ChatGPT", "")
            self.assertNotEqual(kwargs["cwd"], ask.ROOT)
            self.assertEqual(command[command.index("--sandbox") + 1], "read-only")
            for item in [
                "shell_tool",
                "unified_exec",
                "hooks",
                "mcp_servers={}",
                'web_search="disabled"',
            ]:
                self.assertIn(item, command)
            Path(command[command.index("--output-last-message") + 1]).write_text(
                '{"answer":"synthetic","evidence_ids":["fill-1"]}'
            )
            return subprocess.CompletedProcess(command, 0, '{"type":"turn.completed"}', "")

        with (
            patch.dict("os.environ", {"BROKER_TOKEN": "synthetic"}),
            patch.object(ask.subprocess, "run", side_effect=fake_run),
        ):
            self.assertEqual(ask.run()["evidence_ids"], ["fill-1"])
        self.assertEqual(len(calls), 2)

    def test_process_failures(self):
        for failure in ["timeout", "exit", "missing-file", "auth"]:

            def fake_run(command, **kwargs):
                if command[1:3] == ["login", "status"]:
                    auth = "API key" if failure == "auth" else "Logged in using ChatGPT"
                    return subprocess.CompletedProcess(command, 0, auth, "")
                if failure == "timeout":
                    raise subprocess.TimeoutExpired(command, 120)
                return subprocess.CompletedProcess(command, int(failure == "exit"), "", "")

            with (
                self.subTest(failure=failure),
                patch.object(ask.subprocess, "run", side_effect=fake_run),
                self.assertRaises((RuntimeError, subprocess.TimeoutExpired)),
            ):
                ask.run()
