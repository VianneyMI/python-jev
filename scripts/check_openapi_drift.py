"""Compare TypeSafe's published OpenAPI spec with the copy vendored in tests/fixtures.

Exits with status 1 and prints a diff when the spec changed. The API is pre-1.0, so a change may
mean the primitives, errors or client need an update; refresh the vendored copy with `--update`
once the SDK matches it.
"""

from __future__ import annotations

import difflib
import json
import sys
from pathlib import Path

import httpx2

VENDORED = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "openapi.json"
URL = "https://api.typesafe.ai/openapi.json"


def _normalized(text: str) -> str:
    return json.dumps(json.loads(text), indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main(update: bool) -> int:
    published = _normalized(httpx2.get(URL, timeout=30).raise_for_status().text)
    vendored = _normalized(VENDORED.read_text())
    if published == vendored:
        print("openapi.json: unchanged")
        return 0
    print("openapi.json: changed")
    sys.stdout.writelines(
        difflib.unified_diff(
            vendored.splitlines(keepends=True),
            published.splitlines(keepends=True),
            fromfile="vendored/openapi.json",
            tofile="published/openapi.json",
        )
    )
    if update:
        VENDORED.write_text(published)
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main(update="--update" in sys.argv[1:]))
