"""Questionnaires and question mappings to the wire `questions`, and wire answers back."""

from __future__ import annotations

import functools
from collections.abc import Mapping
from typing import Any, cast

from pydantic import BaseModel, JsonValue, ValidationError

from jev.errors import QuestionDefinitionError, UnexpectedAnswerError
from jev.primitives import Primitive


def _is_primitive_class(value: object) -> bool:
    return isinstance(value, type) and issubclass(value, Primitive)


@functools.cache
def _questionnaire(model: type[BaseModel]) -> tuple[tuple[str, type[Primitive]], ...]:
    """Return `(wire name, question class)` for each field of a questionnaire."""
    entries: list[tuple[str, type[Primitive]]] = []
    for name, info in model.model_fields.items():
        annotation = info.annotation
        if not (isinstance(annotation, type) and issubclass(annotation, Primitive)):
            raise QuestionDefinitionError(
                f"{model.__name__}.{name}: every field must be a question class (a subclass of "
                f"Noul, Choice or Score), got {annotation!r}. Do not wrap questions in Optional."
            )
        if info.validation_alias is not None and info.validation_alias != info.alias:
            raise QuestionDefinitionError(
                f"{model.__name__}.{name}: use `alias` to choose the question name, "
                "not a separate `validation_alias`"
            )
        entries.append((info.alias or name, annotation))
    if not entries:
        raise QuestionDefinitionError(f"{model.__name__} declares no questions")
    wire_names = [wire for wire, _ in entries]
    if len(set(wire_names)) != len(wire_names):
        raise QuestionDefinitionError(f"{model.__name__}: question names must be unique")
    return tuple(entries)


def _entries(questions: object) -> list[tuple[str, type[Primitive]]]:
    if isinstance(questions, type):
        if issubclass(questions, Primitive):
            raise QuestionDefinitionError(
                f"pass a questionnaire model or a mapping, e.g. {{'name': {questions.__name__}}}"
            )
        if not issubclass(questions, BaseModel):
            raise QuestionDefinitionError(
                f"questions must be a Pydantic questionnaire model or a mapping, got {questions!r}"
            )
        return list(_questionnaire(questions))
    if isinstance(questions, Mapping):
        mapping = cast(Mapping[object, object], questions)
        if not mapping:
            raise QuestionDefinitionError("the question mapping is empty")
        entries: list[tuple[str, type[Primitive]]] = []
        for name, cls in mapping.items():
            if not isinstance(name, str) or not name:
                raise QuestionDefinitionError(f"question names must be non-empty strings: {name!r}")
            if not _is_primitive_class(cls):
                raise QuestionDefinitionError(
                    f"{name!r}: expected a question class (a subclass of Noul, Choice or Score), "
                    f"got {cls!r}"
                )
            assert isinstance(cls, type) and issubclass(cls, Primitive)
            entries.append((name, cls))
        return entries
    raise QuestionDefinitionError(
        f"questions must be a Pydantic questionnaire model or a mapping, got {questions!r}"
    )


def questions_payload(questions: object) -> dict[str, JsonValue]:
    """Return the wire `questions` object for a questionnaire model or a mapping.

    Raises:
        QuestionDefinitionError: A question or the questionnaire is invalid.
    """
    payload: dict[str, JsonValue] = {}
    for name, cls in _entries(questions):
        try:
            payload[name] = cls.question()
        except QuestionDefinitionError as error:
            raise QuestionDefinitionError(f"question {name!r}: {error}") from error
    return payload


def parse_answers(
    questions: object, answers: Mapping[str, Any], *, raw: Any, request_id: str | None
) -> Any:
    """Return the answers typed as declared: a questionnaire instance or a dict of answers.

    Raises:
        UnexpectedAnswerError: The answers do not match the declared questions.
    """
    if isinstance(questions, type) and issubclass(questions, BaseModel):
        try:
            return questions.model_validate(answers)
        except ValidationError as error:
            raise _unexpected(error, None, raw, request_id) from error
    parsed: dict[str, Primitive] = {}
    for name, cls in _entries(cast(object, questions)):
        if name not in answers:
            raise UnexpectedAnswerError(
                f"no answer for question {name!r}",
                question=name,
                value=None,
                raw=raw,
                request_id=request_id,
            )
        try:
            parsed[name] = cls.model_validate(answers[name])
        except ValidationError as error:
            raise _unexpected(error, name, raw, request_id) from error
    return parsed


def _unexpected(
    error: ValidationError, question: str | None, raw: Any, request_id: str | None
) -> UnexpectedAnswerError:
    first = error.errors()[0]
    location = list(first["loc"])
    if question is None and location:
        question = str(location.pop(0))
    field = ".".join(str(part) for part in location)
    where = f"{question}.{field}" if field else str(question)
    return UnexpectedAnswerError(
        f"answer {where} does not match the declared question: {first['msg']} "
        f"(got {first['input']!r})",
        question=question,
        value=first["input"],
        raw=raw,
        request_id=request_id,
    )
