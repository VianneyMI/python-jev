"""Label types: the options of a choice, the levels of a score, and the outcomes of a noul."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum, StrEnum
from typing import Self

from jev._content import Content


class Options(StrEnum):
    """Base class for the options of a [`Choice`][jev.Choice].

    Each member is one option. Its value is the option's name, as sent to TypeSafe and returned
    in `choice` and `probabilities`. An optional second item describes when the option applies;
    TypeSafe interprets an option without a description by its name alone.

    >>> class Department(Options):
    ...     BILLING = "billing", "Charges, refunds, invoices."
    ...     TECHNICAL = "technical"
    >>> Department.BILLING.value, Department.BILLING.description
    ('billing', 'Charges, refunds, invoices.')
    >>> Department.TECHNICAL.description is None
    True

    A choice takes between 1 and 255 options. Descriptions can be text, a Pydantic object, or
    any JSON value. See https://docs.typesafe.ai/primitives/choice.
    """

    _value_: str
    description: Content | None
    """When this option applies, or `None` to let TypeSafe interpret the option by its name."""

    def __new__(cls, value: str, description: Content | None = None) -> Self:  # noqa: D102
        member = str.__new__(cls, value)
        member._value_ = value
        member.description = description
        return member


class Levels(IntEnum):
    """Base class for the levels of a [`Score`][jev.Score].

    Each member is one level: an integer position, from 0 for the low end of the scale, and a
    required description of what that level means. TypeSafe numbers levels by their position,
    so the values must run from 0 to n - 1 without gaps.

    >>> class Urgency(Levels):
    ...     CAN_WAIT = 0, "Can wait."
    ...     THIS_WEEK = 1, "Needs attention this week."
    ...     TODAY = 2, "Needs attention today."
    >>> Urgency.TODAY.value, Urgency.TODAY.description
    (2, 'Needs attention today.')

    "The model gets the descriptions and nothing else, and each level is judged on its own
    against the state" (TypeSafe). A score takes between 1 and 10 levels; TypeSafe recommends at
    least two. See https://docs.typesafe.ai/primitives/score#levels.
    """

    _value_: int
    description: Content
    """What this level means. The model reads only this description, not the member name."""

    def __new__(cls, value: int, description: Content) -> Self:  # noqa: D102
        member = int.__new__(cls, value)
        member._value_ = value
        member.description = description
        return member


@dataclass(frozen=True)
class NoulCriteria:
    """What counts as a yes and what counts as a no for a [`Noul`][jev.Noul].

    Optional. A noul needs instructions, or criteria describing at least one outcome.

    >>> NoulCriteria(true="Unsolicited advertising", false="A legitimate conversation")
    NoulCriteria(true='Unsolicited advertising', false='A legitimate conversation')

    See https://docs.typesafe.ai/primitives/noul.
    """

    true: Content | None = None
    """What counts as a yes answer."""
    false: Content | None = None
    """What counts as a no answer."""
