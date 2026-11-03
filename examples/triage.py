"""Triage a support ticket with Jev: one call, three primitives, typed answers.

Run with `uv run python examples/triage.py` and TYPESAFE_API_KEY set (or in a .env file).
"""

from dotenv import find_dotenv, load_dotenv
from pydantic import BaseModel

import jev


class Department(jev.Options):
    BILLING = "billing", "Charges, refunds, invoices."
    TECHNICAL = "technical", "Bugs, outages, integrations."
    OTHER = "other"


class Urgency(jev.Levels):
    CAN_WAIT = 0, "Can wait."
    THIS_WEEK = 1, "Needs attention this week."
    TODAY = 2, "Needs attention today."


class RouteTicket(jev.Choice[Department]):
    """Which team should handle this ticket?"""


class HowUrgent(jev.Score[Urgency]):
    """How urgent is this ticket?"""


class IsRefund(jev.Noul):
    """Does the customer ask for money back?"""

    criteria = jev.NoulCriteria(true="Explicitly asks for a refund or a chargeback")


class Triage(BaseModel):
    department: RouteTicket
    urgency: HowUrgent
    refund: IsRefund


class Message(BaseModel):
    sender: str
    text: str


def main() -> None:
    load_dotenv(find_dotenv(usecwd=True))
    ticket = {
        "subject": "Duplicate charge",
        "messages": [
            Message(sender="customer", text="I was charged twice for my October invoice."),
            Message(sender="customer", text="Please refund the duplicate charge today."),
        ],
    }
    with jev.Jev() as client:
        res = client.evaluate(ticket, Triage)

    answers = res.answers
    print(f"model: {res.model}, input tokens: {res.usage.input_tokens}")
    print(
        f"department: {answers.department.choice.name} (confidence {answers.department.confidence})"
    )
    print(f"urgency: expected level {answers.urgency.score} of {len(Urgency) - 1}")
    for level, probability in answers.urgency.probabilities.items():
        print(f"  {level.name:<9} {probability:.2f}  {level.description}")
    print(f"refund requested: p(yes) = {answers.refund.noul}")


if __name__ == "__main__":
    main()
