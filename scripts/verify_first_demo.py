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
    assert actual_status == status, response
    assert body == {"code": code}, body
    return UUID(headers["X-Request-ID"])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--expect-timeout", action="store_true")
    parser.add_argument("--port", type=int, default=5173)
    options = parser.parse_args()

    fixture = json.loads((ROOT / "contracts/first-demo.fixture.json").read_text())
    base = f"http://127.0.0.1:{options.port}/api/v1/fills"
    fill_id = fixture["fill"]["fill_id"]
    fill_url = f"{base}/{fill_id}"
    question_url = f"{fill_url}/questions"
    assert request(fill_url)[:2] == (200, fixture["fill"])
    verify_error(request(f"{base}/missing"), 404, "FILL_NOT_FOUND")
    verify_error(request(f"{base}/missing/questions", fixture["question"]), 404, "FILL_NOT_FOUND")
    verify_error(
        request(question_url, {"question": " ", "account": "synthetic-private"}),
        400,
        "INVALID_REQUEST",
    )

    result = request(question_url, fixture["question"])
    if options.expect_timeout:
        request_id = verify_error(result, 503, "RESEARCH_UNAVAILABLE")
        print(f"PASS question returned 503 with request ID {request_id}")
    else:
        assert result[:2] == (200, fixture["answer"]), result
        print("PASS question returned the fixture answer and evidence ID")

    assert request(fill_url)[:2] == (200, fixture["fill"])
    print("PASS fill query, input validation and unknown fill")


if __name__ == "__main__":
    main()
