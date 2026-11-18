import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "contracts/synthetic-ledger.fixture.json"
DISCLOSURES = ROOT / "contracts/synthetic-disclosures.fixture.json"


def request(base, route, payload=None):
    url = f"{base}/api/v1/ledger/{route}"
    data = None if payload is None else json.dumps(payload).encode()
    req = Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        with urlopen(req, timeout=5) as response:
            return response.status, response.read()
    except HTTPError as response:
        with response:
            return response.code, response.read()


def expect(condition, message):
    if not condition:
        raise ValueError(message)


def read_path(base, route):
    status, body = request(base, route)
    expect(status == 200, f"{route} returned {status}")
    return json.loads(body)


def rebuild_graph(fills):
    with tempfile.TemporaryDirectory() as temp:
        path = Path(temp)
        input_path = path / "fills.json"
        output = path / "graph.json"
        command = [
            sys.executable,
            "-m",
            "services.research.research.graph_builder",
            "--fills",
            str(input_path),
            "--disclosures",
            str(DISCLOSURES),
            "--output",
            str(output),
        ]
        input_path.write_text(json.dumps({"fills": fills}))
        subprocess.run(command, cwd=ROOT, check=True)
        first = output.read_bytes()
        input_path.write_text(json.dumps({"fills": list(reversed(fills))}))
        subprocess.run(command, cwd=ROOT, check=True)
        expect(output.read_bytes() == first, "Reordered fills changed the rebuilt graph")
        graph = json.loads(first)
        nodes = {node["id"]: node for node in graph["nodes"]}
        edges = graph["relationships"]
        expect(len(nodes) == len(graph["nodes"]), "Graph contains duplicate node IDs")
        expect(
            sum(node["kind"] == "trade" for node in nodes.values()) == len(fills),
            "Rebuilt graph has an unexpected number of trades",
        )
        expect(
            all(edge["from"] in nodes and edge["to"] in nodes for edge in edges),
            "Graph has a dangling relationship",
        )
        observed = set()
        for edge in edges:
            if edge["kind"] != "HAS_EVIDENCE":
                continue
            trade, evidence = nodes[edge["from"]], nodes[edge["to"]]
            expect(
                trade["kind"] == "trade" and evidence["kind"] == "evidence",
                "Graph contains an invalid trade-evidence relationship",
            )
            observed.add((evidence["source"], evidence["evidence_id"], trade["quantity"]))
        expected = {(fill["source"], fill["fill_id"], fill["quantity"]) for fill in fills}
        expect(observed == expected, "Graph evidence does not match the original ledger")


def verify(base, after_restart, report):
    address = urlsplit(base)
    expect(
        address.scheme == "http" and address.hostname in {"127.0.0.1", "localhost", "::1"},
        "Synthetic verification requires a local HTTP endpoint",
    )
    fixture = json.loads(FIXTURE.read_text())
    lines = []
    if not after_restart:
        for fill in fixture["fills"]:
            status, _ = request(base, "fills", fill)
            expect(status == 201, f"Expected first insert, got {status}")
        first = fixture["fills"][0]
        status, _ = request(base, "fills", first)
        expect(status == 200, f"Identical fill replay returned {status}")
        status, body = request(base, "fills", {**first, "quantity": 6})
        expect(
            status == 409 and json.loads(body)["code"] == "FILL_CONFLICT",
            "Conflicting fill failed to produce the documented response",
        )
        lines.append("Three first inserts, 200 on replay, 409 on conflicting quantity.")
    else:
        lines.append("Checked the same ledger after Spring Boot restarted.")
    fills = read_path(base, "fills")["fills"]
    expect(fills == fixture["fills"], "Committed fills differ from the shared fixture")
    for key in ("positions", "conflicts"):
        observed = read_path(base, key)[key]
        expected = fixture[key]
        if key == "conflicts":
            observed = [{field: row[field] for field in expected[0]} for row in observed]
        expect(observed == expected, f"{key} differ from the shared fixture")
    lines.append("Three persisted fills, five shares and one recorded conflict.")
    rebuild_graph(fills)
    lines.append("Two graph rebuilds agreed and all relationships resolved.")
    message = "\n".join(lines) + "\n"
    print(message, end="")
    if report:
        with report.open("a") as stream:
            stream.write("\n".join(f"- {line}" for line in lines) + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--base", default=os.environ.get("LEDGER_BASE_URL", "http://127.0.0.1:5173")
    )
    parser.add_argument("--after-restart", action="store_true")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    try:
        verify(args.base.rstrip("/"), args.after_restart, args.report)
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        raise SystemExit(f"Synthetic ledger verification failed: {error}") from error


if __name__ == "__main__":
    main()
