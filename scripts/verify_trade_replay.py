import argparse
import json
from pathlib import Path
from urllib.parse import urlencode, urlsplit

from verify_synthetic_ledger import FIXTURE, ROOT, expect, read_path, request

REPLAY = ROOT / "contracts/synthetic-replay.fixture.json"


def verify(base, report):
    address = urlsplit(base)
    expect(
        address.scheme == "http"
        and address.hostname in {"127.0.0.1", "localhost", "::1"}
        and address.username is None
        and address.password is None,
        "Synthetic verification requires a local HTTP endpoint",
    )
    ledger = json.loads(FIXTURE.read_text())
    fixture = json.loads(REPLAY.read_text())
    expected = fixture["expected"]
    scope = fixture["scope"]
    fills = [*ledger["fills"], fixture["prior_fill"], *fixture["additional_fills"]]
    for fill in fills:
        status, _ = request(base, "fills", fill)
        expect(status in {200, 201}, f"Synthetic fill seed returned {status}")

    replay = read_path(base, "replay?" + urlencode(scope))
    expect(all(replay[key] == value for key, value in scope.items()), "Replay scope drifted")
    expect(
        [fill["fill_id"] for fill in replay["fills"]] == expected["fill_ids"],
        "Replay did not isolate fills by date, collection time and symbol",
    )
    expect(
        replay["position_quantity"] == expected["position_quantity"],
        "Historical position must include known fills before the start of the visible window",
    )

    question = fixture["question"]
    status, body = request(base, "replay/questions", {**scope, "question": question})
    expect(status == 200, f"Replay question returned {status}")
    answer = json.loads(body)
    expect(answer["status"] == "answered", "Expected an answer")
    observed = [item["id"] for item in answer["evidence"]]
    expect(
        len(observed) == len(set(observed)) and set(observed) == set(expected["evidence_ids"]),
        "Replay answer did not cite the expected evidence",
    )
    status, body = request(
        base, "replay/questions", {**expected["empty_scope"], "question": question}
    )
    expect(status == 200, f"Empty symbol question returned {status}")
    expect(
        json.loads(body) == {"status": "insufficient_evidence", "answer": "", "evidence": []},
        "Empty symbol should return insufficient evidence",
    )
    status, _ = request(base, "replay?" + urlencode({**scope, "from_date": "2026-11-14"}))
    expect(status == 400, f"Reversed date range returned {status}")

    lines = [
        "Replay isolated three in-range synthetic fills and included opening shares in the position.",
        "The answer cited the expected fills and disclosure, with an explicit empty-symbol result.",
        "A reversed date range returned HTTP 400.",
    ]
    print("\n".join(lines))
    if report:
        with report.open("a") as stream:
            stream.write("\n".join(f"- {line}" for line in lines) + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:5173")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    try:
        verify(args.base.rstrip("/"), args.report)
    except (OSError, ValueError, KeyError) as error:
        raise SystemExit(f"Trade replay verification failed: {error}") from error


if __name__ == "__main__":
    main()
