import pytest
from pydantic import BaseModel, ValidationError

from src.config.types.common import NonEmptyStr, StrictModel


class _Wrapper(BaseModel):
    value: NonEmptyStr


class _StrictWrapper(StrictModel):
    value: str


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("foo", "foo"),
        ("  foo  ", "foo"),
        ("\tfoo\n", "foo"),
        ("a", "a"),
    ],
)
def test_non_empty_str_strips_whitespace_and_accepts_non_empty(
    raw: str, expected: str
) -> None:
    assert _Wrapper(value=raw).value == expected


@pytest.mark.parametrize("raw", ["", "   ", "\t", "\n"])
def test_non_empty_str_rejects_empty_or_whitespace_only(raw: str) -> None:
    with pytest.raises(ValidationError):
        _Wrapper(value=raw)  # pyright: ignore[reportUnusedCallResult]


def test_strict_model_forbids_extra_fields() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        _StrictWrapper(value="ok", extra="nope")  # type: ignore[call-arg]  # pyright: ignore[reportCallIssue, reportUnusedCallResult]
