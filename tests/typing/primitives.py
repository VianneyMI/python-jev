"""Static typing guarantees of answers, checked by pyright and mypy (never executed).

`reportUnnecessaryTypeIgnoreComment` (pyright) and `warn_unused_ignores` (mypy strict) turn each
`type: ignore` below into an assertion that the line is a type error.
"""
# pyright: reportUnnecessaryTypeIgnoreComment=true

from typing import Literal, assert_type

from pydantic import BaseModel

from jev import Choice, Levels, Noul, Options, Score


class Department(Options):
    BILLING = "billing", "Charges, refunds, invoices."
    OTHER = "other"


class Urgency(Levels):
    CAN_WAIT = 0, "Can wait."
    TODAY = 1, "Needs attention today."


class RouteTicket(Choice[Department]):
    """Which team should handle this ticket?"""


class Tone(Choice[Literal["calm", "angry"]]):
    """What is the tone of this message?"""


class HowUrgent(Score[Urgency]):
    """How urgent is this ticket?"""


class IsRefund(Noul):
    """Does the customer ask for money back?"""


class Triage(BaseModel):
    department: RouteTicket
    tone: Tone
    urgency: HowUrgent
    refund: IsRefund


def answers(triage: Triage) -> None:
    assert_type(triage.department.choice, Department)
    assert_type(triage.department.probabilities, dict[Department, float])
    assert_type(triage.department.confidence, float)
    assert_type(triage.tone.choice, Literal["calm", "angry"])
    assert_type(triage.urgency.score, float)
    assert_type(triage.urgency.probabilities, dict[Urgency, float])
    assert_type(triage.refund.noul, float)


def mistakes(triage: Triage) -> None:
    _level: Urgency = triage.department.choice  # type: ignore[assignment]
    _label: Department = triage.urgency.score  # type: ignore[assignment]
    _confidence: float = triage.refund.confidence  # type: ignore[attr-defined]
