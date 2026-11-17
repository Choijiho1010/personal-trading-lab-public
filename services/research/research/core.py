from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict


class InvalidResearchQuestion(ValueError):
    pass


@dataclass(frozen=True)
class Evidence:
    fill_id: str
    symbol: str
    side: str
    quantity: int
    filled_at: str


@dataclass(frozen=True)
class ResearchQuestion:
    question: str
    evidence: Evidence


def parse_research_question(value: Any) -> ResearchQuestion:
    if not isinstance(value, dict) or set(value) != {"question", "evidence"}:
        raise InvalidResearchQuestion()
    question = value["question"]
    if not isinstance(question, str) or not 1 <= len(question) <= 500 or not question.strip():
        raise InvalidResearchQuestion()
    evidence = value["evidence"]
    if not isinstance(evidence, dict) or set(evidence) != {
        "fill_id",
        "symbol",
        "side",
        "quantity",
        "filled_at",
    }:
        raise InvalidResearchQuestion()
    fill_id = evidence["fill_id"]
    symbol = evidence["symbol"]
    side = evidence["side"]
    quantity = evidence["quantity"]
    filled_at = evidence["filled_at"]
    if not isinstance(fill_id, str) or not fill_id:
        raise InvalidResearchQuestion()
    if not isinstance(symbol, str) or not symbol:
        raise InvalidResearchQuestion()
    if side != "BUY" or isinstance(quantity, bool) or not isinstance(quantity, int) or quantity < 1:
        raise InvalidResearchQuestion()
    if not isinstance(filled_at, str) or not _is_datetime_with_timezone(filled_at):
        raise InvalidResearchQuestion()
    return ResearchQuestion(
        question=question,
        evidence=Evidence(
            fill_id=fill_id,
            symbol=symbol,
            side=side,
            quantity=quantity,
            filled_at=filled_at,
        ),
    )


def answer(question: ResearchQuestion) -> Dict[str, Any]:
    return {
        "answer": f"{question.evidence.quantity}주를 매수했습니다.",
        "evidence_ids": [question.evidence.fill_id],
    }


def _is_datetime_with_timezone(value: str) -> bool:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None
