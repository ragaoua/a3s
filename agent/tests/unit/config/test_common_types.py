import pytest
from pydantic import BaseModel, ValidationError

from src.config.types.common import NonEmptyStr, Sha256Hex, StrictModel


class _Wrapper(BaseModel):
    value: NonEmptyStr


class _Sha256Wrapper(BaseModel):
    value: Sha256Hex


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


def test_sha256_hex_accepts_a_valid_lowercase_digest() -> None:
    digest = "a" * 64
    assert _Sha256Wrapper(value=digest).value == digest


def test_sha256_hex_strips_surrounding_whitespace() -> None:
    digest = "0123456789abcdef" * 4
    assert _Sha256Wrapper(value=f"  {digest}\n").value == digest


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "a" * 63,  # too short
        "a" * 65,  # too long
        "A" * 64,  # uppercase not accepted
        "g" * 64,  # non-hex character
        "z" * 64,
    ],
)
def test_sha256_hex_rejects_non_digests(raw: str) -> None:
    with pytest.raises(ValidationError):
        _Sha256Wrapper(value=raw)  # pyright: ignore[reportUnusedCallResult]


def test_strict_model_forbids_extra_fields() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        _StrictWrapper(value="ok", extra="nope")  # type: ignore[call-arg]  # pyright: ignore[reportCallIssue, reportUnusedCallResult]
