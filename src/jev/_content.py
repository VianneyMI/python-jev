"""Content accepted wherever TypeSafe takes text: state, instructions, and criteria descriptions."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, TypeAlias, cast

from pydantic import BaseModel, JsonValue

Content: TypeAlias = str | BaseModel | Sequence[BaseModel] | JsonValue
"""Text, a Pydantic object, a list of Pydantic objects, or any JSON value.

TypeSafe accepts a string, a JSON object or a JSON array for `state`, `instructions` and
criteria descriptions. Pydantic objects are sent as JSON objects, using field aliases.
"""


def to_wire(content: Any) -> JsonValue:
    """Convert content to the JSON value sent to TypeSafe.

    Pydantic objects are dumped in JSON mode by alias, also inside lists and dicts.

    >>> to_wire(["a", {"b": 1}])
    ['a', {'b': 1}]
    """
    if isinstance(content, BaseModel):
        return content.model_dump(mode="json", by_alias=True)
    if isinstance(content, str):
        return content
    if isinstance(content, Mapping):
        items = cast(Mapping[Any, Any], content)
        return {str(key): to_wire(value) for key, value in items.items()}
    if isinstance(content, Sequence):
        values = cast(Sequence[Any], content)
        return [to_wire(value) for value in values]
    return cast(JsonValue, content)
