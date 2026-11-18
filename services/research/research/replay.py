import re
from dataclasses import dataclass
from datetime import date
from typing import Any
from zoneinfo import ZoneInfo

from .graph_builder import (
    SYMBOL,
    build_graph,
    parse_disclosures,
    parse_fills,
    parse_timestamp,
)

SEOUL = ZoneInfo("Asia/Seoul")
DATE_PATTERN = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
REQUEST_FIELDS = {"symbol", "from_date", "as_of", "question", "fills", "position_quantity"}
TRADE_FIELDS = ("side", "quantity", "price_krw")


@dataclass(frozen=True)
class ReplayQuestion:
    symbol: str
    from_date: date
    as_of: date
    question: str
    fills: list[dict[str, Any]]
    position_quantity: int

    def includes(self, record: dict, occurred_field: str) -> bool:
        occurred = parse_timestamp(record[occurred_field], occurred_field).astimezone(SEOUL).date()
        collected = parse_timestamp(record["collected_at"], "collected_at").astimezone(SEOUL).date()
        return (
            record["symbol"] == self.symbol
            and self.from_date <= occurred <= collected <= self.as_of
        )

    def model_input(self, disclosures: dict) -> dict:
        known = [row for row in parse_disclosures(disclosures) if self.includes(row, "occurred_at")]
        graph = build_graph({"fills": self.fills}, {"disclosures": known})
        nodes = {node["id"]: node for node in graph["nodes"]}
        trades = {
            edge["to"]: nodes[edge["from"]]
            for edge in graph["relationships"]
            if edge["kind"] == "HAS_EVIDENCE"
        }
        records = []
        for node in sorted(graph["nodes"], key=lambda node: (node["id"] not in trades, node["id"])):
            if node["kind"] != "evidence":
                continue
            trade = trades.get(node["id"])
            record = {
                "id": node["id"],
                "kind": "fill" if trade else "disclosure",
                "source": node["source"],
                "reference_id": node["evidence_id"],
                "occurred_at": node["occurred_at"],
                "collected_at": node["collected_at"],
            }
            if trade:
                record.update({key: trade[key] for key in TRADE_FIELDS})
            else:
                record["title"] = node["title"]
            records.append(record)
        return {
            "symbol": self.symbol,
            "from_date": self.from_date.isoformat(),
            "as_of": self.as_of.isoformat(),
            "question": self.question,
            "position_quantity": self.position_quantity,
            "records": records,
        }


def parse_replay_question(value: Any) -> ReplayQuestion:
    if not isinstance(value, dict) or set(value) != REQUEST_FIELDS:
        raise ValueError()
    if not isinstance(value["symbol"], str) or not SYMBOL.fullmatch(value["symbol"]):
        raise ValueError()
    start = _parse_date(value["from_date"])
    end = _parse_date(value["as_of"])
    if start > end:
        raise ValueError()
    question = value["question"]
    if not isinstance(question, str) or not question.strip() or len(question) > 500:
        raise ValueError()
    question.encode("utf-8")
    position = value["position_quantity"]
    if type(position) is not int or not -(2**63) <= position <= 2**63 - 1:
        raise ValueError()
    fills = parse_fills({"fills": value["fills"]})
    request = ReplayQuestion(value["symbol"], start, end, question, fills, position)
    if not all(request.includes(fill, "filled_at") for fill in fills):
        raise ValueError()
    return request


def validate_answer(result: Any, records: list[dict]) -> dict:
    if not isinstance(result, dict) or set(result) != {"status", "answer", "evidence_ids"}:
        raise ValueError()
    status = result["status"]
    answer = result["answer"]
    ids = result["evidence_ids"]
    if status == "insufficient_evidence" and answer == "" and ids == []:
        return {"status": status, "answer": answer, "evidence": []}
    if status != "answered" or not isinstance(answer, str) or not answer.strip():
        raise ValueError()
    by_id = {record["id"]: record for record in records}
    if (
        not isinstance(ids, list)
        or not ids
        or any(not isinstance(item, str) or item not in by_id for item in ids)
    ):
        raise ValueError()
    if len(ids) != len(set(ids)):
        raise ValueError()
    return {
        "status": status,
        "answer": answer,
        "evidence": [
            {key: value for key, value in by_id[item].items() if key not in TRADE_FIELDS}
            for item in ids
        ],
    }


def _parse_date(value: Any) -> date:
    if not isinstance(value, str) or not DATE_PATTERN.fullmatch(value):
        raise ValueError()
    return date.fromisoformat(value)
