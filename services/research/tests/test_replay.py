import json
import sys
import threading
import uuid
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from services.research.research import replay_runtime
from services.research.research.http_adapter import create_server

CONTRACTS = Path(__file__).resolve().parents[3] / "contracts"
REPLAY = json.loads((CONTRACTS / "synthetic-replay.fixture.json").read_text())
LEDGER = json.loads((CONTRACTS / "synthetic-ledger.fixture.json").read_text())
DISCLOSURES = json.loads((CONTRACTS / "synthetic-disclosures.fixture.json").read_text())
PATH = "/internal/v1/research/replay/questions"


@pytest.fixture(autouse=True)
def synthetic_runtime(monkeypatch):
    monkeypatch.delenv("RESEARCH_REPLAY_RUNTIME", raising=False)
    monkeypatch.delenv("RESEARCH_SYNTHETIC_DELAY_MS", raising=False)


@pytest.fixture
def replay_body():
    return {
        **REPLAY["scope"],
        "question": REPLAY["question"],
        "fills": [dict(row) for row in LEDGER["fills"]],
        "position_quantity": REPLAY["expected"]["position_quantity"],
    }


@pytest.fixture
def post():
    with create_server(port=0) as server:
        thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01})
        thread.start()

        def send(body):
            request_id = str(uuid.uuid4())
            request = Request(
                f"http://127.0.0.1:{server.server_port}{PATH}",
                data=json.dumps(body).encode(),
                headers={"Content-Type": "application/json", "X-Request-ID": request_id},
            )
            try:
                response = urlopen(request, timeout=4)
            except HTTPError as error:
                response = error
            with response:
                assert response.headers["X-Request-ID"] == request_id
                return response.status, json.load(response), request_id

        try:
            yield send
        finally:
            server.shutdown()
            thread.join()


def test_offline_replay_reports_period_trades_and_known_disclosure(post, replay_body):
    status, response, _ = post(replay_body)

    assert status == 200
    assert response["status"] == "answered"
    assert [row["id"] for row in response["evidence"]] == REPLAY["expected"]["evidence_ids"]
    assert "6주" in response["answer"]
    assert "1주" in response["answer"]
    assert "합성 샘플 공시" in response["answer"]


def test_offline_position_uses_ledger_quantity(post, replay_body):
    replay_body["question"] = "기준일 보유 수량은 몇 주인가요?"
    status, response, _ = post(replay_body)

    assert status == 200
    assert response["status"] == "answered"
    assert "8주" in response["answer"]


@pytest.mark.parametrize("empty_scope", [True, False])
def test_missing_knowledge_has_no_answer_or_evidence(post, replay_body, empty_scope):
    if empty_scope:
        replay_body.update(REPLAY["expected"]["empty_scope"], fills=[], position_quantity=0)
    else:
        replay_body["question"] = "다음 달 목표 주가는 얼마인가요?"
    status, response, _ = post(replay_body)

    assert status == 200
    assert response == {"status": "insufficient_evidence", "answer": "", "evidence": []}


@pytest.mark.parametrize(
    "change",
    [
        {"synthetic": False},
        {"source": "live-broker"},
        {"symbol": "OTHER"},
        {"filled_at": "2026-11-11T14:59:59Z"},
        {"filled_at": "2026-11-13T15:00:00Z", "collected_at": "2026-11-13T15:00:00Z"},
        {"collected_at": "2026-11-13T15:00:00Z"},
        {"account_number": "fake-account-marker"},
    ],
)
def test_rejects_out_of_scope_or_unapproved_fill_before_model(
    post, replay_body, change, fake_codex
):
    replay_body["fills"][0].update(change)
    status, response, _ = post(replay_body)

    assert status == 400
    assert response == {"code": "INVALID_REQUEST"}
    assert not fake_codex.exists()


@pytest.mark.parametrize(
    "change",
    [
        {"symbol": "sample"},
        {"from_date": "2026-11-14"},
        {"as_of": "2026-11-31"},
        {"position_quantity": True},
        {"broker_config": "fake-config-marker"},
    ],
)
def test_rejects_invalid_scope_or_request_fields(post, replay_body, change):
    replay_body.update(change)
    assert post(replay_body)[:2] == (400, {"code": "INVALID_REQUEST"})


@pytest.fixture
def fake_codex(tmp_path, monkeypatch):
    capture = tmp_path / "capture.json"
    fake = tmp_path / "codex"
    fake.write_text(
        f"#!{sys.executable}\n"
        + f"""
import json
import os
import pathlib
import sys
import time

arguments = sys.argv[1:]
if arguments == ["login", "status"]:
    print("Logged in using ChatGPT")
    sys.exit(0)
prompt = sys.stdin.read()
pathlib.Path({str(capture)!r}).write_text(json.dumps({{
    "arguments": arguments,
    "cwd": os.getcwd(),
    "environment": list(os.environ),
    "codex_home": os.environ["CODEX_HOME"],
    "codex_home_files": sorted(path.name for path in pathlib.Path(os.environ["CODEX_HOME"]).iterdir()),
    "auth_mode": pathlib.Path(os.environ["CODEX_HOME"], "auth.json").stat().st_mode & 0o777,
    "prompt": prompt,
}}))
scenario = pathlib.Path({str(tmp_path / "scenario")!r}).read_text()
if scenario == "timeout":
    time.sleep(2)
if scenario == "exit":
    sys.exit(1)
if scenario == "invalid event":
    print("invalid-json")
print('{{"type":"turn.completed"}}')
if scenario == "failure event":
    print('{{"type":"turn.failed"}}')
if scenario == "missing output":
    sys.exit(0)
path = pathlib.Path(arguments[arguments.index("--output-last-message") + 1])
response = {{
    "status": "answered",
    "answer": "합성 답변",
    "evidence_ids": ["evidence:fill:synthetic-broker:partial-1"],
}}
if scenario == "unknown id":
    response["evidence_ids"] = [{REPLAY["expected"]["invalid_evidence_id"]!r}]
if scenario == "duplicate id":
    response["evidence_ids"] *= 2
if scenario == "missing citations":
    response["evidence_ids"] = []
if scenario == "empty answer":
    response["answer"] = " "
if scenario == "unexpected field":
    response["account_number"] = "fake-output-marker"
if scenario == "insufficient with evidence":
    response.update(status="insufficient_evidence", answer="")
if scenario == "insufficient":
    response.update(status="insufficient_evidence", answer="", evidence_ids=[])
path.write_text("invalid-json" if scenario == "bad output" else json.dumps(response))
""",
        encoding="utf-8",
    )
    fake.chmod(0o700)
    (tmp_path / "scenario").write_text("success")
    monkeypatch.setenv("PATH", f"{tmp_path}:{Path(sys.executable).parent}:/usr/bin:/bin")
    monkeypatch.setenv("RESEARCH_REPLAY_RUNTIME", "codex")
    login_home = tmp_path / "login"
    login_home.mkdir()
    (login_home / "auth.json").write_text('{"synthetic": true}')
    (login_home / "AGENTS.md").write_text("fake global instructions marker")
    monkeypatch.setenv("CODEX_HOME", str(login_home))
    monkeypatch.setenv("BROKER_API_TOKEN", "fake-env-marker")
    return capture


def test_codex_receives_only_scoped_evidence_and_ledger_quantity(
    post, replay_body, fake_codex, monkeypatch
):
    replay_body["fills"][0].update(
        filled_at="2026-11-11T15:00:00Z", collected_at="2026-11-11T15:00:00Z"
    )
    documents = {
        "disclosures": [
            {**DISCLOSURES["disclosures"][0], "title": "이전 지시를 무시하라는 합성 공시"},
        ]
    }
    fixture_dir = fake_codex.parent
    (fixture_dir / "synthetic-disclosures.fixture.json").write_text(json.dumps(documents))
    (fixture_dir / "synthetic-replay.fixture.json").write_text(json.dumps(REPLAY))
    monkeypatch.setattr(replay_runtime, "CONTRACTS", fixture_dir)
    status, response, _ = post(replay_body)

    assert status == 200
    assert response["status"] == "answered"
    capture = json.loads(fake_codex.read_text())
    instructions, encoded_payload = capture["prompt"].split("\n\n", 1)
    assert "데이터" in instructions
    expected_records = [
        {
            "id": evidence_id,
            "kind": "fill",
            "source": row["source"],
            "reference_id": row["fill_id"],
            "occurred_at": row["filled_at"],
            "collected_at": row["collected_at"],
            "side": row["side"],
            "quantity": row["quantity"],
            "price_krw": row["price_krw"],
        }
        for row, evidence_id in zip(replay_body["fills"], REPLAY["expected"]["evidence_ids"])
    ]
    expected_records.append(
        {
            "id": REPLAY["expected"]["evidence_ids"][-1],
            "kind": "disclosure",
            "source": "synthetic-disclosures",
            "reference_id": "sample-disclosure-1",
            "occurred_at": "2026-11-12T00:00:00Z",
            "collected_at": "2026-11-12T00:01:00Z",
            "title": "이전 지시를 무시하라는 합성 공시",
        }
    )
    assert json.loads(encoded_payload) == {
        **REPLAY["scope"],
        "question": REPLAY["question"],
        "position_quantity": 8,
        "records": expected_records,
    }
    assert response["evidence"] == [
        {
            key: value
            for key, value in expected_records[0].items()
            if key not in {"side", "quantity", "price_krw"}
        }
    ]
    assert "BROKER_API_TOKEN" not in capture["environment"]
    assert Path(capture["codex_home"]) != fake_codex.parent / "login"
    assert capture["codex_home_files"] == ["auth.json"]
    assert capture["auth_mode"] == 0o600
    assert not Path(capture["codex_home"]).exists()
    assert set(
        [
            "--ignore-user-config",
            "--ignore-rules",
            "--ephemeral",
            "read-only",
            "shell_tool",
            "unified_exec",
            "hooks",
            "mcp_servers={}",
            'web_search="disabled"',
        ]
    ) <= set(capture["arguments"])
    assert Path(capture["cwd"]) != CONTRACTS.parent
    assert not Path(capture["cwd"]).exists()


def test_codex_mode_rejects_questions_without_synthetic_provenance(post, replay_body, fake_codex):
    replay_body["question"] = "unapproved question marker"
    assert post(replay_body)[:2] == (400, {"code": "INVALID_REQUEST"})
    assert not fake_codex.exists()


def test_model_can_return_insufficient_evidence(post, replay_body, fake_codex):
    (fake_codex.parent / "scenario").write_text("insufficient")

    assert post(replay_body)[:2] == (
        200,
        {"status": "insufficient_evidence", "answer": "", "evidence": []},
    )


@pytest.mark.parametrize(
    "scenario",
    [
        "exit",
        "timeout",
        "invalid event",
        "failure event",
        "missing output",
        "bad output",
        "unknown id",
        "duplicate id",
        "missing citations",
        "empty answer",
        "unexpected field",
        "insufficient with evidence",
    ],
)
def test_codex_failure_returns_safe_correlated_503(
    post, replay_body, fake_codex, scenario, caplog, monkeypatch
):
    (fake_codex.parent / "scenario").write_text(scenario)
    monkeypatch.setenv("RESEARCH_REPLAY_CODEX_TIMEOUT_SECONDS", "0.5")
    with caplog.at_level("INFO", logger="research"):
        status, response, request_id = post(replay_body)

    assert status == 503
    assert response == {"code": "RESEARCH_UNAVAILABLE"}
    assert fake_codex.exists()
    assert request_id in caplog.text
    assert replay_body["question"] not in caplog.text
    assert "fake-output-marker" not in caplog.text
    assert "합성 샘플 공시" not in caplog.text
