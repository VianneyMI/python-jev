from typing import Any

import pytest
from pydantic import BaseModel, Field
from questions import (
    SCENARIOS,
    Department,
    HowFrustrated,
    HowUrgent,
    IsRefund,
    RepeatContact,
    RouteTicket,
    Sentiment,
    Urgency,
)
from recorded import answers, questions, response

from jev import Choice, Noul, QuestionDefinitionError, UnexpectedAnswerError
from jev._compile import parse_answers, questions_payload
from jev.result import Result, Usage


class Triage(BaseModel):
    refund: IsRefund
    repeat_contact: RepeatContact
    department: RouteTicket
    sentiment: Sentiment
    urgency: HowUrgent
    frustration: HowFrustrated


class Aliased(BaseModel):
    route: RouteTicket = Field(alias="department")


def test_questionnaire_compiles_to_the_recorded_questions() -> None:
    assert questions_payload(Triage) == questions("combined")


@pytest.mark.parametrize("scenario", sorted(SCENARIOS))
def test_mapping_compiles_to_the_recorded_questions(scenario: str) -> None:
    assert questions_payload(SCENARIOS[scenario]) == questions(scenario)


def test_alias_is_the_question_name() -> None:
    assert list(questions_payload(Aliased)) == ["department"]
    parsed = parse_answers(Aliased, answers("choice_described"), raw={}, request_id=None)
    assert parsed.route.choice is Department.BILLING


def test_questionnaire_answers_are_typed() -> None:
    parsed = parse_answers(Triage, answers("combined"), raw={}, request_id=None)
    assert isinstance(parsed, Triage)
    assert parsed.department.choice is Department.BILLING
    assert set(parsed.urgency.probabilities) == set(Urgency)


def test_mapping_answers_are_instances_of_each_question() -> None:
    parsed = parse_answers(SCENARIOS["combined"], answers("combined"), raw={}, request_id=None)
    assert isinstance(parsed["department"], RouteTicket)
    assert isinstance(parsed["refund"], IsRefund)


def test_undeclared_label_in_a_questionnaire() -> None:
    wire = answers("combined")
    wire["department"] = dict(wire["department"], choice="sales")
    with pytest.raises(UnexpectedAnswerError) as caught:
        parse_answers(Triage, wire, raw={"x": 1}, request_id="req_1")
    assert caught.value.question == "department"
    assert caught.value.value == "sales"
    assert caught.value.raw == {"x": 1}
    assert caught.value.request_id == "req_1"


def test_undeclared_level_in_a_mapping() -> None:
    wire = answers("score_3")
    wire["urgency"] = dict(wire["urgency"], probabilities={"0": 0.5, "7": 0.5})
    with pytest.raises(UnexpectedAnswerError) as caught:
        parse_answers({"urgency": HowUrgent}, wire, raw={}, request_id=None)
    assert caught.value.question == "urgency"


def test_missing_answer_in_a_mapping() -> None:
    with pytest.raises(UnexpectedAnswerError, match="no answer for question 'urgency'"):
        parse_answers({"urgency": HowUrgent}, {}, raw={}, request_id=None)


class NotAQuestion(BaseModel):
    refund: bool


class OptionalQuestion(BaseModel):
    refund: IsRefund | None


class BareBase(BaseModel):
    refund: Noul


class Empty(BaseModel):
    pass


class ValidationAlias(BaseModel):
    refund: IsRefund = Field(validation_alias="other")


class Duplicate(BaseModel):
    first: IsRefund = Field(alias="refund")
    second: RepeatContact = Field(alias="refund")


@pytest.mark.parametrize(
    ("questions_", "message"),
    [
        (NotAQuestion, r"NotAQuestion\.refund: every field must be a question class"),
        (OptionalQuestion, "Do not wrap questions in Optional"),
        (BareBase, "question 'refund': Noul is a base class"),
        (Empty, "Empty declares no questions"),
        (ValidationAlias, "not a separate `validation_alias`"),
        (Duplicate, "question names must be unique"),
        ({}, "the question mapping is empty"),
        ({"refund": "IsRefund"}, "expected a question class"),
        ({"": IsRefund}, "non-empty strings"),
        (IsRefund, r"pass a questionnaire model or a mapping, e\.g\. \{'name': IsRefund\}"),
        (int, "must be a Pydantic questionnaire model or a mapping"),
        ([IsRefund], "must be a Pydantic questionnaire model or a mapping"),
    ],
)
def test_invalid_questions(questions_: Any, message: str) -> None:
    with pytest.raises(QuestionDefinitionError, match=message):
        questions_payload(questions_)


def test_a_bare_parametrized_choice_is_a_valid_question() -> None:
    class Plain(BaseModel):
        department: Choice[Department]

    assert questions_payload(Plain)["department"] == {
        "type": "choice",
        "criteria": {
            "billing": "Charges, refunds, invoices.",
            "technical": "Bugs, outages, integrations.",
            "other": None,
        },
    }


def _result(answers_: Any) -> dict[str, Any]:
    body = response("combined")
    return {
        "answers": answers_,
        "model": body["model"],
        "usage": Usage.model_validate(body["usage"]),
        "raw": body,
        "request_id": "req_1",
    }


def test_questionnaire_result_round_trips_through_json() -> None:
    parsed = parse_answers(Triage, answers("combined"), raw={}, request_id=None)
    result = Result[Triage](**_result(parsed))
    assert Result[Triage].model_validate_json(result.model_dump_json()) == result


def test_aliased_result_round_trips_through_json() -> None:
    parsed = parse_answers(Aliased, answers("choice_described"), raw={}, request_id=None)
    result = Result[Aliased](**_result(parsed))
    assert '"department"' in result.model_dump_json()
    assert Result[Aliased].model_validate_json(result.model_dump_json()) == result


def test_mapping_result_round_trips_as_base_primitives() -> None:
    parsed = parse_answers(SCENARIOS["combined"], answers("combined"), raw={}, request_id=None)
    restored = Result.model_validate_json(Result(**_result(parsed)).model_dump_json())
    department = restored.answers["department"]
    assert isinstance(department, Choice)
    assert not isinstance(department, RouteTicket)
    assert restored.answers["department"].model_dump() == parsed["department"].model_dump()
