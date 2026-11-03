"""Record live TypeSafe API responses into tests/fixtures/responses.

Uses raw httpx2, not the SDK, so the fixtures describe the API independently of this package.
Needs TYPESAFE_API_KEY (read from the environment or the nearest .env file).

    uv run python scripts/record_fixtures.py            # record every scenario
    uv run python scripts/record_fixtures.py score_3    # record selected scenarios
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import httpx2
from dotenv import find_dotenv, load_dotenv

API_URL = "https://api.typesafe.ai/v1/systemone"
OUT = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "responses"
KEPT_HEADERS = ("content-type", "x-typesafe-request-id", "retry-after", "retry-after-ms")

TICKET = (
    "Hi, I was charged twice for my October invoice (INV-2291). "
    "Please refund the duplicate charge as soon as possible, this is the second time I write."
)

NOUL_REFUND: dict[str, Any] = {
    "type": "noul",
    "instructions": "Does the customer ask for money back?",
}
NOUL_REPEAT: dict[str, Any] = {
    "type": "noul",
    "instructions": "Has the customer contacted support before about this?",
    "criteria": {
        "true": "Mentions a prior attempt, ticket, or that they have written before",
        "false": "No sign of any previous contact",
    },
}
CHOICE_DEPARTMENT: dict[str, Any] = {
    "type": "choice",
    "instructions": "Which team should handle this ticket?",
    "criteria": {
        "billing": "Charges, refunds, invoices.",
        "technical": "Bugs, outages, integrations.",
        "other": None,
    },
}
CHOICE_SENTIMENT: dict[str, Any] = {
    "type": "choice",
    "instructions": "What is the tone of this message?",
    "criteria": {"positive": None, "neutral": None, "negative": None},
}
SCORE_URGENCY: dict[str, Any] = {
    "type": "score",
    "instructions": "How urgent is this ticket?",
    "criteria": ["Can wait.", "Needs attention this week.", "Needs attention today."],
}
SCORE_FRUSTRATION: dict[str, Any] = {
    "type": "score",
    "instructions": "How frustrated is the customer?",
    "criteria": [
        "Not frustrated at all.",
        "Slightly annoyed.",
        "Clearly frustrated.",
        "Very frustrated.",
        "Furious, threatening to leave.",
    ],
}

STATE_OBJECT: dict[str, Any] = {
    "subject": "Duplicate charge",
    "message": TICKET,
    "customer": {"plan": "pro", "tenure_months": 14},
}
STATE_ARRAY: list[Any] = [
    "Hi, my card was charged twice for October.",
    "I already wrote last week and nobody answered.",
    "Please refund the duplicate charge.",
]
STATE_NESTED: dict[str, Any] = {
    "ticket": {
        "subject": "Duplicate charge",
        "messages": [
            {"from": "customer", "text": "I was charged twice for October."},
            {"from": "agent", "text": "Sorry about that, we are looking into it."},
            {"from": "customer", "text": "It has been a week. Refund me now or I cancel."},
        ],
    },
    "policy": {"refund_window_days": 30, "auto_refund_duplicates": True},
}


def nested(depth: int) -> Any:
    value: Any = "leaf"
    for _ in range(depth):
        value = {"next": value}
    return value


SCENARIOS: dict[str, dict[str, Any]] = {
    "noul_plain": {"state": TICKET, "questions": {"refund": NOUL_REFUND}},
    "noul_criteria": {"state": TICKET, "questions": {"repeat_contact": NOUL_REPEAT}},
    "choice_described": {"state": TICKET, "questions": {"department": CHOICE_DEPARTMENT}},
    "choice_names_only": {"state": TICKET, "questions": {"sentiment": CHOICE_SENTIMENT}},
    "score_3": {"state": TICKET, "questions": {"urgency": SCORE_URGENCY}},
    "score_5": {"state": TICKET, "questions": {"frustration": SCORE_FRUSTRATION}},
    "combined": {
        "state": TICKET,
        "questions": {
            "refund": NOUL_REFUND,
            "repeat_contact": NOUL_REPEAT,
            "department": CHOICE_DEPARTMENT,
            "sentiment": CHOICE_SENTIMENT,
            "urgency": SCORE_URGENCY,
            "frustration": SCORE_FRUSTRATION,
        },
    },
    "state_object": {
        "state": STATE_OBJECT,
        "questions": {"refund": NOUL_REFUND, "urgency": SCORE_URGENCY},
    },
    "state_array": {
        "state": STATE_ARRAY,
        "questions": {"repeat_contact": NOUL_REPEAT, "sentiment": CHOICE_SENTIMENT},
    },
    "state_nested": {
        "state": STATE_NESTED,
        "questions": {
            "churn_risk": {
                "type": "noul",
                "instructions": (
                    "Does the last customer message in `ticket.messages` threaten to cancel?"
                ),
            },
            "frustration": SCORE_FRUSTRATION,
        },
    },
    "structured_instructions": {
        "state": STATE_NESTED,
        "questions": {
            "eligible": {
                "type": "noul",
                "instructions": {
                    "question": "Is this refund request eligible under the policy?",
                    "policy_field": "policy",
                    "consider": ["refund_window_days", "auto_refund_duplicates"],
                },
            },
        },
    },
    "structured_criteria": {
        "state": TICKET,
        "questions": {
            "department": {
                "type": "choice",
                "instructions": "Which team should handle this ticket?",
                "criteria": {
                    "billing": {"handles": ["charges", "refunds", "invoices"]},
                    "technical": {"handles": ["bugs", "outages"]},
                    "other": None,
                },
            },
            "urgency": {
                "type": "score",
                "instructions": "How urgent is this ticket?",
                "criteria": [
                    {"label": "low", "meaning": "Can wait."},
                    {"label": "medium", "meaning": "Needs attention this week."},
                    {"label": "high", "meaning": "Needs attention today."},
                ],
            },
            "refund": {
                "type": "noul",
                "instructions": "Does the customer ask for money back?",
                "criteria": {"true": {"signals": ["refund", "chargeback", "money back"]}},
            },
        },
    },
    "err_401": {"state": TICKET, "questions": {"refund": NOUL_REFUND}, "_key": "ts-invalid-key"},
    "err_422_choice_without_criteria": {
        "state": TICKET,
        "questions": {"department": {"type": "choice", "instructions": "Which team?"}},
    },
    "err_400_unknown_type": {
        "state": TICKET,
        "questions": {"amount": {"type": "number", "instructions": "How much?"}},
    },
    "err_400_nesting": {"state": nested(70), "questions": {"refund": NOUL_REFUND}},
}


def record(name: str, scenario: dict[str, Any], api_key: str) -> None:
    body = {key: value for key, value in scenario.items() if not key.startswith("_")}
    body = {"model": "jev-latest", **body}
    key = scenario.get("_key", api_key)
    response = httpx2.post(
        API_URL,
        json=body,
        headers={"Authorization": f"Bearer {key}", "User-Agent": "python-jev-fixtures"},
        timeout=60.0,
    )
    try:
        payload: Any = response.json()
    except ValueError:
        payload = response.text
    recording = {
        "status": response.status_code,
        "headers": {k: v for k, v in response.headers.items() if k.lower() in KEPT_HEADERS},
        "request": body,
        "response": payload,
    }
    (OUT / f"{name}.json").write_text(json.dumps(recording, indent=2, ensure_ascii=False) + "\n")
    print(f"{name}: {response.status_code}")


def main(names: list[str]) -> None:
    load_dotenv(find_dotenv(usecwd=True))
    api_key = os.environ.get("TYPESAFE_API_KEY")
    if not api_key:
        sys.exit("TYPESAFE_API_KEY is not set")
    OUT.mkdir(parents=True, exist_ok=True)
    for name in names or list(SCENARIOS):
        record(name, SCENARIOS[name], api_key)


if __name__ == "__main__":
    main(sys.argv[1:])
