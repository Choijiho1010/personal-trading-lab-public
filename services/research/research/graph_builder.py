import argparse
import json
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

FILL_FIELDS = {
    "source",
    "fill_id",
    "symbol",
    "side",
    "quantity",
    "price_krw",
    "filled_at",
    "collected_at",
    "synthetic",
}
DISCLOSURE_FIELDS = {
    "source",
    "evidence_id",
    "symbol",
    "occurred_at",
    "collected_at",
    "title",
    "synthetic",
}
IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
SYMBOL = re.compile(r"^[A-Z0-9][A-Z0-9.-]{0,19}$")


class InvalidGraphInput(ValueError):
    pass


class DuplicateJsonKey(ValueError):
    pass


def build_graph(fills_document: Any, disclosures_document: Any) -> dict[str, Any]:
    fills = parse_fills(fills_document)
    disclosures = parse_disclosures(disclosures_document)
    nodes = []
    relationships = []
    symbols = sorted({fill["symbol"] for fill in fills} | {item["symbol"] for item in disclosures})
    for symbol in symbols:
        nodes.append({"id": f"instrument:{symbol}", "kind": "instrument", "symbol": symbol})
    for fill in fills:
        trade_id = _trade_id(fill)
        evidence_id = _fill_evidence_id(fill)
        nodes.extend(
            [
                {
                    "collected_at": fill["collected_at"],
                    "filled_at": fill["filled_at"],
                    "id": trade_id,
                    "kind": "trade",
                    "price_krw": fill["price_krw"],
                    "quantity": fill["quantity"],
                    "side": fill["side"],
                    "source": fill["source"],
                    "symbol": fill["symbol"],
                },
                {
                    "collected_at": fill["collected_at"],
                    "evidence_id": fill["fill_id"],
                    "id": evidence_id,
                    "kind": "evidence",
                    "occurred_at": fill["filled_at"],
                    "source": fill["source"],
                    "synthetic": True,
                },
            ]
        )
        relationships.extend(
            [
                {"from": trade_id, "kind": "TRADED_IN", "to": f"instrument:{fill['symbol']}"},
                {"from": trade_id, "kind": "HAS_EVIDENCE", "to": evidence_id},
            ]
        )
    for disclosure in disclosures:
        evidence_id = _disclosure_evidence_id(disclosure)
        nodes.append(
            {
                "collected_at": disclosure["collected_at"],
                "evidence_id": disclosure["evidence_id"],
                "id": evidence_id,
                "kind": "evidence",
                "occurred_at": disclosure["occurred_at"],
                "source": disclosure["source"],
                "synthetic": True,
                "title": disclosure["title"],
            }
        )
        relationships.append(
            {"from": evidence_id, "kind": "ABOUT", "to": f"instrument:{disclosure['symbol']}"}
        )
    nodes.sort(key=lambda item: item["id"])
    relationships.sort(key=lambda item: (item["from"], item["kind"], item["to"]))
    return {"schema_version": 1, "nodes": nodes, "relationships": relationships}


def read_graph_inputs(
    fills_path: Path, disclosures_path: Path
) -> tuple[dict[str, Any], dict[str, Any]]:
    return read_document(fills_path, "fills"), read_document(disclosures_path, "disclosures")


def write_graph(graph: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{output_path.name}.", suffix=".tmp", dir=output_path.parent
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(graph, stream, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_name, output_path)
    except Exception:
        Path(temporary_name).unlink(missing_ok=True)
        raise


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fills", required=True, type=Path)
    parser.add_argument("--disclosures", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    try:
        fills, disclosures = read_graph_inputs(arguments.fills, arguments.disclosures)
        write_graph(build_graph(fills, disclosures), arguments.output)
    except InvalidGraphInput as error:
        parser.exit(2, f"Invalid graph input: {error}\n")
    print(arguments.output)


def read_document(path: Path, name: str) -> dict[str, Any]:
    try:
        with path.open(encoding="utf-8") as stream:
            value = json.load(stream, object_pairs_hook=_no_duplicate_json_keys)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, DuplicateJsonKey) as error:
        raise InvalidGraphInput(f"{name}: invalid JSON") from error
    if not isinstance(value, dict):
        raise InvalidGraphInput(f"{name}: expected an object")
    return value


def parse_fills(document: Any) -> list[dict[str, Any]]:
    if (
        not isinstance(document, dict)
        or "fills" not in document
        or not set(document)
        <= {
            "fills",
            "positions",
            "conflicts",
        }
    ):
        raise InvalidGraphInput("fills: expected ledger export fields")
    fills = document["fills"]
    if not isinstance(fills, list):
        raise InvalidGraphInput("fills: expected a list")
    parsed = [_parse_fill(value) for value in fills]
    identities = [(value["source"], value["fill_id"]) for value in parsed]
    if len(set(identities)) != len(identities):
        raise InvalidGraphInput("fills: duplicate fill")
    return sorted(parsed, key=lambda value: (value["source"], value["fill_id"]))


def _parse_fill(value: Any) -> dict[str, Any]:
    _expected_fields(value, FILL_FIELDS, "fill")
    _require(value["source"] == "synthetic-broker", "fill.source")
    _identifier(value["fill_id"], "fill.fill_id")
    _symbol(value["symbol"], "fill.symbol")
    _require(value["side"] in ("BUY", "SELL"), "fill.side")
    _positive_integer(value["quantity"], "fill.quantity")
    _positive_integer(value["price_krw"], "fill.price_krw")
    filled_at = parse_timestamp(value["filled_at"], "fill.filled_at")
    collected_at = parse_timestamp(value["collected_at"], "fill.collected_at")
    _require(collected_at >= filled_at, "fill.collected_at")
    _require(value["synthetic"] is True, "fill.synthetic")
    return value


def parse_disclosures(document: Any) -> list[dict[str, Any]]:
    if not isinstance(document, dict) or set(document) != {"disclosures"}:
        raise InvalidGraphInput("disclosures: expected only disclosures")
    disclosures = document["disclosures"]
    if not isinstance(disclosures, list):
        raise InvalidGraphInput("disclosures: expected a list")
    parsed = [_parse_disclosure(value) for value in disclosures]
    identities = [(value["source"], value["evidence_id"]) for value in parsed]
    if len(set(identities)) != len(identities):
        raise InvalidGraphInput("disclosures: duplicate disclosure")
    return sorted(parsed, key=lambda value: (value["source"], value["evidence_id"]))


def _parse_disclosure(value: Any) -> dict[str, Any]:
    _expected_fields(value, DISCLOSURE_FIELDS, "disclosure")
    _require(value["source"] == "synthetic-disclosures", "disclosure.source")
    _identifier(value["evidence_id"], "disclosure.evidence_id")
    _symbol(value["symbol"], "disclosure.symbol")
    _text(value["title"], "disclosure.title")
    occurred_at = parse_timestamp(value["occurred_at"], "disclosure.occurred_at")
    collected_at = parse_timestamp(value["collected_at"], "disclosure.collected_at")
    _require(collected_at >= occurred_at, "disclosure.collected_at")
    _require(value["synthetic"] is True, "disclosure.synthetic")
    return value


def _trade_id(fill: dict[str, Any]) -> str:
    return f"trade:{fill['source']}:{fill['fill_id']}"


def _fill_evidence_id(fill: dict[str, Any]) -> str:
    return f"evidence:fill:{fill['source']}:{fill['fill_id']}"


def _disclosure_evidence_id(disclosure: dict[str, Any]) -> str:
    return f"evidence:disclosure:{disclosure['source']}:{disclosure['evidence_id']}"


def _no_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    value = {}
    for key, item in pairs:
        if key in value:
            raise DuplicateJsonKey()
        value[key] = item
    return value


def _identifier(value: Any, field: str) -> None:
    _require(isinstance(value, str) and IDENTIFIER.fullmatch(value), field)


def _symbol(value: Any, field: str) -> None:
    _require(isinstance(value, str) and SYMBOL.fullmatch(value), field)


def _positive_integer(value: Any, field: str) -> None:
    _require(
        isinstance(value, int) and not isinstance(value, bool) and 1 <= value <= 2_147_483_647,
        field,
    )


def _text(value: Any, field: str) -> None:
    _require(isinstance(value, str) and value.strip(), field)


def parse_timestamp(value: Any, field: str) -> datetime:
    _require(isinstance(value, str), field)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise InvalidGraphInput(field) from error
    _require(parsed.tzinfo is not None, field)
    return parsed


def _require(condition: bool, field: str) -> None:
    if not condition:
        raise InvalidGraphInput(field)


def _expected_fields(value: Any, expected: set[str], prefix: str) -> None:
    if not isinstance(value, dict):
        raise InvalidGraphInput(prefix)
    missing = expected - set(value)
    unexpected = set(value) - expected
    if missing:
        raise InvalidGraphInput(f"{prefix}.{sorted(missing)[0]}")
    if unexpected:
        raise InvalidGraphInput(f"{prefix}: unexpected field")


if __name__ == "__main__":
    main()
