"""Static typing guarantees of label types, checked by pyright and mypy (never executed)."""

from typing import assert_type

from jev._content import Content
from jev.labels import Levels, NoulCriteria, Options


class Department(Options):
    BILLING = "billing", "Charges, refunds, invoices."
    TECHNICAL = "technical"


class Urgency(Levels):
    CAN_WAIT = 0, "Can wait."
    TODAY = 1, "Needs attention today."


assert_type(Department.BILLING.value, str)
assert_type(Department.BILLING.description, Content | None)
assert_type(Urgency.TODAY.value, int)
assert_type(Urgency.TODAY.description, Content)
assert_type(NoulCriteria(true="yes").true, Content | None)
