"""Unofficial typed Python SDK for TypeSafe's Jev.

Jev is TypeSafe's System One model: it reads a state (text or JSON) and answers typed questions
about it with probabilities, all questions in one call. This package represents TypeSafe's
primitives (noul, choice, score) as Pydantic classes: the class is the question, its instances
are the typed answers.

This package is not affiliated with or endorsed by TypeSafe. See https://docs.typesafe.ai for
TypeSafe's documentation.
"""

from jev._client import AsyncJev, Jev
from jev._content import Content
from jev._version import __version__
from jev.errors import (
    APIConnectionError,
    APIError,
    APITimeoutError,
    AuthenticationError,
    BadRequestError,
    ContextLengthExceededError,
    JevConfigurationError,
    JevError,
    OverloadedError,
    PayloadTooLargeError,
    QuestionDefinitionError,
    RateLimitError,
    UnexpectedAnswerError,
    UnprocessableEntityError,
    UnsupportedMediaTypeError,
)
from jev.labels import Levels, NoulCriteria, Options
from jev.primitives import Answer, Choice, Noul, Primitive, Question, Score
from jev.result import Result, Usage

__all__ = [
    "APIConnectionError",
    "APIError",
    "APITimeoutError",
    "Answer",
    "AsyncJev",
    "AuthenticationError",
    "BadRequestError",
    "Choice",
    "Content",
    "ContextLengthExceededError",
    "Jev",
    "JevConfigurationError",
    "JevError",
    "Levels",
    "Noul",
    "NoulCriteria",
    "Options",
    "OverloadedError",
    "PayloadTooLargeError",
    "Primitive",
    "Question",
    "QuestionDefinitionError",
    "RateLimitError",
    "Result",
    "Score",
    "UnexpectedAnswerError",
    "UnprocessableEntityError",
    "UnsupportedMediaTypeError",
    "Usage",
    "__version__",
]
