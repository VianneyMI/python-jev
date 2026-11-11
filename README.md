# python-jev

python-jev is a typed Python SDK for [Jev](https://typesafe.ai), TypeSafe's System One model for
fast decisions and classification. Jev reads a state, such as a support ticket or a JSON document,
and answers a set of questions about it in a single call, with a probability for each possible
answer. python-jev turns each question into a Python class and each answer into a typed object.

## Features

- Write each question once, as a class. After the call, the same class holds the answer.
- Get choices and levels back as members of your own enums, like `Department.BILLING`.
- Ask all your questions in one request.
- Pass text, Pydantic objects or JSON as state, instructions and criteria.
- Read TypeSafe's documentation in your editor, through the docstrings.
- Use a sync or an async client, fully typed for pyright and mypy.

## Installation

```shell
pip install python-jev
```

Python 3.11 or later. The package imports as `jev`. Set `TYPESAFE_API_KEY` with a key from
[console.typesafe.ai](https://console.typesafe.ai), or pass `Jev(api_key=...)`.

> The `jev` package on PyPI is a separate project with the same import name. Install one or the
> other in a given environment.

## Usage

> The examples below look at the same support ticket. Outputs come from calls to `jev-1.14.0`.

### Basic usage: one question

```python
from pydantic import BaseModel

import jev

TICKET = (
    "Hi, I was charged twice for my October invoice (INV-2291). Please refund the duplicate "
    "charge as soon as possible, this is the second time I write."
)


# Declaring a yes/no question
class IsRefund(jev.Noul):
    """Does the customer ask for money back?"""


# Listing the questions to ask
class Ticket(BaseModel):
    refund: IsRefund


# Asking Jev
with jev.Jev() as client:
    response = client.evaluate(TICKET, Ticket)

# Reading the answer
response.answers.refund.noul  # 0.98, the probability of yes
```

### Several questions in one call

```python
from pydantic import BaseModel

import jev

TICKET = (
    "Hi, I was charged twice for my October invoice (INV-2291). Please refund the duplicate "
    "charge as soon as possible, this is the second time I write."
)


# Declaring the possible answers
class Department(jev.Options):
    BILLING = "billing", "Charges, refunds, invoices."
    TECHNICAL = "technical", "Bugs, outages, integrations."
    OTHER = "other"


class Urgency(jev.Levels):
    CAN_WAIT = 0, "Can wait."
    THIS_WEEK = 1, "Needs attention this week."
    TODAY = 2, "Needs attention today."


# Declaring the questions
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


# Asking all three in one request
with jev.Jev() as client:
    response = client.evaluate(TICKET, Triage)

triage = response.answers

triage.department.choice  # Department.BILLING
triage.department.probabilities  # {Department.BILLING: 1.0, Department.TECHNICAL: 0.0, ...}

triage.urgency.score  # 1.47, between THIS_WEEK (1) and TODAY (2)
triage.urgency.probabilities  # {Urgency.CAN_WAIT: 0.0, Urgency.THIS_WEEK: 0.53, Urgency.TODAY: 0.47}
triage.urgency.confidence  # 0.3, Jev hesitates between the two

triage.refund.noul  # 0.98
```

### Structured state and decisions

```python
from pydantic import BaseModel

import jev


# Describing the state as a Pydantic model
class Policy(BaseModel):
    refund_window_days: int
    auto_refund_duplicates: bool


class RefundRequest(BaseModel):
    messages: list[str]
    policy: Policy


# Pointing the question at one part of the state
class Eligible(jev.Noul):
    """Is this refund request eligible under `policy`?"""


class RefundCheck(BaseModel):
    eligible: Eligible


request = RefundRequest(
    messages=[
        "I was charged twice for October.",
        "It has been a week. Refund me now or I cancel.",
    ],
    policy=Policy(refund_window_days=30, auto_refund_duplicates=True),
)

with jev.Jev() as client:
    response = client.evaluate(request, RefundCheck)

# Deciding, with the starting thresholds TypeSafe suggests
p_yes = response.answers.eligible.noul  # 0.92
if p_yes >= 0.7:
    action = "refund"
elif p_yes <= 0.3:
    action = "decline"
else:
    action = "human review"
```

TypeSafe recommends an object as state, with a descriptive name for each part. A question can
point at one part with a backticked path, such as `` `policy` `` above or
`` `policy.refund_window_days` ``. Pydantic objects are sent by alias, and plain JSON works too.
Instructions accept the same inputs as the state.

> Tip: ruff flags a plain `dict` assigned to `instructions` (RUF012, "mutable class attribute").
> Use a Pydantic object or annotate the attribute with `ClassVar`.

## Questions and answers

TypeSafe calls its question types *primitives*. Each one has a base class in `jev`. Subclass it to
declare a question. After a call, your class holds the answer.

| Primitive | Asks | You declare | The answer holds |
| --- | --- | --- | --- |
| `jev.Noul` | Is this true? | instructions, optional `criteria` | `noul` |
| `jev.Choice[Options]` | Which option? | options (type parameter), optional instructions | `choice`, `confidence`, `probabilities` |
| `jev.Score[Levels]` | Which level? | levels (type parameter), optional instructions | `score`, `confidence`, `probabilities` |

Instructions go in the class docstring or in an `instructions` class attribute, which takes text, a
Pydantic object or any JSON value. Use one of the two per question. `RouteTicket.question()`
returns the question as sent to TypeSafe.

### Noul

`noul` is the probability of yes, between 0 and 1. TypeSafe advises one condition per noul, phrased
with yes as the high end, and a score for questions of degree. A common starting point is yes above
0.7, no below 0.3 and human review in between, tuned to the cost of each kind of error.

`criteria` describes what yes and no look like:

```python
class IsSpam(jev.Noul):
    """Is this message spam?"""

    criteria = jev.NoulCriteria(true="Unsolicited advertising", false="A legitimate conversation")
```

For a confidence on the same scale as a choice's, take `abs(2 * noul - 1)`.

### Choice

Options come from the type parameter, as a `jev.Options` subclass (options with descriptions) or a
`Literal` of strings (names only). `choice` and the keys of `probabilities` carry your option type.
An answer outside your options raises `UnexpectedAnswerError`.

```python
class Tone(jev.Choice[Literal["calm", "angry", "excited"]]):
    """What is the tone of this message?"""
```

`confidence` equals `(n · p_max − 1) / (n − 1)` for n options. It reads 0 for an even spread and 1
when one option takes all the probability.

### Score

Levels come from a `jev.Levels` subclass, numbered from 0 (the low end) to n − 1. Each level needs a
description, since descriptions are what the model reads. `score` is the expected level, the
probability-weighted average of the levels, and it can land between two of them. `probabilities`
uses your `Levels` members as keys.

`confidence` equals `max(0, 1 − Σ pᵢ·|i − m| / MAD)`, with `m` the most likely level and `MAD` the
same average distance for an even spread. Probability on a neighbouring level costs less confidence
than probability on a distant one. Details at
[docs.typesafe.ai/confidence](https://docs.typesafe.ai/confidence).

## Questions built at runtime

`evaluate` also takes a dict of names to question classes. Answers come back in a dict.

```python
response = client.evaluate(state, {"refund": IsRefund, "urgency": HowUrgent})
response.answers["refund"]  # Noul | Choice[Any] | Score[Any]
```

Both forms send one request, and Jev answers the questions in parallel. Names key the answers, and
the model reads instructions and criteria. In a questionnaire, a field's `alias` sets the name.

## Results

`Result[T]` is a frozen Pydantic model with these fields:

- `answers`: your questionnaire instance, or a dict of answers
- `model`: the model that answered, such as `jev-1.14.0`
- `usage.input_tokens` and `usage.output_tokens`
- `raw`: the response body as received
- `request_id`: the `x-typesafe-request-id` header

`response.model_dump_json()` stores a result, and `jev.Result[Triage].model_validate_json(...)`
restores it.

`Jev()` calls `jev-latest`, an alias that moves to each new Jev release, and answers can move with
it. For stable answers, pin a version with `Jev(model="jev-1.14.0")` or `evaluate(..., model=...)`.
`response.model` names the model that answered.

## Cost and limits

TypeSafe bills input tokens, meaning the state plus the text of every question. Output tokens are
free. Six questions about the example ticket, in one call, came to 582 input tokens.

- Choice: 1 to 255 options
- Score: 1 to 10 levels
- Request body: 32 MiB
- JSON nesting: 64 levels

## Errors

Every exception derives from `jev.JevError`.

| Exception | When |
| --- | --- |
| `QuestionDefinitionError` | A question or questionnaire is invalid. Raised before any request. |
| `UnexpectedAnswerError` | An answer contradicts your declaration, e.g. an undeclared label. |
| `AuthenticationError` | 401: missing or invalid API key |
| `BadRequestError`, `ContextLengthExceededError` | 400: a request rule was broken, or the request is too long |
| `UnprocessableEntityError` | 422: a malformed request |
| `PayloadTooLargeError`, `UnsupportedMediaTypeError` | 413, 415 |
| `RateLimitError`, `OverloadedError` | 429, 529. `retry_after` holds the requested delay in seconds |
| `APIConnectionError`, `APITimeoutError` | The network failed or timed out |

`APIError` carries `status_code`, `error_type`, `detail` and `request_id`. Automatic retries for 429
and 529 arrive in 0.4 ([#6](https://github.com/VianneyMI/python-jev/issues/6)). Meanwhile, wait
`retry_after` seconds before calling again.

## Async

```python
async with jev.AsyncJev() as client:
    response = await client.evaluate(state, Triage)
```

## Going further

- [examples/triage.py](examples/triage.py) runs a ticket triage end to end.
- [docs.typesafe.ai](https://docs.typesafe.ai) is TypeSafe's documentation.
- Images and the box primitive come in 0.3. Retries, the long-context header and model listing
  come in 0.4. Both are tracked in the [issues](https://github.com/VianneyMI/python-jev/issues).

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

MIT. python-jev is a community project, independent from TypeSafe. Docstrings and this README
quote TypeSafe's documentation and link to the source pages.
