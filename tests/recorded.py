"""Access to responses recorded from the live TypeSafe API (see tests/fixtures/responses).

Recordings are produced by `scripts/record_fixtures.py`. Numbers in answers are rounded by the
API to two decimals.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, TypedDict, cast

RESPONSES = Path(__file__).parent / "fixtures" / "responses"


class Recording(TypedDict):
    status: int
    headers: dict[str, str]
    request: dict[str, Any]
    response: dict[str, Any] | str


def names() -> list[str]:
    """Return the names of all recordings."""
    return sorted(path.stem for path in RESPONSES.glob("*.json"))


def load(name: str) -> Recording:
    """Return the recording stored in `fixtures/responses/<name>.json`."""
    return cast(Recording, json.loads((RESPONSES / f"{name}.json").read_text()))


def response(name: str) -> dict[str, Any]:
    """Return the JSON body of a recording."""
    body = load(name)["response"]
    assert isinstance(body, dict)
    return body


def answers(name: str) -> dict[str, dict[str, Any]]:
    """Return the raw `answers` object of a successful recording."""
    return cast(dict[str, dict[str, Any]], response(name)["answers"])


def questions(name: str) -> dict[str, dict[str, Any]]:
    """Return the `questions` sent in a recording."""
    return cast(dict[str, dict[str, Any]], load(name)["request"]["questions"])


def successes() -> list[str]:
    """Return the names of recordings with HTTP status 200."""
    return [name for name in names() if load(name)["status"] == 200]
