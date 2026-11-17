import json
import logging
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Optional, Tuple

from .core import InvalidResearchQuestion, answer, parse_research_question
from .synthetic_runtime import InvalidSyntheticDelay, wait_for_synthetic_delay

LOGGER = logging.getLogger("research")
PATH = "/internal/v1/research/questions"
MAX_BODY_BYTES = 16384


class DuplicateJsonKey(ValueError):
    pass


class ResearchRequestHandler(BaseHTTPRequestHandler):
    server_version = "ResearchService"
    sys_version = ""

    def do_POST(self) -> None:
        request_id, request_id_valid = _request_id(self.headers.get("X-Request-ID"))
        if self.path != PATH:
            self._failure(404, "INVALID_REQUEST", request_id, "route_not_found")
            return
        if not request_id_valid:
            self._failure(400, "INVALID_REQUEST", request_id, "invalid_request_id")
            return
        if self.headers.get_content_type() != "application/json":
            self._failure(400, "INVALID_REQUEST", request_id, "invalid_request")
            return
        try:
            payload = _read_json(self)
            question = parse_research_question(payload)
        except (DuplicateJsonKey, InvalidResearchQuestion, UnicodeDecodeError, ValueError):
            self._failure(400, "INVALID_REQUEST", request_id, "invalid_request")
            return
        try:
            wait_for_synthetic_delay()
            response = answer(question)
        except InvalidSyntheticDelay:
            self._failure(503, "RESEARCH_UNAVAILABLE", request_id, "synthetic_delay_invalid")
            return
        except Exception:
            self._failure(503, "RESEARCH_UNAVAILABLE", request_id, "research_failure")
            return
        self._safe_respond(200, response, request_id)

    def do_GET(self) -> None:
        request_id, _ = _request_id(self.headers.get("X-Request-ID"))
        self._failure(404, "INVALID_REQUEST", request_id, "route_not_found")

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _failure(self, status: int, code: str, request_id: str, reason: str) -> None:
        self._log(status, request_id, reason)
        self._safe_respond(status, {"code": code}, request_id)

    def _safe_respond(self, status: int, body: dict, request_id: str) -> None:
        try:
            self._respond(status, body, request_id)
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
            self._log(499, request_id, "client_disconnected")

    def _log(self, status: int, request_id: str, reason: str) -> None:
        LOGGER.info(
            json.dumps(
                {
                    "operation": "answer_question",
                    "reason": reason,
                    "request_id": request_id,
                    "service": "research",
                    "status": status,
                },
                sort_keys=True,
            )
        )

    def _respond(self, status: int, body: dict, request_id: str) -> None:
        encoded = json.dumps(body, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("X-Request-ID", request_id)
        self.end_headers()
        self.wfile.write(encoded)


def create_server(host: str = "127.0.0.1", port: int = 8000) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), ResearchRequestHandler)


def _request_id(value: Optional[str]) -> Tuple[str, bool]:
    if value is None:
        return str(uuid.uuid4()), False
    try:
        uuid.UUID(value)
    except (AttributeError, ValueError):
        return str(uuid.uuid4()), False
    return value, True


def _read_json(handler: BaseHTTPRequestHandler) -> Any:
    content_length = handler.headers.get("Content-Length")
    if content_length is None:
        raise ValueError()
    try:
        length = int(content_length)
    except ValueError as error:
        raise ValueError() from error
    if not 0 <= length <= MAX_BODY_BYTES:
        raise ValueError()
    raw_body = handler.rfile.read(length)
    if len(raw_body) != length:
        raise ValueError()
    return json.loads(raw_body.decode("utf-8"), object_pairs_hook=_no_duplicate_json_keys)


def _no_duplicate_json_keys(pairs: list) -> dict:
    value = {}
    for key, item in pairs:
        if key in value:
            raise DuplicateJsonKey()
        value[key] = item
    return value
