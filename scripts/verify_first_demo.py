import argparse
import json
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import UUID

ROOT = Path(__file__).resolve().parents[1]


def request(url, body=None):
    data = None if body is None else json.dumps(body).encode()
    headers = {} if data is None else {"Content-Type": "application/json"}
    try:
        response = urlopen(Request(url, data=data, headers=headers), timeout=10)
    except HTTPError as error:
        response = error
    with response:
        return response.status, json.load(response), response.headers


def verify_error(response, status, code):
    actual_status, body, headers = response
    assert actual_status == status, f"Expected HTTP {status}; got {actual_status}"
    assert body == {"code": code}, f"Expected error code {code}"
    return UUID(headers["X-Request-ID"])


def verify(port, expect_timeout, observations):
    fixture = json.loads((ROOT / "contracts/first-demo.fixture.json").read_text())
    base = f"http://127.0.0.1:{port}/api/v1/fills"
    fill_id = fixture["fill"]["fill_id"]
    fill_url = f"{base}/{fill_id}"
    question_url = f"{fill_url}/questions"
    assert request(fill_url)[:2] == (200, fixture["fill"])
    observations.append(f"체결 조회 HTTP 200 · 합성 체결 {fill_id} 일치")
    verify_error(request(f"{base}/missing"), 404, "FILL_NOT_FOUND")
    verify_error(request(f"{base}/missing/questions", fixture["question"]), 404, "FILL_NOT_FOUND")
    observations.append("미등록 체결 조회와 질문 HTTP 404 · FILL_NOT_FOUND")
    verify_error(
        request(question_url, {"question": " ", "account": "synthetic-private"}),
        400,
        "INVALID_REQUEST",
    )
    observations.append("잘못된 질문 HTTP 400 · INVALID_REQUEST")

    result = request(question_url, fixture["question"])
    if expect_timeout:
        request_id = verify_error(result, 503, "RESEARCH_UNAVAILABLE")
        observations.append(f"질문 HTTP 503 · RESEARCH_UNAVAILABLE · 요청 ID `{request_id}`")
        print(f"PASS question returned 503 with request ID {request_id}")
    else:
        assert result[:2] == (200, fixture["answer"]), "Expected the synthetic answer and evidence"
        answer = fixture["answer"]["answer"]
        evidence_ids = ", ".join(fixture["answer"]["evidence_ids"])
        observations.append(f"질문 HTTP 200 · {answer} 근거 `{evidence_ids}`")
        print("PASS question returned the fixture answer and evidence ID")

    assert request(fill_url)[:2] == (200, fixture["fill"])
    observations.append("질문 이후 체결 재조회 HTTP 200 · 기존 합성 체결 일치")
    print("PASS fill query, input validation and unknown fill")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--expect-timeout", action="store_true")
    parser.add_argument("--port", type=int, default=5173)
    parser.add_argument("--report", type=Path, help="Append synthetic observations to Markdown")
    options = parser.parse_args()

    observations = []
    passed = False
    try:
        verify(options.port, options.expect_timeout, observations)
        passed = True
    finally:
        if options.report is not None:
            scenario = "설명 서비스 타임아웃" if options.expect_timeout else "정상 응답"
            result = "통과" if passed else "실패 · 자세한 오류는 검사 로그 참조"
            with options.report.open("a", encoding="utf-8") as report:
                report.write(f"\n### HTTP 통합 검사 · {scenario}\n\n- 결과 — {result}\n")
                report.writelines(f"- {observation}\n" for observation in observations)


if __name__ == "__main__":
    main()
