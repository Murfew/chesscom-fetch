from datetime import date

import pytest

from chesscom_fetch.models import Archive
from chesscom_fetch.sync import _is_archive_in_window, _is_month_complete
from tests.helpers import build_archive_url


class TestIsMonthComplete:
    @pytest.mark.parametrize(
        ("year", "month", "today", "expected"),
        [
            pytest.param(
                2026,
                3,
                date(2026, 3, 15),
                False,
                id="during-month",
            ),
            pytest.param(
                2026,
                3,
                date(2026, 4, 1),
                False,
                id="just-before-boundary",
            ),
            pytest.param(
                2026,
                3,
                date(2026, 4, 2),
                True,
                id="exactly-at-boundary",
            ),
            pytest.param(
                2026,
                12,
                date(2027, 1, 2),
                True,
                id="december-rolls-into-next-year",
            ),
            pytest.param(
                2028,
                2,
                date(2028, 3, 1),
                False,
                id="february-leap-year",
            ),
            pytest.param(
                2026,
                12,
                date(2026, 12, 15),
                False,
                id="december-before-boundary",
            ),
            pytest.param(
                2026,
                11,
                date(2026, 12, 2),
                True,
                id="november-stays-in-same-year",
            ),
        ],
    )
    def test_returns_correct_value(
        self, year: int, month: int, today: date, expected: bool
    ) -> None:
        assert (
            _is_month_complete(
                Archive(url=build_archive_url(year, month), year=year, month=month),
                today,
            )
            == expected
        )


class TestIsArchiveInWindow:
    TODAY = date(2027, 2, 10)

    @pytest.mark.parametrize(
        ("months", "year", "month", "expected"),
        [
            pytest.param(
                1,
                2027,
                2,
                True,
                id="current-month",
            ),
            pytest.param(
                1,
                2027,
                1,
                False,
                id="previous-month-excluded-when-one",
            ),
            pytest.param(
                3,
                2026,
                12,
                True,
                id="earliest-month-in-window",
            ),
            pytest.param(
                3,
                2026,
                11,
                False,
                id="just-outside-window",
            ),
            pytest.param(
                14,
                2026,
                1,
                True,
                id="window-spans-year-boundary",
            ),
        ],
    )
    def test_returns_correct_value(
        self, months: int, year: int, month: int, expected: bool
    ) -> None:
        assert (
            _is_archive_in_window(
                months,
                Archive(url=build_archive_url(year, month), year=year, month=month),
                self.TODAY,
            )
            == expected
        )


class TestSync:
    def test_stores_games_from_months_in_window(self) -> None: ...
    def test_skips_complete_months_without_request(self) -> None: ...
    def test_sends_stored_etag_and_counts_unchanged_month(self) -> None: ...
    def test_counts_skipped_games(self) -> None: ...
    def test_saves_new_etag_and_completeness(self) -> None: ...
    def test_second_run_stores_no_duplicates(self) -> None: ...
