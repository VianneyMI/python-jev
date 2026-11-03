"""Sync and async clients for TypeSafe's System One API."""

from __future__ import annotations

import os
from collections.abc import Mapping
from types import TracebackType
from typing import Any, Self, cast

import httpx2
from pydantic import BaseModel, JsonValue, ValidationError

from jev._compile import parse_answers, questions_payload
from jev._content import Content, to_wire
from jev._version import __version__
from jev.errors import (
    APIConnectionError,
    APIError,
    APITimeoutError,
    JevConfigurationError,
    api_error,
)
from jev.primitives import Answer, Question
from jev.result import Result, T, Usage

DEFAULT_BASE_URL = "https://api.typesafe.ai"
DEFAULT_MODEL = "jev-latest"
DEFAULT_TIMEOUT = 30.0
API_KEY_VARIABLE = "TYPESAFE_API_KEY"
REQUEST_ID_HEADER = "x-typesafe-request-id"


class _Body(BaseModel):
    model: str
    answers: dict[str, Any]
    usage: Usage


class _ClientBase:
    """Request building and response parsing shared by the sync and async clients."""

    def __init__(self, *, api_key: str | None, model: str, base_url: str) -> None:
        api_key = api_key or os.environ.get(API_KEY_VARIABLE)
        if not api_key:
            raise JevConfigurationError(
                f"Pass api_key or set the {API_KEY_VARIABLE} environment variable"
            )
        self._api_key = api_key
        self.model = model
        """The model used when `evaluate` is called without `model`."""
        self._url = f"{base_url.rstrip('/')}/v1/systemone"

    def __repr__(self) -> str:
        return f"{type(self).__name__}(model={self.model!r})"

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "User-Agent": f"python-jev/{__version__}",
        }

    def _body(self, state: Content, questions: object, model: str | None) -> dict[str, JsonValue]:
        payload = questions_payload(questions)
        return {"model": model or self.model, "state": to_wire(state), "questions": payload}

    @staticmethod
    def _parse(response: httpx2.Response, questions: object) -> Any:
        status_code = response.status_code
        request_id = response.headers.get(REQUEST_ID_HEADER)
        try:
            body: Any = response.json()
        except ValueError:
            body = response.text
        if response.is_error:
            raise api_error(status_code, body, response.headers, request_id)
        try:
            parsed = _Body.model_validate(body)
        except ValidationError as error:
            raise APIError(
                f"Unexpected response from TypeSafe: {response.text[:500]!r}",
                status_code=status_code,
                request_id=request_id,
            ) from error
        answers = parse_answers(questions, parsed.answers, raw=body, request_id=request_id)
        if isinstance(questions, type):
            result_type: type[Result[Any]] = Result[questions]  # type: ignore[valid-type]
        else:
            result_type = Result[dict[str, Answer]]
        return result_type.model_construct(
            answers=answers,
            model=parsed.model,
            usage=parsed.usage,
            raw=cast(dict[str, JsonValue], body),
            request_id=request_id,
        )


class Jev(_ClientBase):
    """Client for TypeSafe's System One API, answering questions with Jev.

    ```python
    with Jev() as client:
        res = client.evaluate(ticket, Triage)
    res.answers.department.choice
    ```

    Args:
        api_key: str | None
            TypeSafe API key. Defaults to the `TYPESAFE_API_KEY` environment variable.
        model: str
            Model used by `evaluate` unless it is given one. Defaults to `jev-latest`, an alias
            that moves to each new Jev release; pin a version such as `jev-1.14.0` to keep
            answers stable. `Result.model` tells which model answered.
        base_url: str
            API root, to route requests through a proxy.
        timeout: float | httpx2.Timeout
            Seconds to wait for a response. Ignored when `http_client` is given.
        http_client: httpx2.Client | None
            HTTP client to send requests with, for custom transports or proxies. The caller
            closes it.

    Raises:
        JevConfigurationError: No API key was passed or set in the environment.
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str = DEFAULT_MODEL,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float | httpx2.Timeout = DEFAULT_TIMEOUT,
        http_client: httpx2.Client | None = None,
    ) -> None:
        super().__init__(api_key=api_key, model=model, base_url=base_url)
        self._owns_http_client = http_client is None
        self._http_client = http_client or httpx2.Client(timeout=timeout)

    def evaluate(
        self,
        state: Content,
        questions: type[T] | Mapping[str, Question],
        *,
        model: str | None = None,
    ) -> Result[T]:
        """Ask Jev every question about `state` in one call.

        Jev reads the state once and answers all questions in parallel and independently: adding
        a question does not change the others' answers, and costs little extra time.

        Args:
            state: Content
                The content all questions refer to: text, a Pydantic object, a list of them, or
                any JSON value. "Use an object for most requests so each part of the state has a
                descriptive name" (TypeSafe).
            questions: type[T] | Mapping[str, Question]
                A questionnaire, a Pydantic model whose fields are question classes, or a mapping
                from question names to question classes. Names are only keys: TypeSafe does not
                send them to the model.
            model: str | None
                Model for this call, overriding the client's.

        Returns:
            The answers, as an instance of the questionnaire or as a dict of answers, with the
            model that answered, token usage, the raw response and the request id.

        Raises:
            QuestionDefinitionError: A question is invalid; no request is sent.
            UnexpectedAnswerError: The answers do not match the declared questions.
            APIError: TypeSafe returned an error status; see its subclasses.
            APIConnectionError: TypeSafe could not be reached; `APITimeoutError` on timeout.
        """
        body = self._body(state, questions, model)
        try:
            response = self._http_client.post(self._url, json=body, headers=self._headers())
        except httpx2.TimeoutException as error:
            raise APITimeoutError(f"TypeSafe did not answer in time: {error}") from error
        except httpx2.TransportError as error:
            raise APIConnectionError(f"Could not reach TypeSafe: {error}") from error
        return cast(Result[T], self._parse(response, questions))

    def close(self) -> None:
        """Close the HTTP connections, unless the HTTP client was passed in."""
        if self._owns_http_client:
            self._http_client.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()


class AsyncJev(_ClientBase):
    """Async client for TypeSafe's System One API. Same options and behaviour as `Jev`.

    ```python
    async with AsyncJev() as client:
        res = await client.evaluate(ticket, Triage)
    ```
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str = DEFAULT_MODEL,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float | httpx2.Timeout = DEFAULT_TIMEOUT,
        http_client: httpx2.AsyncClient | None = None,
    ) -> None:
        super().__init__(api_key=api_key, model=model, base_url=base_url)
        self._owns_http_client = http_client is None
        self._http_client = http_client or httpx2.AsyncClient(timeout=timeout)

    async def evaluate(
        self,
        state: Content,
        questions: type[T] | Mapping[str, Question],
        *,
        model: str | None = None,
    ) -> Result[T]:
        """Ask Jev every question about `state` in one call. See `Jev.evaluate`."""
        body = self._body(state, questions, model)
        try:
            response = await self._http_client.post(self._url, json=body, headers=self._headers())
        except httpx2.TimeoutException as error:
            raise APITimeoutError(f"TypeSafe did not answer in time: {error}") from error
        except httpx2.TransportError as error:
            raise APIConnectionError(f"Could not reach TypeSafe: {error}") from error
        return cast(Result[T], self._parse(response, questions))

    async def aclose(self) -> None:
        """Close the HTTP connections, unless the HTTP client was passed in."""
        if self._owns_http_client:
            await self._http_client.aclose()

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.aclose()
