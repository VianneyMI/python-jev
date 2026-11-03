from typing import Any, Literal, cast

import pytest
from pydantic import ValidationError
from questions import (
    SCENARIOS,
    Department,
    HowUrgent,
    IsRefund,
    RouteTicket,
    Sentiment,
    Urgency,
)
from recorded import answers, questions, successes

from jev import (
    Choice,
    Levels,
    Noul,
    NoulCriteria,
    Options,
    Primitive,
    QuestionDefinitionError,
    Score,
)

# The API rounds answers to two decimals, so recomputed confidences can differ by about 0.01.
ROUNDING = 0.011

SCENARIO_QUESTIONS = [
    (scenario, name, cls)
    for scenario, entries in SCENARIOS.items()
    for name, cls in entries.items()
]


def test_every_success_recording_has_question_classes() -> None:
    assert sorted(SCENARIOS) == successes()


@pytest.mark.parametrize(("scenario", "name", "cls"), SCENARIO_QUESTIONS)
def test_question_matches_the_recorded_request(
    scenario: str, name: str, cls: type[Primitive]
) -> None:
    assert cls.question() == questions(scenario)[name]


@pytest.mark.parametrize(("scenario", "name", "cls"), SCENARIO_QUESTIONS)
def test_recorded_answer_parses(scenario: str, name: str, cls: type[Primitive]) -> None:
    answer = cls.model_validate(answers(scenario)[name])
    assert isinstance(answer, cls)


def test_choice_answer_uses_the_declared_options() -> None:
    answer = RouteTicket.model_validate(answers("choice_described")["department"])
    assert answer.choice is Department.BILLING
    assert set(answer.probabilities) == set(Department)


def test_choice_answer_with_literal_options() -> None:
    answer = Sentiment.model_validate(answers("choice_names_only")["sentiment"])
    assert answer.choice in ("positive", "neutral", "negative")


def test_score_answer_keys_are_levels() -> None:
    answer = HowUrgent.model_validate(answers("score_3")["urgency"])
    assert list(answer.probabilities) == list(Urgency)
    assert all(isinstance(level, Urgency) for level in answer.probabilities)
    assert 0 <= answer.score <= 2


def test_noul_answer() -> None:
    answer = IsRefund.model_validate(answers("noul_plain")["refund"])
    assert 0 <= answer.noul <= 1


def test_undeclared_label_is_rejected() -> None:
    answer = dict(answers("choice_described")["department"], choice="sales")
    with pytest.raises(ValidationError):
        RouteTicket.model_validate(answer)


def _choice_confidence(probabilities: list[float]) -> float:
    n = len(probabilities)
    return (max(probabilities) - 1 / n) / (1 - 1 / n)


def _score_confidence(probabilities: list[float]) -> float:
    n = len(probabilities)
    m = max(range(n), key=lambda i: probabilities[i])
    spread = sum(p * abs(i - m) for i, p in enumerate(probabilities))
    even_spread = sum(abs(i - (n - 1) / 2) for i in range(n)) / n
    return max(0.0, 1 - spread / even_spread)


def _recorded_answers(kind: str) -> list[dict[str, Any]]:
    return [
        answer
        for scenario in successes()
        for answer in answers(scenario).values()
        if answer["type"] == kind
    ]


@pytest.mark.parametrize("answer", _recorded_answers("choice"))
def test_documented_choice_confidence_formula(answer: dict[str, Any]) -> None:
    probabilities = list(cast(dict[str, float], answer["probabilities"]).values())
    assert _choice_confidence(probabilities) == pytest.approx(answer["confidence"], abs=ROUNDING)


@pytest.mark.parametrize("answer", _recorded_answers("score"))
def test_documented_score_confidence_formula(answer: dict[str, Any]) -> None:
    levels = cast(dict[str, float], answer["probabilities"])
    probabilities = [levels[str(i)] for i in range(len(levels))]
    assert _score_confidence(probabilities) == pytest.approx(answer["confidence"], abs=ROUNDING)
    expected = sum(i * p for i, p in enumerate(probabilities))
    assert expected == pytest.approx(answer["score"], abs=ROUNDING)


def test_question_returns_a_copy() -> None:
    question = RouteTicket.question()
    question["type"] = "mutated"
    assert RouteTicket.question()["type"] == "choice"


def test_instructions_are_inherited_from_a_user_base() -> None:
    class Child(RouteTicket):
        pass

    assert Child.question()["instructions"] == "Which team should handle this ticket?"


def test_a_parametrized_base_has_no_instructions() -> None:
    assert "instructions" not in Choice[Department].question()


def test_instructions_attribute() -> None:
    class Spam(Noul):
        instructions = {"task": "Identify unsolicited advertising."}  # noqa: RUF012

    assert Spam.question()["instructions"] == {"task": "Identify unsolicited advertising."}


def test_noul_with_criteria_only() -> None:
    class Spam(Noul):
        criteria = NoulCriteria(true="Unsolicited advertising")

    assert Spam.question() == {"type": "noul", "criteria": {"true": "Unsolicited advertising"}}


@pytest.mark.parametrize("base", [Primitive, Noul, Choice, Score])
def test_base_classes_are_not_questions(base: type[Primitive]) -> None:
    with pytest.raises(QuestionDefinitionError, match="base class"):
        base.question()


def test_docstring_and_instructions_are_exclusive() -> None:
    class Both(Noul):
        """Is this spam?"""

        instructions = "Is this spam?"

    with pytest.raises(QuestionDefinitionError, match="both a docstring and `instructions`"):
        Both.question()


def test_noul_needs_instructions_or_described_criteria() -> None:
    class Empty(Noul):
        criteria = NoulCriteria()

    with pytest.raises(QuestionDefinitionError, match="needs instructions or criteria"):
        Empty.question()


def test_choice_options_must_be_options_or_literal() -> None:
    class Free(Choice[str]):
        """Which team?"""

    with pytest.raises(QuestionDefinitionError, match="Options subclass or a Literal"):
        Free.question()


def test_choice_takes_at_most_255_options() -> None:
    many = cast(Any, Literal).__getitem__(tuple(f"o{i}" for i in range(256)))

    class Many(Choice[many]):  # type: ignore[valid-type]
        """Which one?"""

    with pytest.raises(QuestionDefinitionError, match="1 to 255 options"):
        Many.question()


def test_score_levels_must_be_levels() -> None:
    class Loose(Score[int]):
        """How much?"""

    with pytest.raises(QuestionDefinitionError, match="Levels subclass"):
        Loose.question()


def test_score_levels_must_start_at_zero_without_gaps() -> None:
    class Gappy(Levels):
        LOW = 0, "Low."
        HIGH = 2, "High."

    class Rate(Score[Gappy]):
        """How high?"""

    with pytest.raises(QuestionDefinitionError, match="from 0 to 1 without gaps"):
        Rate.question()


def test_score_levels_need_descriptions() -> None:
    class Blank(Levels):
        LOW = 0, ""
        HIGH = 1, "High."

    class Rate(Score[Blank]):
        """How high?"""

    with pytest.raises(QuestionDefinitionError, match=r"Blank\.LOW needs a description"):
        Rate.question()


def test_score_takes_at_most_10_levels() -> None:
    eleven = cast(Any, Levels)("Eleven", {f"L{i}": (i, f"Level {i}.") for i in range(11)})

    class Rate(Score[eleven]):  # type: ignore[valid-type]
        """How high?"""

    with pytest.raises(QuestionDefinitionError, match="1 to 10 levels"):
        Rate.question()


def test_empty_options_are_rejected() -> None:
    class Nothing(Options):
        pass

    class Pick(Choice[Nothing]):
        """Which one?"""

    with pytest.raises(QuestionDefinitionError, match="1 to 255 options"):
        Pick.question()
