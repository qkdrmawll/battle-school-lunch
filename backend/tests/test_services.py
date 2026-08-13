from datetime import date

import pytest

from battle_school_lunch.errors import AppError
from battle_school_lunch.services.schools import normalize_menu, normalize_query, parse_date_range


def test_query_is_trimmed() -> None:
    assert normalize_query("  중앙고  ") == "중앙고"


@pytest.mark.parametrize("query", ["", " ", "\t"])
def test_empty_query_is_invalid(query: str) -> None:
    with pytest.raises(AppError, match="학교명"):
        normalize_query(query)


def test_date_range_is_parsed() -> None:
    assert parse_date_range("2026-08-01", "2026-08-03") == (
        date(2026, 8, 1),
        date(2026, 8, 3),
    )


@pytest.mark.parametrize(
    ("from_value", "to_value", "code"),
    [
        ("2026-02-30", "2026-03-01", "INVALID_DATE"),
        ("2026/02/01", "2026-03-01", "INVALID_DATE"),
        ("20260201", "2026-03-01", "INVALID_DATE"),
        ("2026-03-02", "2026-03-01", "INVALID_DATE_RANGE"),
    ],
)
def test_invalid_date_ranges(from_value: str, to_value: str, code: str) -> None:
    with pytest.raises(AppError) as error:
        parse_date_range(from_value, to_value)
    assert error.value.code == code


def test_menu_normalizes_all_br_variants_and_preserves_allergens() -> None:
    assert normalize_menu("쌀밥 (1.5)<br>국<br/>김치 (9)<BR />") == [
        "쌀밥 (1.5)",
        "국",
        "김치 (9)",
    ]
