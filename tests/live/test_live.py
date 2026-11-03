"""Calls against the real TypeSafe API: `uv run pytest -m live` (needs TYPESAFE_API_KEY)."""

import pytest
from pydantic import BaseModel
from questions import (
    ChurnRisk,
    Department,
    Eligible,
    HowFrustrated,
    HowUrgent,
    IsRefund,
    RepeatContact,
    RouteTicket,
    Sentiment,
    StructuredHowUrgent,
    StructuredRouteTicket,
    Urgency,
)

from jev import AsyncJev, AuthenticationError, Jev

pytestmark = pytest.mark.live

TICKET = (
    "Hi, I was charged twice for my October invoice (INV-2291). "
    "Please refund the duplicate charge as soon as possible, this is the second time I write."
)


class Triage(BaseModel):
    refund: IsRefund
    repeat_contact: RepeatContact
    department: RouteTicket
    sentiment: Sentiment
    urgency: HowUrgent


class Message(BaseModel):
    sender: str
    text: str


class Thread(BaseModel):
    subject: str
    messages: list[Message]


def test_questionnaire_with_every_primitive(jev: Jev) -> None:
    res = jev.evaluate(TICKET, Triage)
    assert res.answers.refund.noul > 0.5
    assert res.answers.department.choice is Department.BILLING
    assert set(res.answers.urgency.probabilities) == set(Urgency)
    assert res.answers.sentiment.choice in ("positive", "neutral", "negative")
    assert res.model.startswith("jev-")
    assert res.request_id


def test_mapping_of_questions(jev: Jev) -> None:
    res = jev.evaluate(TICKET, {"refund": IsRefund, "urgency": HowUrgent})
    assert isinstance(res.answers["refund"], IsRefund)
    assert isinstance(res.answers["urgency"], HowUrgent)


def test_structured_inputs(jev: Jev) -> None:
    thread = Thread(
        subject="Duplicate charge",
        messages=[
            Message(sender="customer", text="I was charged twice for October."),
            Message(sender="customer", text="Refund me now or I cancel."),
        ],
    )
    res = jev.evaluate(
        {"ticket": thread, "policy": {"refund_window_days": 30, "auto_refund_duplicates": True}},
        {
            "churn_risk": ChurnRisk,
            "frustration": HowFrustrated,
            "eligible": Eligible,
            "department": StructuredRouteTicket,
            "urgency": StructuredHowUrgent,
        },
    )
    assert set(res.answers) == {"churn_risk", "frustration", "eligible", "department", "urgency"}


def test_invalid_key() -> None:
    with Jev(api_key="ts-invalid-key") as client, pytest.raises(AuthenticationError):
        client.evaluate(TICKET, {"refund": IsRefund})


@pytest.mark.anyio
async def test_async_questionnaire(async_jev: AsyncJev) -> None:
    res = await async_jev.evaluate(TICKET, Triage)
    assert res.answers.department.choice is Department.BILLING
