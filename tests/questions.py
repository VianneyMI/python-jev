"""Question classes matching the scenarios recorded by scripts/record_fixtures.py."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from jev import Choice, Levels, Noul, NoulCriteria, Options, Primitive, Score


class IsRefund(Noul):
    """Does the customer ask for money back?"""


class RepeatContact(Noul):
    """Has the customer contacted support before about this?"""

    criteria = NoulCriteria(
        true="Mentions a prior attempt, ticket, or that they have written before",
        false="No sign of any previous contact",
    )


class Department(Options):
    BILLING = "billing", "Charges, refunds, invoices."
    TECHNICAL = "technical", "Bugs, outages, integrations."
    OTHER = "other"


class RouteTicket(Choice[Department]):
    """Which team should handle this ticket?"""


Tone = Literal["positive", "neutral", "negative"]


class Sentiment(Choice[Tone]):
    """What is the tone of this message?"""


class Urgency(Levels):
    CAN_WAIT = 0, "Can wait."
    THIS_WEEK = 1, "Needs attention this week."
    TODAY = 2, "Needs attention today."


class HowUrgent(Score[Urgency]):
    """How urgent is this ticket?"""


class Frustration(Levels):
    NONE = 0, "Not frustrated at all."
    SLIGHT = 1, "Slightly annoyed."
    CLEAR = 2, "Clearly frustrated."
    VERY = 3, "Very frustrated."
    FURIOUS = 4, "Furious, threatening to leave."


class HowFrustrated(Score[Frustration]):
    """How frustrated is the customer?"""


class ChurnRisk(Noul):
    """Does the last customer message in `ticket.messages` threaten to cancel?"""


class EligibilityTask(BaseModel):
    question: str
    policy_field: str
    consider: list[str]


class Eligible(Noul):
    instructions = EligibilityTask(
        question="Is this refund request eligible under the policy?",
        policy_field="policy",
        consider=["refund_window_days", "auto_refund_duplicates"],
    )


class Handles(BaseModel):
    handles: list[str]


class StructuredDepartment(Options):
    BILLING = "billing", Handles(handles=["charges", "refunds", "invoices"])
    TECHNICAL = "technical", Handles(handles=["bugs", "outages"])
    OTHER = "other"


class StructuredRouteTicket(Choice[StructuredDepartment]):
    """Which team should handle this ticket?"""


class LevelSpec(BaseModel):
    label: str
    meaning: str


class StructuredUrgency(Levels):
    LOW = 0, LevelSpec(label="low", meaning="Can wait.")
    MEDIUM = 1, LevelSpec(label="medium", meaning="Needs attention this week.")
    HIGH = 2, LevelSpec(label="high", meaning="Needs attention today.")


class StructuredHowUrgent(Score[StructuredUrgency]):
    """How urgent is this ticket?"""


class Signals(BaseModel):
    signals: list[str]


class StructuredIsRefund(Noul):
    """Does the customer ask for money back?"""

    criteria = NoulCriteria(true=Signals(signals=["refund", "chargeback", "money back"]))


SCENARIOS: dict[str, dict[str, type[Primitive]]] = {
    "noul_plain": {"refund": IsRefund},
    "noul_criteria": {"repeat_contact": RepeatContact},
    "choice_described": {"department": RouteTicket},
    "choice_names_only": {"sentiment": Sentiment},
    "score_3": {"urgency": HowUrgent},
    "score_5": {"frustration": HowFrustrated},
    "combined": {
        "refund": IsRefund,
        "repeat_contact": RepeatContact,
        "department": RouteTicket,
        "sentiment": Sentiment,
        "urgency": HowUrgent,
        "frustration": HowFrustrated,
    },
    "state_object": {"refund": IsRefund, "urgency": HowUrgent},
    "state_array": {"repeat_contact": RepeatContact, "sentiment": Sentiment},
    "state_nested": {"churn_risk": ChurnRisk, "frustration": HowFrustrated},
    "structured_instructions": {"eligible": Eligible},
    "structured_criteria": {
        "department": StructuredRouteTicket,
        "urgency": StructuredHowUrgent,
        "refund": StructuredIsRefund,
    },
}
