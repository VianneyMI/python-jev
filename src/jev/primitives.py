"""TypeSafe's primitives: noul, choice and score.

Each primitive is a class that plays two roles, like a Pydantic model whose class is the schema
and whose instances are the data:

- **The class is the question.** Subclass a primitive and give it instructions, either as the
  class docstring (text) or as an `instructions = ...` class attribute (text, a Pydantic object,
  or any JSON value). Choice options and score levels come from the type parameter.
- **Each instance is an answer.** After a call, its fields hold what Jev returned: `noul` for a
  noul, `choice`, `confidence` and `probabilities` for a choice, `score`, `confidence` and
  `probabilities` for a score.

>>> from jev import Choice, Options
>>> class Department(Options):
...     BILLING = "billing", "Charges, refunds, invoices."
...     OTHER = "other"
>>> class RouteTicket(Choice[Department]):
...     '''Which team should handle this ticket?'''
>>> RouteTicket.question()
{'type': 'choice', 'instructions': 'Which team should handle this ticket?', \
'criteria': {'billing': 'Charges, refunds, invoices.', 'other': None}}

See https://docs.typesafe.ai/primitives.
"""

from __future__ import annotations

import copy
import functools
import inspect
from typing import Annotated, Any, ClassVar, Generic, Literal, TypeAlias, cast, get_args, get_origin

from pydantic import BaseModel, ConfigDict, Field, JsonValue
from typing_extensions import TypeVar

from jev._content import Content, to_wire
from jev.errors import QuestionDefinitionError
from jev.labels import Levels, NoulCriteria, Options

L = TypeVar("L", default=str)
V = TypeVar("V", default=int)

MAX_OPTIONS = 255
MAX_LEVELS = 10


class Primitive(BaseModel):
    """Base class of TypeSafe's primitives: [`Noul`][jev.Noul], [`Choice`][jev.Choice] and
    [`Score`][jev.Score].

    Subclass one of them to declare a question; its instances are the answers.
    """  # noqa: D205

    model_config = ConfigDict(frozen=True, extra="ignore")

    instructions: ClassVar[Content | None] = None
    """The question asked about the state: text, a Pydantic object, or any JSON value.

    Set it as a class attribute, or write text instructions as the class docstring (not both).
    An object or array can put the question in one field and the data it refers to in others.
    """

    @classmethod
    def question(cls) -> dict[str, JsonValue]:
        """Return the question exactly as sent to TypeSafe.

        Raises:
            QuestionDefinitionError: The class is not a valid question.
        """
        return copy.deepcopy(dict(_question(cls)))


class Noul(Primitive):
    """A yes/no question or statement, answered with the probability of yes.

    Declare one by subclassing, with instructions, criteria, or both:

    >>> class IsRefund(Noul):
    ...     '''Does the customer ask for money back?'''
    >>> IsRefund.question()
    {'type': 'noul', 'instructions': 'Does the customer ask for money back?'}

    TypeSafe's guidance: ask one condition per noul and combine answers in code, and phrase the
    question so that a high value means yes. Use a [`Score`][jev.Score], not a noul, for
    questions about degree. See https://docs.typesafe.ai/primitives/noul.
    """

    criteria: ClassVar[NoulCriteria | None] = None
    """Optional description of what counts as a yes and what counts as a no."""

    type: Literal["noul"] = "noul"
    noul: float
    """Probability of a yes answer or a true statement, from 0 to 1.

    Values near 1 favour yes, values near 0 favour no, and values near 0.5 indicate uncertainty.
    A noul value "is not a scale of the thing you asked about" (TypeSafe): 0.9 means "very likely
    yes", not "very much". A noul has no separate `confidence`, because this one number already
    carries the uncertainty; `abs(2 * noul - 1)` gives a confidence on the same scale as a
    choice's. TypeSafe suggests starting with 0.7 for yes and 0.3 for no, then moving the
    thresholds according to the cost of each kind of error.
    """


class Choice(Primitive, Generic[L]):
    """A question that selects one option from the choices you define.

    The type parameter declares the options: an [`Options`][jev.Options] subclass (names and
    optional descriptions) or a `Literal` of strings (names only, each interpreted by its name).

    >>> from typing import Literal
    >>> class Tone(Choice[Literal["calm", "angry"]]):
    ...     '''What is the tone of this message?'''
    >>> Tone.question()["criteria"]
    {'calm': None, 'angry': None}

    The answer is constrained to your options: Jev returns a probability for each of them and
    never a value outside them. See https://docs.typesafe.ai/primitives/choice.
    """

    type: Literal["choice"] = "choice"
    choice: L
    """The option with the highest probability."""
    confidence: float
    """How concentrated `probabilities` is, from 0 (even spread) to 1 (all on one option).

    For n options and the top probability `p_max`, TypeSafe computes
    `(p_max - 1/n) / (1 - 1/n)`, that is `(n * p_max - 1) / (n - 1)`. Only the top probability
    counts: (0.6, 0.3, 0.1) and (0.6, 0.2, 0.2) both give 0.4. See
    https://docs.typesafe.ai/confidence#choice.
    """
    probabilities: dict[L, float]
    """Probability of each option, keyed by option; values sum to approximately 1."""


class Score(Primitive, Generic[V]):
    """A question that rates the state against ordered levels.

    The type parameter declares the levels: a [`Levels`][jev.Levels] subclass whose members run
    from 0 (low end) to n - 1 (high end), each with a description.

    Use a score when the answer falls on a spectrum and you can describe each point of it.
    See https://docs.typesafe.ai/primitives/score.
    """

    type: Literal["score"] = "score"
    score: float
    """Expected level: the probability-weighted average of the levels, from 0 to n - 1.

    It is a position along your levels, not a level: it can fall between two of them. With
    probabilities (0, 0.53, 0.47) over three levels, `score` is 1.47. Read `probabilities` for the
    distribution.
    """
    confidence: float
    """How concentrated `probabilities` is around the most likely level, from 0 to 1.

    For n levels with probabilities `p_i` and most likely level `m`, TypeSafe computes
    `max(0, 1 - sum(p_i * |i - m|) / MAD)`, where `MAD = (1/n) * sum(|i - (n - 1)/2|)` is the same
    average distance for an even spread. Probability on a neighbouring level lowers confidence
    less than probability far away: over three levels, (0, 0.5, 0.5) gives 0.25 and
    (0.5, 0, 0.5) gives 0. See https://docs.typesafe.ai/confidence#score.
    """
    probabilities: dict[V, float]
    """Probability of each level, keyed by level; values sum to approximately 1."""


Question: TypeAlias = type[Primitive]
"""A question: a subclass of [`Noul`][jev.Noul], [`Choice`][jev.Choice] or [`Score`][jev.Score]."""

Answer: TypeAlias = Annotated[Noul | Choice[Any] | Score[Any], Field(discriminator="type")]
"""An answer to a question given in a mapping: an instance of that question class."""

_BASES: frozenset[type[Primitive]] = frozenset({Primitive, Noul, Choice, Score})


def _is_library_class(cls: type) -> bool:
    if cls in _BASES or not issubclass(cls, Primitive):
        return True
    metadata = cls.__pydantic_generic_metadata__
    return metadata["origin"] is not None


def _instructions(cls: type[Primitive]) -> Content | None:
    """Return the instructions declared on `cls` or the nearest user-defined base class."""
    for klass in cls.__mro__:
        if _is_library_class(klass):
            continue
        doc = klass.__dict__.get("__doc__")
        attribute = klass.__dict__.get("instructions")
        if doc and attribute is not None:
            raise QuestionDefinitionError(
                f"{klass.__name__} sets both a docstring and `instructions`; use one of them"
            )
        if attribute is not None:
            return cast(Content, attribute)
        if doc:
            return inspect.cleandoc(doc)
    return None


def _type_argument(cls: type[Primitive], origin: type[Primitive]) -> Any:
    for klass in cls.__mro__:
        metadata: dict[str, Any] | None = getattr(klass, "__pydantic_generic_metadata__", None)
        if metadata and metadata["origin"] is origin and metadata["args"]:
            return metadata["args"][0]
    raise QuestionDefinitionError(
        f"{cls.__name__} must parametrize {origin.__name__}, e.g. {origin.__name__}[MyLabels]"
    )


def _choice_criteria(cls: type[Primitive]) -> dict[str, JsonValue]:
    labels = _type_argument(cls, Choice)
    if isinstance(labels, type) and issubclass(labels, Options):
        criteria: dict[str, JsonValue] = {
            member.value: to_wire(member.description) for member in labels
        }
    elif get_origin(labels) is Literal and all(isinstance(arg, str) for arg in get_args(labels)):
        criteria = dict.fromkeys(get_args(labels))
    else:
        raise QuestionDefinitionError(
            f"{cls.__name__}: choice options must be an Options subclass or a Literal of strings, "
            f"got {labels!r}"
        )
    if not 1 <= len(criteria) <= MAX_OPTIONS:
        raise QuestionDefinitionError(
            f"{cls.__name__}: a choice takes 1 to {MAX_OPTIONS} options, got {len(criteria)}"
        )
    return criteria


def _score_criteria(cls: type[Primitive]) -> list[JsonValue]:
    levels = _type_argument(cls, Score)
    if not (isinstance(levels, type) and issubclass(levels, Levels)):
        raise QuestionDefinitionError(
            f"{cls.__name__}: score levels must be a Levels subclass, got {levels!r}"
        )
    members: list[Levels] = sorted(levels, key=lambda member: member.value)
    if not 1 <= len(members) <= MAX_LEVELS:
        raise QuestionDefinitionError(
            f"{cls.__name__}: a score takes 1 to {MAX_LEVELS} levels, got {len(members)}"
        )
    if [member.value for member in members] != list(range(len(members))):
        raise QuestionDefinitionError(
            f"{cls.__name__}: levels of {levels.__name__} must run from 0 to "
            f"{len(members) - 1} without gaps, got {[member.value for member in members]}"
        )
    for member in members:
        if member.description is None or member.description == "":
            raise QuestionDefinitionError(
                f"{cls.__name__}: level {levels.__name__}.{member.name} needs a description"
            )
    return [to_wire(member.description) for member in members]


@functools.cache
def _question(cls: type[Primitive]) -> tuple[tuple[str, JsonValue], ...]:
    if cls in _BASES:
        raise QuestionDefinitionError(
            f"{cls.__name__} is a base class; subclass it to declare a question"
        )
    instructions = _instructions(cls)
    declared: type[Primitive] = cls
    question: dict[str, JsonValue] = {}
    if issubclass(cls, Noul):
        question["type"] = "noul"
        criteria = cls.criteria
        described = criteria is not None and (
            criteria.true is not None or criteria.false is not None
        )
        if instructions is None and not described:
            raise QuestionDefinitionError(
                f"{cls.__name__}: a noul needs instructions or criteria describing an outcome"
            )
        if instructions is not None:
            question["instructions"] = to_wire(instructions)
        if criteria is not None and described:
            question["criteria"] = {
                key: to_wire(value)
                for key, value in (("true", criteria.true), ("false", criteria.false))
                if value is not None
            }
    elif issubclass(cls, Choice):
        question["type"] = "choice"
        if instructions is not None:
            question["instructions"] = to_wire(instructions)
        question["criteria"] = _choice_criteria(declared)
    elif issubclass(cls, Score):
        question["type"] = "score"
        if instructions is not None:
            question["instructions"] = to_wire(instructions)
        question["criteria"] = _score_criteria(declared)
    else:
        raise QuestionDefinitionError(
            f"{cls.__name__} must subclass Noul, Choice or Score, not Primitive directly"
        )
    return tuple(question.items())


__all__ = ["Answer", "Choice", "Noul", "Primitive", "Question", "Score"]
