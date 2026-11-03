import os
from collections.abc import AsyncIterator, Iterator

import pytest
from dotenv import find_dotenv, load_dotenv

from jev import AsyncJev, Jev

load_dotenv(find_dotenv(usecwd=True))


def _require_api_key() -> None:
    if not os.environ.get("TYPESAFE_API_KEY"):
        pytest.skip("set TYPESAFE_API_KEY to run live tests")


@pytest.fixture
def jev() -> Iterator[Jev]:
    _require_api_key()
    with Jev() as client:
        yield client


@pytest.fixture
async def async_jev() -> AsyncIterator[AsyncJev]:
    _require_api_key()
    async with AsyncJev() as client:
        yield client
