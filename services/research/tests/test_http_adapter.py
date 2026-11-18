import json
import os
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
import uuid
from contextlib import contextmanager
from pathlib import Path

from services.research.research.http_adapter import create_server


@contextmanager
def running_server():
    server = create_server(port=0)
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


def request(base_url, body, request_id=None):
    headers = {"Content-Type": "application/json"}
    if request_id is not None:
        headers["X-Request-ID"] = request_id
    return urllib.request.urlopen(
        urllib.request.Request(
            f"{base_url}/internal/v1/research/questions",
            data=json.dumps(body).encode(),
            headers=headers,
            method="POST",
        )
    )


def payload(quantity=4):
    return {
        "question": "이 거래에서 몇 주 샀어?",
        "evidence": {
            "fill_id": "demo-fill-1",
            "symbol": "SAMPLE",
            "side": "BUY",
            "quantity": quantity,
            "filled_at": "2026-11-13T00:00:00Z",
        },
    }


class ResearchHttpAdapterTests(unittest.TestCase):
    def test_post_returns_deterministic_answer_and_propagates_uuid(self):
        request_id = "df721db6-0c2a-42bf-a945-0c5cf21e7ebd"
        with running_server() as base_url, request(base_url, payload(7), request_id) as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(response.headers["X-Request-ID"], request_id)
            self.assertEqual(
                json.loads(response.read()),
                {"answer": "7주를 매수했습니다.", "evidence_ids": ["demo-fill-1"]},
            )

    def test_invalid_request_id_returns_400_with_safe_generated_uuid(self):
        with running_server() as base_url:
            with self.assertRaises(urllib.error.HTTPError) as raised:
                request(base_url, payload(), "not-a-uuid")
        response = raised.exception
        self.assertEqual(response.code, 400)
        self.assertEqual(json.loads(response.read()), {"code": "INVALID_REQUEST"})
        self.assertNotEqual(response.headers["X-Request-ID"], "not-a-uuid")
        self.assertEqual(
            str(uuid.UUID(response.headers["X-Request-ID"])), response.headers["X-Request-ID"]
        )
        response.close()

    def test_rejects_extra_evidence_field_without_exposing_question(self):
        body = payload()
        body["evidence"]["account"] = "synthetic-account-123"
        body["question"] = "synthetic private question"
        with self.assertLogs("research", level="INFO") as logs, running_server() as base_url:
            with self.assertRaises(urllib.error.HTTPError) as raised:
                request(base_url, body, str(uuid.uuid4()))
        response = raised.exception
        self.assertEqual(response.code, 400)
        self.assertEqual(json.loads(response.read()), {"code": "INVALID_REQUEST"})
        output = "\n".join(logs.output)
        self.assertIn('"reason": "invalid_request"', output)
        self.assertNotIn("synthetic private question", output)
        self.assertNotIn("synthetic-account-123", output)
        response.close()

    def test_delay_setting_delays_synthetic_response(self):
        previous = os.environ.get("RESEARCH_SYNTHETIC_DELAY_MS")
        os.environ["RESEARCH_SYNTHETIC_DELAY_MS"] = "25"
        try:
            with running_server() as base_url:
                started = time.monotonic()
                with request(base_url, payload(), str(uuid.uuid4())):
                    pass
                self.assertGreaterEqual(time.monotonic() - started, 0.02)
        finally:
            if previous is None:
                os.environ.pop("RESEARCH_SYNTHETIC_DELAY_MS", None)
            else:
                os.environ["RESEARCH_SYNTHETIC_DELAY_MS"] = previous

    def test_client_disconnect_is_logged_without_request_data(self):
        previous = os.environ.get("RESEARCH_SYNTHETIC_DELAY_MS")
        os.environ["RESEARCH_SYNTHETIC_DELAY_MS"] = "100"
        request_id = str(uuid.uuid4())
        try:
            with self.assertLogs("research", level="INFO") as logs, running_server() as base_url:
                host_port = base_url.removeprefix("http://").split(":")
                body = json.dumps(payload()).encode()
                request_lines = [
                    "POST /internal/v1/research/questions HTTP/1.1",
                    f"Host: {host_port[0]}",
                    "Content-Type: application/json",
                    f"Content-Length: {len(body)}",
                    f"X-Request-ID: {request_id}",
                    "Connection: close",
                    "",
                    "",
                ]
                client = socket.create_connection((host_port[0], int(host_port[1])))
                client.sendall("\r\n".join(request_lines).encode() + body)
                client.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
                client.close()
                time.sleep(0.2)
        finally:
            if previous is None:
                os.environ.pop("RESEARCH_SYNTHETIC_DELAY_MS", None)
            else:
                os.environ["RESEARCH_SYNTHETIC_DELAY_MS"] = previous
        output = "\n".join(logs.output)
        self.assertIn('"reason": "client_disconnected"', output)
        self.assertIn(request_id, output)
        self.assertNotIn("이 거래에서 몇 주 샀어?", output)

    def test_import_linter_rejects_core_importing_an_adapter(self):
        with tempfile.TemporaryDirectory() as directory:
            root = os.path.abspath(directory)
            package = os.path.join(root, "boundary_sample")
            os.mkdir(package)
            with open(os.path.join(package, "__init__.py"), "w"):
                pass
            with open(os.path.join(package, "adapter.py"), "w") as file:
                file.write("value = 1\n")
            with open(os.path.join(package, "core.py"), "w") as file:
                file.write("from boundary_sample import adapter\n")
            config = os.path.join(root, "pyproject.toml")
            with open(config, "w") as file:
                file.write(
                    "[tool.importlinter]\n"
                    'root_packages = ["boundary_sample"]\n\n'
                    "[[tool.importlinter.contracts]]\n"
                    'name = "core has no adapter dependencies"\n'
                    'type = "forbidden"\n'
                    'source_modules = ["boundary_sample.core"]\n'
                    'forbidden_modules = ["boundary_sample.adapter"]\n'
                )
            completed = subprocess.run(
                [str(Path(sys.executable).with_name("lint-imports")), "--config", config],
                cwd=root,
                capture_output=True,
                text=True,
            )
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("core has no adapter dependencies", completed.stdout + completed.stderr)
