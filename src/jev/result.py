"""The result of an evaluation."""

from __future__ import annotations

from typing import Any, Generic

from pydantic import (
    BaseModel,
    ConfigDict,
    JsonValue,
    SerializationInfo,
    SerializerFunctionWrapHandler,
    field_serializer,
)
from typing_extensions import TypeVar

from jev.primitives import Answer

T = TypeVar("T", default=dict[str, Answer])


class Usage(BaseModel):
    """Token usage of one evaluation."""

    model_config = ConfigDict(frozen=True, extra="allow")

    input_tokens: int
    """Billable input tokens: the state and the text of every question."""
    output_tokens: int
    """Output tokens used to answer the questions. TypeSafe does not charge for them."""


class Result(BaseModel, Generic[T]):
    """What one call returned: the typed answers, the model that answered, and token usage.

    `answers` is an instance of the questionnaire model you passed, or a dict of answers when you
    passed a mapping of questions. Results are Pydantic models: `model_dump_json()` stores one,
    and `Result[MyQuestionnaire].model_validate_json(...)` restores it. A result of a mapping is
    restored with base primitive instances (`Noul`, `Choice`, `Score`), not your subclasses.
    """

    model_config = ConfigDict(frozen=True)

    answers: T
    """The answers, typed as declared."""
    model: str
    """The model that answered, such as `jev-1.14.0`. It can differ from the requested alias:
    `jev-latest` moves when TypeSafe releases a new model, and answers can change with it."""
    usage: Usage
    """Token usage."""
    raw: dict[str, JsonValue]
    """The response body exactly as received, including fields this package does not model."""
    request_id: str | None = None
    """The `x-typesafe-request-id` response header, useful when contacting TypeSafe."""

    @field_serializer("answers", mode="wrap")
    def _serialize_answers_by_alias(
        self, answers: Any, handler: SerializerFunctionWrapHandler, info: SerializationInfo
    ) -> Any:
        # Answers arrive keyed by question name (the alias), so dump them the same way.
        if isinstance(answers, BaseModel):
            return answers.model_dump(mode=info.mode, by_alias=True)
        return handler(answers)
