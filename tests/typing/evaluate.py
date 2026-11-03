"""Static typing guarantees of `evaluate`, checked by pyright and mypy (never executed).

One overload-free signature types both layers: a questionnaire model gives `Result[Model]`, and a
mapping of questions leaves `T` unsolved, so it falls back to its default, `dict[str, Answer]`.
"""
# pyright: reportUnnecessaryTypeIgnoreComment=true

from typing import assert_type

from pydantic import BaseModel

from jev import Answer, AsyncJev, Jev, Noul, Options, Result
from jev import Choice as ChoiceBase


class Department(Options):
    BILLING = "billing"
    OTHER = "other"


class RouteTicket(ChoiceBase[Department]):
    """Which team should handle this ticket?"""


class IsRefund(Noul):
    """Does the customer ask for money back?"""


class Triage(BaseModel):
    department: RouteTicket
    refund: IsRefund


def sync_calls(client: Jev) -> None:
    res = client.evaluate("text", Triage)
    assert_type(res, Result[Triage])
    assert_type(res.answers.department.choice, Department)

    adhoc = client.evaluate("text", {"refund": IsRefund, "department": RouteTicket})
    assert_type(adhoc, Result[dict[str, Answer]])
    assert_type(adhoc.answers["refund"], Answer)


async def async_calls(client: AsyncJev) -> None:
    res = await client.evaluate({"subject": "Refund"}, Triage)
    assert_type(res, Result[Triage])
    adhoc = await client.evaluate("text", {"refund": IsRefund})
    assert_type(adhoc, Result[dict[str, Answer]])


def mistakes(client: Jev) -> None:
    client.evaluate("text", {"refund": "IsRefund"})  # type: ignore[dict-item]
    client.evaluate("text", Triage, model=1)  # type: ignore[arg-type]
