import json
from collections.abc import Callable
from typing import Any

import httpx2
import pytest
from pydantic import BaseModel
from questions import SCENARIOS, Department, HowUrgent, IsRefund, RouteTicket, Urgency
from recorded import Recording, load

from jev import (
    APIConnectionError,
    APIError,
    APITimeoutError,
    AsyncJev,
    AuthenticationError,
    BadRequestError,
    ContextLengthExceededError,
    Jev,
    JevConfigurationError,
    OverloadedError,
    PayloadTooLargeError,
    QuestionDefinitionError,
    RateLimitError,
    UnexpectedAnswerError,
    UnprocessableEntityError,
    UnsupportedMediaTypeError,
)

STATE = "Hi, I was charged twice for my October invoice."


class Triage(BaseModel):
    refund: IsRefund
    department: RouteTicket
    urgency: HowUrgent


class Recorder:
    """MockTransport handler replaying a recording and keeping the requests it received."""

    def __init__(
        self,
        name: str | None = None,
        *,
        recording: Recording | None = None,
        raises: Exception | None = None,
    ) -> None:
        self.recording = recording if recording is not None else load(name) if name else None
        self.raises = raises
        self.requests: list[httpx2.Request] = []

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        if self.raises is not None:
            raise self.raises
        assert self.recording is not None
        body = self.recording["response"]
        content = body.encode() if isinstance(body, str) else json.dumps(body).encode()
        return httpx2.Response(
            self.recording["status"], headers=self.recording["headers"], content=content
        )

    @property
    def body(self) -> dict[str, Any]:
        return json.loads(self.requests[-1].content)


def client(recorder: Recorder, **kwargs: Any) -> Jev:
    transport = httpx2.MockTransport(recorder)
    return Jev(api_key="ts-test", http_client=httpx2.Client(transport=transport), **kwargs)


def async_client(recorder: Recorder, **kwargs: Any) -> AsyncJev:
    transport = httpx2.MockTransport(recorder)
    return AsyncJev(
        api_key="ts-test", http_client=httpx2.AsyncClient(transport=transport), **kwargs
    )


def synthetic(status: int, body: Any, headers: dict[str, str] | None = None) -> Recording:
    return {"status": status, "headers": headers or {}, "request": {}, "response": body}


def test_questionnaire_call() -> None:
    recorder = Recorder("combined")
    res = client(recorder).evaluate(STATE, Triage)
    assert isinstance(res.answers, Triage)
    assert res.answers.department.choice is Department.BILLING
    assert set(res.answers.urgency.probabilities) == set(Urgency)
    assert res.model == "jev-1.14.0"
    assert res.usage.input_tokens > 0
    assert res.raw == load("combined")["response"]
    assert res.request_id == load("combined")["headers"]["x-typesafe-request-id"]


def test_mapping_call() -> None:
    res = client(Recorder("combined")).evaluate(STATE, SCENARIOS["combined"])
    assert isinstance(res.answers["department"], RouteTicket)
    assert isinstance(res.answers["refund"], IsRefund)


def test_request_body_and_headers() -> None:
    recorder = Recorder("combined")
    client(recorder).evaluate(STATE, Triage)
    request = recorder.requests[0]
    assert request.method == "POST"
    assert str(request.url) == "https://api.typesafe.ai/v1/systemone"
    assert request.headers["authorization"] == "Bearer ts-test"
    assert request.headers["user-agent"].startswith("python-jev/")
    assert recorder.body == {
        "model": "jev-latest",
        "state": STATE,
        "questions": {
            "refund": IsRefund.question(),
            "department": RouteTicket.question(),
            "urgency": HowUrgent.question(),
        },
    }


def test_model_can_be_set_per_client_and_per_call() -> None:
    recorder = Recorder("noul_plain")
    jev = client(recorder, model="jev-1.13.0")
    jev.evaluate(STATE, {"refund": IsRefund})
    assert recorder.body["model"] == "jev-1.13.0"
    jev.evaluate(STATE, {"refund": IsRefund}, model="jev-1.14.0")
    assert recorder.body["model"] == "jev-1.14.0"


class Message(BaseModel):
    sender: str
    text: str


def test_structured_state_is_sent_as_json() -> None:
    recorder = Recorder("noul_plain")
    client(recorder).evaluate([Message(sender="customer", text="Refund me")], {"refund": IsRefund})
    assert recorder.body["state"] == [{"sender": "customer", "text": "Refund me"}]


def test_base_url() -> None:
    recorder = Recorder("noul_plain")
    client(recorder, base_url="https://proxy.example/").evaluate(STATE, {"refund": IsRefund})
    assert str(recorder.requests[0].url) == "https://proxy.example/v1/systemone"


def test_invalid_questions_send_no_request() -> None:
    recorder = Recorder("noul_plain")
    with pytest.raises(QuestionDefinitionError):
        client(recorder).evaluate(STATE, {"refund": int})  # type: ignore[dict-item]
    assert recorder.requests == []


def test_undeclared_answer() -> None:
    recording = load("choice_described")
    body = recording["response"]
    assert isinstance(body, dict)
    body["answers"]["department"]["choice"] = "sales"
    with pytest.raises(UnexpectedAnswerError) as caught:
        client(Recorder(recording=recording)).evaluate(STATE, {"department": RouteTicket})
    assert caught.value.question == "department"
    assert caught.value.request_id == recording["headers"]["x-typesafe-request-id"]


@pytest.mark.parametrize(
    ("name", "error_type", "status", "message"),
    [
        ("err_401", AuthenticationError, 401, "Cannot authenticate"),
        ("err_400_nesting", BadRequestError, 400, "nesting exceeds the maximum depth of 64"),
        ("err_400_unknown_type", BadRequestError, 400, "Invalid request."),
        (
            "err_422_choice_without_criteria",
            UnprocessableEntityError,
            422,
            "body.questions.department.choice.criteria: Field required",
        ),
    ],
)
def test_recorded_errors(name: str, error_type: type[APIError], status: int, message: str) -> None:
    with pytest.raises(error_type) as caught:
        client(Recorder(name)).evaluate(STATE, {"refund": IsRefund})
    assert type(caught.value) is error_type
    assert caught.value.status_code == status
    assert message in caught.value.message
    assert caught.value.request_id == load(name)["headers"]["x-typesafe-request-id"]
    assert caught.value.detail == load(name)["response"]["detail"]  # type: ignore[index]


@pytest.mark.parametrize(
    ("status", "error_type"),
    [
        (413, PayloadTooLargeError),
        (415, UnsupportedMediaTypeError),
        (500, APIError),
    ],
)
def test_other_statuses(status: int, error_type: type[APIError]) -> None:
    detail = {"error_type": "api_usage_error", "message": "Nope."}
    recorder = Recorder(recording=synthetic(status, {"detail": detail}))
    with pytest.raises(error_type) as caught:
        client(recorder).evaluate(STATE, {"refund": IsRefund})
    assert type(caught.value) is error_type
    assert caught.value.error_type == "api_usage_error"
    assert str(caught.value) == f"Nope. (HTTP {status})"


def test_context_length_exceeded() -> None:
    detail = {"error_type": "max_tokens_exceeded", "message": "Too long."}
    recorder = Recorder(recording=synthetic(400, {"detail": detail}))
    with pytest.raises(ContextLengthExceededError):
        client(recorder).evaluate(STATE, {"refund": IsRefund})


@pytest.mark.parametrize(
    ("status", "error_type", "headers", "retry_after"),
    [
        (429, RateLimitError, {"retry-after": "2"}, 2.0),
        (429, RateLimitError, {"retry-after-ms": "250"}, 0.25),
        (529, OverloadedError, {"retry-after": "Wed, 21 Oct 2015 07:28:00 GMT"}, 0.0),
        (529, OverloadedError, {"retry-after": "later"}, None),
        (529, OverloadedError, {}, None),
    ],
)
def test_retryable_errors(
    status: int, error_type: type[APIError], headers: dict[str, str], retry_after: float | None
) -> None:
    recorder = Recorder(recording=synthetic(status, {"detail": "Slow down."}, headers))
    with pytest.raises(error_type) as caught:
        client(recorder).evaluate(STATE, {"refund": IsRefund})
    assert getattr(caught.value, "retry_after") == retry_after  # noqa: B009


def test_non_json_error_body() -> None:
    recorder = Recorder(recording=synthetic(502, "<html>Bad gateway</html>"))
    with pytest.raises(APIError, match="Bad gateway"):
        client(recorder).evaluate(STATE, {"refund": IsRefund})


def test_unexpected_success_body() -> None:
    recorder = Recorder(recording=synthetic(200, {"something": "else"}))
    with pytest.raises(APIError, match="Unexpected response from TypeSafe"):
        client(recorder).evaluate(STATE, {"refund": IsRefund})


@pytest.mark.parametrize(
    ("exception", "error_type"),
    [
        (httpx2.ReadTimeout("timed out"), APITimeoutError),
        (httpx2.ConnectError("refused"), APIConnectionError),
    ],
)
def test_transport_errors(exception: Exception, error_type: type[Exception]) -> None:
    with pytest.raises(error_type):
        client(Recorder(raises=exception)).evaluate(STATE, {"refund": IsRefund})


def test_api_key_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TYPESAFE_API_KEY", "ts-env")
    recorder = Recorder("noul_plain")
    transport = httpx2.MockTransport(recorder)
    Jev(http_client=httpx2.Client(transport=transport)).evaluate(STATE, {"refund": IsRefund})
    assert recorder.requests[0].headers["authorization"] == "Bearer ts-env"


@pytest.mark.parametrize("factory", [Jev, AsyncJev])
def test_missing_api_key(monkeypatch: pytest.MonkeyPatch, factory: Callable[[], object]) -> None:
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    with pytest.raises(JevConfigurationError, match="TYPESAFE_API_KEY"):
        factory()


def test_repr_hides_the_api_key() -> None:
    assert "ts-test" not in repr(Jev(api_key="ts-test"))


def test_context_manager_closes_only_its_own_client() -> None:
    http_client = httpx2.Client()
    with Jev(api_key="ts-test", http_client=http_client):
        pass
    assert not http_client.is_closed
    with Jev(api_key="ts-test") as owned:
        pass
    assert owned._http_client.is_closed  # pyright: ignore[reportPrivateUsage]


@pytest.mark.anyio
async def test_async_questionnaire_call() -> None:
    recorder = Recorder("combined")
    async with async_client(recorder) as jev:
        res = await jev.evaluate(STATE, Triage)
    assert res.answers.department.choice is Department.BILLING
    assert recorder.body["questions"]["refund"] == IsRefund.question()


@pytest.mark.anyio
async def test_async_mapping_call() -> None:
    async with async_client(Recorder("combined")) as jev:
        res = await jev.evaluate(STATE, SCENARIOS["combined"])
    assert isinstance(res.answers["urgency"], HowUrgent)


@pytest.mark.anyio
async def test_async_errors() -> None:
    async with async_client(Recorder("err_401")) as jev:
        with pytest.raises(AuthenticationError):
            await jev.evaluate(STATE, {"refund": IsRefund})


@pytest.mark.anyio
async def test_async_transport_errors() -> None:
    async with async_client(Recorder(raises=httpx2.ReadTimeout("timed out"))) as jev:
        with pytest.raises(APITimeoutError):
            await jev.evaluate(STATE, {"refund": IsRefund})


@pytest.mark.anyio
async def test_async_invalid_questions_send_no_request() -> None:
    recorder = Recorder("noul_plain")
    async with async_client(recorder) as jev:
        with pytest.raises(QuestionDefinitionError):
            await jev.evaluate(STATE, {})
    assert recorder.requests == []
