from pydantic import BaseModel, Field

from jev._content import to_wire
from jev.labels import Levels, NoulCriteria, Options


class Department(Options):
    BILLING = "billing", "Charges, refunds, invoices."
    TECHNICAL = "technical"


class Scope(BaseModel):
    handles: list[str]


class Urgency(Levels):
    CAN_WAIT = 0, "Can wait."
    TODAY = 1, Scope(handles=["outages"])


class Message(BaseModel):
    sender: str = Field(alias="from")
    text: str


def test_options_keep_their_value_and_description() -> None:
    assert Department.BILLING == "billing"
    assert Department("billing") is Department.BILLING
    assert Department.BILLING.description == "Charges, refunds, invoices."
    assert Department.TECHNICAL.description is None


def test_levels_keep_their_value_and_description() -> None:
    assert Urgency.TODAY == 1
    assert Urgency(0) is Urgency.CAN_WAIT
    assert Urgency.TODAY.description == Scope(handles=["outages"])


def test_noul_criteria_default_to_none() -> None:
    assert NoulCriteria(true="Spam") == NoulCriteria(true="Spam", false=None)


def test_to_wire_passes_text_and_json_through() -> None:
    assert to_wire("text") == "text"
    assert to_wire({"a": [1, 2.5, None, True]}) == {"a": [1, 2.5, None, True]}


def test_to_wire_dumps_models_by_alias() -> None:
    assert to_wire(Message.model_validate({"from": "customer", "text": "Hi"})) == {
        "from": "customer",
        "text": "Hi",
    }


def test_to_wire_dumps_models_inside_lists_and_dicts() -> None:
    messages = [Message.model_validate({"from": "a", "text": "x"})]
    assert to_wire(messages) == [{"from": "a", "text": "x"}]
    assert to_wire({"thread": messages}) == {"thread": [{"from": "a", "text": "x"}]}


def test_to_wire_dumps_descriptions_of_any_shape() -> None:
    assert to_wire(Urgency.TODAY.description) == {"handles": ["outages"]}
