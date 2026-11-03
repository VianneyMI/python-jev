"""Exceptions raised by python-jev.

Every exception derives from `JevError`. Errors returned by the TypeSafe API derive from
`APIError`, one subclass per documented status (see https://docs.typesafe.ai/api/errors).
"""

from __future__ import annotations

import math
import time
from collections.abc import Mapping
from email.utils import parsedate_to_datetime
from typing import Any, cast


class JevError(Exception):
    """Base class for every python-jev exception."""


class JevConfigurationError(JevError):
    """The client is missing configuration, such as the `TYPESAFE_API_KEY` API key."""


class QuestionDefinitionError(JevError):
    """A question class or questionnaire is invalid. Raised before any request is sent."""


class UnexpectedAnswerError(JevError):
    """TypeSafe returned answers that do not match the declared questions.

    For example a choice label or a score level that the question did not declare. This points
    at API drift or a bug; the untouched response is kept in `raw`.
    """

    def __init__(
        self,
        message: str,
        *,
        question: str | None,
        value: Any,
        raw: Any,
        request_id: str | None,
    ) -> None:
        super().__init__(message)
        self.question = question
        """Name of the question whose answer did not match, when known."""
        self.value = value
        """The unexpected value."""
        self.raw = raw
        """The response body exactly as received."""
        self.request_id = request_id
        """The `x-typesafe-request-id` response header."""


class APIError(JevError):
    """The TypeSafe API returned an error status."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        error_type: str | None = None,
        detail: Any = None,
        request_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        """Human-readable explanation, taken from the response's `detail`."""
        self.status_code = status_code
        """HTTP status code."""
        self.error_type = error_type
        """TypeSafe's `detail.error_type`, such as `api_usage_error`, when present."""
        self.detail = detail
        """The response's `detail` exactly as received."""
        self.request_id = request_id
        """The `x-typesafe-request-id` response header, useful when contacting TypeSafe."""

    def __str__(self) -> str:
        return f"{self.message} (HTTP {self.status_code})"


class BadRequestError(APIError):
    """400: the body breaks a request rule (encoding, nesting, non-finite numbers, ...)."""


class ContextLengthExceededError(BadRequestError):
    """400 `max_tokens_exceeded`: the request is longer than the model's context length."""


class AuthenticationError(APIError):
    """401: missing or invalid API key."""


class PayloadTooLargeError(APIError):
    """413: the body is over 32 MiB."""


class UnsupportedMediaTypeError(APIError):
    """415: unsupported `Content-Encoding`, or more than one compression layer."""


class UnprocessableEntityError(APIError):
    """422: the request failed validation, e.g. a malformed question. `detail` names the field."""


class _RetryableError(APIError):
    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        error_type: str | None = None,
        detail: Any = None,
        request_id: str | None = None,
        retry_after: float | None = None,
    ) -> None:
        super().__init__(
            message,
            status_code=status_code,
            error_type=error_type,
            detail=detail,
            request_id=request_id,
        )
        self.retry_after = retry_after
        """Seconds to wait before retrying, from `Retry-After` or `retry-after-ms`, if sent."""


class RateLimitError(_RetryableError):
    """429: rate limit exceeded. Back off and retry, ideally with exponential backoff."""


class OverloadedError(_RetryableError):
    """529: TypeSafe is temporarily overloaded. Retry after a short delay."""


class APIConnectionError(JevError):
    """The request could not reach TypeSafe, or the connection failed."""


class APITimeoutError(APIConnectionError):
    """The request timed out."""


_STATUS_ERRORS: dict[int, type[APIError]] = {
    400: BadRequestError,
    401: AuthenticationError,
    413: PayloadTooLargeError,
    415: UnsupportedMediaTypeError,
    422: UnprocessableEntityError,
}
_RETRYABLE_ERRORS: dict[int, type[_RetryableError]] = {429: RateLimitError, 529: OverloadedError}
_MAX_MESSAGE = 500


def parse_retry_after(headers: Mapping[str, str]) -> float | None:
    """Return the delay in seconds requested by `retry-after-ms` or `Retry-After`, if any.

    `Retry-After` may hold seconds or an HTTP date. Negative or unparsable values are ignored.

    >>> parse_retry_after({"retry-after-ms": "1500"})
    1.5
    >>> parse_retry_after({"retry-after": "3"})
    3.0
    >>> parse_retry_after({"retry-after": "soon"}) is None
    True
    """
    lowered = {key.lower(): value for key, value in headers.items()}
    if (raw := lowered.get("retry-after-ms")) is not None:
        delay = _non_negative(raw)
        if delay is not None:
            return delay / 1000
    if (raw := lowered.get("retry-after")) is not None:
        delay = _non_negative(raw)
        if delay is not None:
            return delay
        try:
            return max(0.0, parsedate_to_datetime(raw).timestamp() - time.time())
        except (TypeError, ValueError, OverflowError):
            return None
    return None


def _non_negative(raw: str) -> float | None:
    try:
        value = float(raw.strip())
    except ValueError:
        return None
    return value if math.isfinite(value) and value >= 0 else None


def _describe(detail: Any) -> tuple[str | None, str | None]:
    """Return `(error_type, message)` from a TypeSafe or FastAPI `detail`."""
    if isinstance(detail, str):
        return None, detail
    if isinstance(detail, Mapping):
        fields = cast(Mapping[str, Any], detail)
        error_type = fields.get("error_type")
        message = fields.get("message")
        return (
            error_type if isinstance(error_type, str) else None,
            message if isinstance(message, str) else None,
        )
    if isinstance(detail, list) and detail:
        first = cast(object, detail[0])
        if isinstance(first, Mapping):
            item = cast(Mapping[str, Any], first)
            location = ".".join(str(part) for part in item.get("loc", ()))
            message = str(item.get("msg", ""))
            return None, f"{location}: {message}" if location else message
    return None, None


def api_error(
    status_code: int, body: Any, headers: Mapping[str, str], request_id: str | None
) -> APIError:
    """Build the exception for an error response."""
    detail: Any = cast(Mapping[str, Any], body).get("detail") if isinstance(body, Mapping) else body
    error_type, message = _describe(detail)
    if message is None:
        text = body if isinstance(body, str) else repr(cast(object, body))
        message = text[:_MAX_MESSAGE] if text else f"HTTP {status_code}"
    arguments: dict[str, Any] = {
        "status_code": status_code,
        "error_type": error_type,
        "detail": detail,
        "request_id": request_id,
    }
    if status_code in _RETRYABLE_ERRORS:
        retry_after = parse_retry_after(headers)
        return _RETRYABLE_ERRORS[status_code](message, retry_after=retry_after, **arguments)
    if status_code == 400 and error_type == "max_tokens_exceeded":
        return ContextLengthExceededError(message, **arguments)
    return _STATUS_ERRORS.get(status_code, APIError)(message, **arguments)
