"""Unofficial typed Python SDK for TypeSafe's Jev.

Jev is TypeSafe's System One model: it reads a state (text or JSON) and answers typed questions
about it with probabilities, all questions in one call. This package represents TypeSafe's
primitives (noul, choice, score) as Pydantic classes: the class is the question, its instances
are the typed answers.

This package is not affiliated with or endorsed by TypeSafe. See https://docs.typesafe.ai for
TypeSafe's documentation.
"""

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
from jev.primitives import Choice, Noul, Primitive, Score

__all__ = [
    "APIConnectionError",
    "APIError",
    "APITimeoutError",
    "AuthenticationError",
    "BadRequestError",
    "Choice",
    "Content",
    "ContextLengthExceededError",
    "JevConfigurationError",
    "JevError",
    "Levels",
    "Noul",
    "NoulCriteria",
    "Options",
    "OverloadedError",
    "PayloadTooLargeError",
    "Primitive",
    "QuestionDefinitionError",
    "RateLimitError",
    "Score",
    "UnexpectedAnswerError",
    "UnprocessableEntityError",
    "UnsupportedMediaTypeError",
    "__version__",
]
