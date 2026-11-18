import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from services.research.research.graph_builder import (
    InvalidGraphInput,
    build_graph,
    read_graph_inputs,
)

ROOT = Path(__file__).resolve().parents[3]
FILL_FIXTURE = ROOT / "contracts" / "synthetic-ledger.fixture.json"
DISCLOSURE_FIXTURE = ROOT / "contracts" / "synthetic-disclosures.fixture.json"


def fixtures():
    fills = json.loads(FILL_FIXTURE.read_text())
    disclosures = json.loads(DISCLOSURE_FIXTURE.read_text())
    return fills, disclosures


def test_builds_a_deterministic_graph_from_synthetic_fills_and_disclosures():
    fills, disclosures = fixtures()

    graph = build_graph(fills, disclosures)

    assert graph["schema_version"] == 1
    assert [node["id"] for node in graph["nodes"]] == [
        "evidence:disclosure:synthetic-disclosures:sample-disclosure-1",
        "evidence:fill:synthetic-broker:partial-1",
        "evidence:fill:synthetic-broker:partial-2",
        "evidence:fill:synthetic-broker:sell-1",
        "instrument:SAMPLE",
        "trade:synthetic-broker:partial-1",
        "trade:synthetic-broker:partial-2",
        "trade:synthetic-broker:sell-1",
    ]
    assert {node["kind"] for node in graph["nodes"]} == {"instrument", "trade", "evidence"}
    trade = next(
        node for node in graph["nodes"] if node["id"] == "trade:synthetic-broker:partial-1"
    )
    assert trade == {
        "collected_at": "2026-11-13T00:00:01Z",
        "filled_at": "2026-11-13T00:00:00Z",
        "id": "trade:synthetic-broker:partial-1",
        "kind": "trade",
        "price_krw": 10000,
        "quantity": 4,
        "side": "BUY",
        "source": "synthetic-broker",
        "symbol": "SAMPLE",
    }
    assert graph["relationships"] == sorted(
        graph["relationships"], key=lambda value: (value["from"], value["kind"], value["to"])
    )
    assert {(edge["from"], edge["kind"], edge["to"]) for edge in graph["relationships"]} == {
        (
            "evidence:disclosure:synthetic-disclosures:sample-disclosure-1",
            "ABOUT",
            "instrument:SAMPLE",
        ),
        *(
            (f"trade:synthetic-broker:{fill_id}", "TRADED_IN", "instrument:SAMPLE")
            for fill_id in ("partial-1", "partial-2", "sell-1")
        ),
        *(
            (
                f"trade:synthetic-broker:{fill_id}",
                "HAS_EVIDENCE",
                f"evidence:fill:synthetic-broker:{fill_id}",
            )
            for fill_id in ("partial-1", "partial-2", "sell-1")
        ),
    }
    assert all(
        relationship["from"] in {node["id"] for node in graph["nodes"]}
        and relationship["to"] in {node["id"] for node in graph["nodes"]}
        for relationship in graph["relationships"]
    )


def test_same_facts_in_a_different_input_order_produce_identical_output():
    fills, disclosures = fixtures()
    reordered_fills = deepcopy(fills)
    reordered_disclosures = deepcopy(disclosures)
    reordered_fills["fills"].reverse()
    reordered_disclosures["disclosures"].reverse()

    assert build_graph(fills, disclosures) == build_graph(reordered_fills, reordered_disclosures)


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda fills, disclosures: fills["fills"][0].update(synthetic=False), "synthetic"),
        (lambda fills, disclosures: fills["fills"][0].update(side=["BUY"]), "fill.side"),
        (
            lambda fills, disclosures: fills["fills"][0].update(quantity=2_147_483_648),
            "fill.quantity",
        ),
        (lambda fills, disclosures: fills["fills"][0].pop("collected_at"), "collected_at"),
        (lambda fills, disclosures: fills["fills"][0].update(filled_at="not-a-date"), "filled_at"),
        (
            lambda fills, disclosures: fills["fills"][0].update(
                collected_at="2026-11-12T23:59:59Z"
            ),
            "fill.collected_at",
        ),
        (
            lambda fills, disclosures: fills["fills"].append(deepcopy(fills["fills"][0])),
            "duplicate fill",
        ),
        (lambda fills, disclosures: disclosures["disclosures"][0].pop("source"), "source"),
        (
            lambda fills, disclosures: disclosures["disclosures"][0].update(
                occurred_at="2026-11-12"
            ),
            "occurred_at",
        ),
    ],
)
def test_rejects_invalid_or_ambiguous_graph_inputs(mutate, message):
    fills, disclosures = fixtures()
    mutate(fills, disclosures)

    with pytest.raises(InvalidGraphInput, match=message):
        build_graph(fills, disclosures)


def test_cli_reads_ledger_export_and_writes_graph_atomically(tmp_path):
    fills, disclosures = fixtures()
    fills_path = tmp_path / "fills.json"
    disclosures_path = tmp_path / "disclosures.json"
    output_path = tmp_path / "nested" / "graph.json"
    fills_path.write_text(json.dumps(fills))
    disclosures_path.write_text(json.dumps(disclosures))

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "services.research.research.graph_builder",
            "--fills",
            str(fills_path),
            "--disclosures",
            str(disclosures_path),
            "--output",
            str(output_path),
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(output_path.read_text()) == build_graph(fills, disclosures)
    assert completed.stdout == f"{output_path}\n"
    assert not list(output_path.parent.glob(".graph.json.*"))


def test_reader_rejects_non_object_json_inputs(tmp_path):
    fills_path = tmp_path / "fills.json"
    disclosures_path = tmp_path / "disclosures.json"
    fills_path.write_text("[]")
    disclosures_path.write_text("{}")

    with pytest.raises(InvalidGraphInput, match="fills"):
        read_graph_inputs(fills_path, disclosures_path)


def test_cli_rejects_bad_dates_without_printing_input_or_replacing_graph(tmp_path):
    fills, disclosures = fixtures()
    fills["fills"][0]["filled_at"] = "private-sentinel"
    fills_path = tmp_path / "fills.json"
    disclosures_path = tmp_path / "disclosures.json"
    output_path = tmp_path / "graph.json"
    fills_path.write_text(json.dumps(fills))
    disclosures_path.write_text(json.dumps(disclosures))
    output_path.write_text("previous graph\n")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "services.research.research.graph_builder",
            "--fills",
            str(fills_path),
            "--disclosures",
            str(disclosures_path),
            "--output",
            str(output_path),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert result.stderr == "Invalid graph input: fill.filled_at\n"
    assert output_path.read_text() == "previous graph\n"
