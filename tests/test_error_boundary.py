import runpy
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
PRIVATE_TEXT = "synthetic private model text"


@pytest.mark.parametrize(
    ("failure", "expected"),
    [("exit", "CODEX_EXEC_FAILED"), ("timeout", "CODEX_TIMEOUT")],
)
def test_cli_failure_output_omits_subprocess_details(monkeypatch, capsys, failure, expected):
    def fake_run(command, **kwargs):
        if command[1:3] == ["login", "status"]:
            return subprocess.CompletedProcess(command, 0, "Logged in using ChatGPT", "")
        if failure == "timeout":
            raise subprocess.TimeoutExpired([PRIVATE_TEXT], 120, stderr=PRIVATE_TEXT)
        event = '{"type": "' + PRIVATE_TEXT + '"}'
        return subprocess.CompletedProcess(command, 1, event, PRIVATE_TEXT)

    monkeypatch.setattr(subprocess, "run", fake_run)
    with pytest.raises(SystemExit) as exit_info:
        runpy.run_path(str(ROOT / "scripts/ask.py"), run_name="__main__")
    captured = capsys.readouterr()
    assert exit_info.value.code == 1
    assert captured.out == ""
    assert PRIVATE_TEXT not in captured.err
    assert expected in captured.err


def test_first_demo_error_contract_only_exposes_code_and_request_id():
    contract = yaml.safe_load((ROOT / "contracts/first-demo.openapi.yaml").read_text())

    def resolve(ref):
        group, name = ref.removeprefix("#/components/").split("/")
        return contract["components"][group][name]

    expected = {
        ("/api/v1/fills/{fill_id}", "get"): {"404": "FILL_NOT_FOUND"},
        ("/api/v1/fills/{fill_id}/questions", "post"): {
            "400": "INVALID_REQUEST",
            "404": "FILL_NOT_FOUND",
            "503": "RESEARCH_UNAVAILABLE",
        },
        ("/internal/v1/research/questions", "post"): {
            "400": "INVALID_REQUEST",
            "503": "RESEARCH_UNAVAILABLE",
        },
    }
    paths = contract["paths"]
    assert set(paths) == {path for path, _ in expected}
    internal_parameters = paths["/internal/v1/research/questions"]["post"]["parameters"]
    assert internal_parameters == [
        {
            "name": "X-Request-ID",
            "in": "header",
            "required": True,
            "schema": {"$ref": "#/components/schemas/RequestId"},
        }
    ]
    assert resolve("#/components/schemas/RequestId") == {"type": "string", "format": "uuid"}
    for (path, method), codes in expected.items():
        responses = paths[path][method]["responses"]
        assert set(responses) - {"200"} == set(codes)
        for status, code in codes.items():
            response = resolve(responses[status]["$ref"])
            assert set(response["headers"]) == {"X-Request-ID"}
            header = resolve(response["headers"]["X-Request-ID"]["$ref"])
            assert header["required"] is True
            schema = resolve(response["content"]["application/json"]["schema"]["$ref"])
            assert schema["additionalProperties"] is False
            assert schema["required"] == ["code"]
            assert schema["properties"] == {"code": {"const": code}}
