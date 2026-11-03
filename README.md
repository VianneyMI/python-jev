# python-jev

Unofficial typed Python SDK for [TypeSafe](https://typesafe.ai)'s **Jev**, a System One model for
fast decisions and classification. You declare questions as Python classes. Jev answers all of
them in one call. You get answers typed with your own labels and levels.

> This package is not affiliated with or endorsed by TypeSafe. TypeSafe's documentation lives at
> [docs.typesafe.ai](https://docs.typesafe.ai). Parts of it are quoted in this README and in the
> docstrings.

```python
from pydantic import BaseModel
import jev


class Department(jev.Options):
    BILLING = "billing", "Charges, refunds, invoices."
    TECHNICAL = "technical", "Bugs, outages, integrations."
    OTHER = "other"


class Urgency(jev.Levels):
    CAN_WAIT = 0, "Can wait."
    THIS_WEEK = 1, "Needs attention this week."
    TODAY = 2, "Needs attention today."


class RouteTicket(jev.Choice[Department]):
    """Which team should handle this ticket?"""


class HowUrgent(jev.Score[Urgency]):
    """How urgent is this ticket?"""


class IsRefund(jev.Noul):
    """Does the customer ask for money back?"""


class Triage(BaseModel):
    department: RouteTicket
    urgency: HowUrgent
    refund: IsRefund


with jev.Jev() as client:  # reads TYPESAFE_API_KEY
    res = client.evaluate("I was charged twice for October, please refund me.", Triage)

res.answers.department.choice  # Department.BILLING
res.answers.department.probabilities  # {Department.BILLING: 1.0, Department.TECHNICAL: 0.0, ...}
res.answers.urgency.score  # 1.47, the expected level (between two levels)
res.answers.urgency.probabilities  # {Urgency.CAN_WAIT: 0.0, Urgency.THIS_WEEK: 0.53, ...}
res.answers.refund.noul  # 0.98, the probability of yes
```

## Install

```bash
pip install python-jev      # or: uv add python-jev
```

The import name is `jev`. Python 3.11 or later. Get an API key from
[console.typesafe.ai](https://console.typesafe.ai) and set `TYPESAFE_API_KEY`, or pass
`Jev(api_key=...)`.

> An unrelated package named `jev` exists on PyPI and also installs a top-level `jev` module.
> Don't install both in the same environment.

## Primitives: the class is the question, its instances are the answers

TypeSafe answers three kinds of questions, its *primitives*. Each one is a base class here.
Subclass it to declare a question. After a call, each instance of your class is an answer. This
works like a Pydantic model, where the class is the schema and the instances are the data.

| Primitive | Asks | You declare | The answer holds |
| --- | --- | --- | --- |
| `jev.Noul` | Is this true? | instructions, optional `criteria` | `noul` |
| `jev.Choice[Options]` | Which option? | options (type parameter), optional instructions | `choice`, `confidence`, `probabilities` |
| `jev.Score[Levels]` | Which level? | levels (type parameter), optional instructions | `score`, `confidence`, `probabilities` |

**Instructions** are the class docstring (text) or an `instructions = ...` class attribute, which
can be text, a Pydantic object or any JSON value. Setting both is an error.
`RouteTicket.question()` returns the exact question that gets sent.

### Noul

`noul` is the **probability of yes**, from 0 to 1. TypeSafe: a noul value "is not a scale of the
thing you asked about". 0.9 means "very likely yes", not "very much". Ask one condition per noul
and combine the answers in your code. Phrase the question so that a high value means yes. A good
starting point is 0.7 for yes and 0.3 for no, then adjust both to the cost of each kind of error.

```python
class IsSpam(jev.Noul):
    """Is this message spam?"""

    criteria = jev.NoulCriteria(true="Unsolicited advertising", false="A legitimate conversation")
```

A noul has no `confidence`. If you need one on the same scale as a choice's, use
`abs(2 * noul - 1)`.

### Choice

The options come from the type parameter. Use a `jev.Options` subclass for options with
descriptions, or a `Literal` of strings for options identified by name only. `choice` and the
keys of `probabilities` are typed with your options, so the type checker knows exactly which
values are possible. If TypeSafe ever returns an undeclared option, `UnexpectedAnswerError` is
raised.

```python
class Tone(jev.Choice[Literal["calm", "angry", "excited"]]):
    """What is the tone of this message?"""
```

`confidence` is `(n · p_max − 1) / (n − 1)` for n options: 0 for an even spread, 1 when all the
probability is on one option.

### Score

The levels come from a `jev.Levels` subclass. Its members run from 0 (the low end) to n − 1, and
each needs a description: "the model gets the descriptions and nothing else". `score` is the
**expected level**, the probability-weighted average of the levels. It can fall between two
levels. `probabilities` is keyed by your `Levels` members.

`confidence` is `max(0, 1 − Σ pᵢ·|i − m| / MAD)`, where `m` is the most likely level and `MAD`
is the same average distance for an even spread. Probability on a level next to `m` lowers
confidence less than probability on a distant level. See
[docs.typesafe.ai/confidence](https://docs.typesafe.ai/confidence).

## Two ways to ask

**A questionnaire** is a Pydantic model whose fields are question classes. The result is typed as
that model:

```python
res = client.evaluate(state, Triage)  # Result[Triage]
```

**A mapping** of names to question classes is useful for questions you assemble at runtime:

```python
res = client.evaluate(state, {"refund": IsRefund, "urgency": HowUrgent})
res.answers["refund"]  # Noul | Choice[Any] | Score[Any]
```

Both go through the same `evaluate` and send a single request. Jev answers every question in
parallel and independently, so adding questions costs almost no time. Question names are only
keys: TypeSafe does not send them to the model. In a questionnaire, a field's `alias` sets the
name.

## Structured inputs

`state`, `instructions`, option and level descriptions, and noul criteria all accept text, a
Pydantic object, or JSON that may contain Pydantic objects. Models are sent by alias.

```python
class Message(BaseModel):
    sender: str
    text: str


class Eligible(jev.Noul):
    instructions = EligibilityTask(question="Is this refund eligible under `policy`?")


res = client.evaluate(
    {"messages": [Message(sender="customer", text="Refund me")], "policy": policy}, ...
)
```

TypeSafe recommends an object for most states, so that each part has a descriptive name. Point a
question at one part with a backticked path, for example `` `ticket.messages` ``.

> Tip: a plain `dict` assigned to `instructions` triggers ruff's RUF012 ("mutable class
> attribute"). Use a Pydantic object instead, or annotate the attribute with `ClassVar`.

## Results

`Result[T]` is a frozen Pydantic model with these fields:

- `answers`: your questionnaire instance, or a dict of answers
- `model`: the model that answered, such as `jev-1.14.0`
- `usage.input_tokens` and `usage.output_tokens` (output tokens are free)
- `raw`: the response body exactly as received
- `request_id`: the `x-typesafe-request-id` header

Store a result with `res.model_dump_json()` and restore it with
`jev.Result[Triage].model_validate_json(...)`.

**Model versions.** `Jev()` uses `jev-latest` by default. That alias moves to each new Jev
release, and answers can change with it. Pin a version with `Jev(model="jev-1.14.0")` or
`evaluate(..., model=...)` when you need stable answers. `res.model` always tells you which model
answered.

## Errors

Every exception derives from `jev.JevError`.

| Exception | When |
| --- | --- |
| `QuestionDefinitionError` | A question or questionnaire is invalid. Raised before any request. |
| `UnexpectedAnswerError` | The answers don't match your declaration, e.g. an undeclared label. |
| `AuthenticationError` | 401: missing or invalid API key |
| `BadRequestError`, `ContextLengthExceededError` | 400: a request rule was broken, or the request is too long |
| `UnprocessableEntityError` | 422: a malformed request |
| `PayloadTooLargeError`, `UnsupportedMediaTypeError` | 413, 415 |
| `RateLimitError`, `OverloadedError` | 429, 529. `retry_after` holds the requested delay in seconds |
| `APIConnectionError`, `APITimeoutError` | The network failed or timed out |

`APIError` carries `status_code`, `error_type`, `detail` and `request_id`. There are no automatic
retries yet.

## Async

```python
async with jev.AsyncJev() as client:
    res = await client.evaluate(state, Triage)
```

## Development

```bash
uv sync
uv run ruff format --check && uv run ruff check && uv run pyright && uv run mypy && uv run pytest
uv run pytest -m live                        # real API calls, needs TYPESAFE_API_KEY
uv run python scripts/record_fixtures.py     # re-record tests/fixtures/responses
uv run python scripts/check_openapi_drift.py # compare with TypeSafe's published OpenAPI spec
```

Typing guarantees live in `tests/typing/` and are checked by both pyright and mypy.

## License

MIT
