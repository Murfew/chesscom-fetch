from pathlib import Path

import pytest

from chesscom_fetch.database import get_connection
from chesscom_fetch.domain import UNKNOWN_OPENING_FAMILY, Colour, Result, TimeClass
from chesscom_fetch.reports import (
    MonthlyRating,
    OpeningRecord,
    Record,
    get_monthly_ratings,
    get_most_played_openings,
    get_record,
)
from chesscom_fetch.sync_store import add_games
from tests.helpers import (
    CARO_KANN_DEFENSE,
    FRENCH_DEFENSE,
    LONDON_SYSTEM,
    SCANDINAVIAN_DEFENSE,
    SICILIAN_DEFENSE,
    USERNAME_ONE,
    USERNAME_TWO,
    VIENNA_GAMBIT,
    BuildFakeGameRow,
)


class TestGetRecord:
    def test_counts_each_result(
        self, temp_db: Path, build_fake_game_row: BuildFakeGameRow
    ) -> None:

        with get_connection(temp_db) as conn:
            add_games(
                conn,
                [
                    build_fake_game_row(result=Result.WIN),
                    build_fake_game_row(result=Result.WIN),
                    build_fake_game_row(result=Result.WIN),
                    build_fake_game_row(result=Result.DRAW),
                    build_fake_game_row(result=Result.LOSS),
                    build_fake_game_row(result=Result.LOSS),
                ],
            )

        record = get_record(temp_db, USERNAME_ONE)

        assert record == Record(wins=3, draws=1, losses=2)

    def test_returns_zeros_when_no_games(self, temp_db: Path) -> None:
        record = get_record(temp_db, USERNAME_ONE)

        assert record == Record()

    def test_counts_only_requested_player(
        self, temp_db: Path, build_fake_game_row: BuildFakeGameRow
    ) -> None:
        with get_connection(temp_db) as conn:
            add_games(
                conn,
                [
                    build_fake_game_row(username=USERNAME_ONE),
                    build_fake_game_row(username=USERNAME_ONE),
                    build_fake_game_row(username=USERNAME_TWO),
                ],
            )

        record = get_record(temp_db, USERNAME_ONE)

        assert record.total_games == 2


class TestRecord:
    def test_points_count_draws_as_half(self) -> None:
        record = Record(wins=1, draws=1, losses=0)
        assert record.points == pytest.approx(1.5)

    def test_total_games_adds_all_results(self) -> None:
        record = Record(wins=1, draws=3, losses=2)
        assert record.total_games == 6

    def test_score_is_points_over_games(self) -> None:
        record = Record(wins=2, draws=2, losses=1)
        assert record.score == pytest.approx(0.6)

    def test_score_is_none_without_games(self) -> None:
        record = Record(wins=0, draws=0, losses=0)
        assert record.score is None


class TestGetMostPlayedOpenings:
    def test_orders_by_games_played(
        self, temp_db: Path, build_fake_game_row: BuildFakeGameRow
    ) -> None:
        with get_connection(temp_db) as conn:
            add_games(
                conn,
                [
                    build_fake_game_row(opening_family=FRENCH_DEFENSE),
                    build_fake_game_row(opening_family=FRENCH_DEFENSE),
                    build_fake_game_row(opening_family=CARO_KANN_DEFENSE),
                ],
            )

        openings = get_most_played_openings(temp_db, USERNAME_ONE, Colour.WHITE)
        assert openings[0].opening_family == FRENCH_DEFENSE
        assert openings[1].opening_family == CARO_KANN_DEFENSE

    def test_breaks_ties_alphabetically(
        self, temp_db: Path, build_fake_game_row: BuildFakeGameRow
    ) -> None:
        with get_connection(temp_db) as conn:
            add_games(
                conn,
                [
                    build_fake_game_row(opening_family=FRENCH_DEFENSE),
                    build_fake_game_row(opening_family=CARO_KANN_DEFENSE),
                ],
            )

        openings = get_most_played_openings(temp_db, USERNAME_ONE, Colour.WHITE)
        assert openings[0].opening_family == CARO_KANN_DEFENSE
        assert openings[1].opening_family == FRENCH_DEFENSE

    def test_returns_at_most_five_openings(
        self, temp_db: Path, build_fake_game_row: BuildFakeGameRow
    ) -> None:
        with get_connection(temp_db) as conn:
            add_games(
                conn,
                [
                    build_fake_game_row(opening_family=FRENCH_DEFENSE),
                    build_fake_game_row(opening_family=CARO_KANN_DEFENSE),
                    build_fake_game_row(opening_family=SCANDINAVIAN_DEFENSE),
                    build_fake_game_row(opening_family=LONDON_SYSTEM),
                    build_fake_game_row(opening_family=VIENNA_GAMBIT),
                    build_fake_game_row(opening_family=SICILIAN_DEFENSE),
                ],
            )

        openings = [
            opening_record.opening_family
            for opening_record in get_most_played_openings(
                temp_db, USERNAME_ONE, Colour.WHITE
            )
        ]
        assert len(openings) == 5
        assert VIENNA_GAMBIT not in openings

    def test_returns_empty_when_no_games_as_colour(
        self, temp_db: Path, build_fake_game_row: BuildFakeGameRow
    ) -> None:
        with get_connection(temp_db) as conn:
            add_games(
                conn,
                [
                    build_fake_game_row(
                        opening_family=FRENCH_DEFENSE, colour=Colour.WHITE
                    ),
                ],
            )

        openings = get_most_played_openings(temp_db, USERNAME_ONE, Colour.BLACK)
        assert len(openings) == 0

    def test_counts_only_requested_colour(
        self, temp_db: Path, build_fake_game_row: BuildFakeGameRow
    ) -> None:
        with get_connection(temp_db) as conn:
            add_games(
                conn,
                [
                    build_fake_game_row(
                        opening_family=FRENCH_DEFENSE, colour=Colour.WHITE
                    ),
                    build_fake_game_row(
                        opening_family=CARO_KANN_DEFENSE, colour=Colour.BLACK
                    ),
                ],
            )

        openings = get_most_played_openings(temp_db, USERNAME_ONE, Colour.BLACK)
        assert len(openings) == 1
        assert openings[0].opening_family == CARO_KANN_DEFENSE

    def test_counts_only_requested_player(
        self, temp_db: Path, build_fake_game_row: BuildFakeGameRow
    ) -> None:
        with get_connection(temp_db) as conn:
            add_games(
                conn,
                [
                    build_fake_game_row(
                        username=USERNAME_ONE, opening_family=FRENCH_DEFENSE
                    ),
                    build_fake_game_row(
                        username=USERNAME_TWO, opening_family=CARO_KANN_DEFENSE
                    ),
                ],
            )

        openings = get_most_played_openings(temp_db, USERNAME_ONE, Colour.WHITE)
        assert len(openings) == 1
        assert openings[0].opening_family == FRENCH_DEFENSE

    def test_counts_results_per_family(
        self, temp_db: Path, build_fake_game_row: BuildFakeGameRow
    ) -> None:
        with get_connection(temp_db) as conn:
            add_games(
                conn,
                [
                    build_fake_game_row(
                        opening_family=FRENCH_DEFENSE, result=Result.WIN
                    ),
                    build_fake_game_row(
                        opening_family=FRENCH_DEFENSE, result=Result.WIN
                    ),
                    build_fake_game_row(
                        opening_family=FRENCH_DEFENSE, result=Result.DRAW
                    ),
                    build_fake_game_row(
                        opening_family=FRENCH_DEFENSE, result=Result.LOSS
                    ),
                    build_fake_game_row(
                        opening_family=CARO_KANN_DEFENSE, result=Result.WIN
                    ),
                    build_fake_game_row(
                        opening_family=CARO_KANN_DEFENSE, result=Result.LOSS
                    ),
                    build_fake_game_row(
                        opening_family=CARO_KANN_DEFENSE, result=Result.LOSS
                    ),
                ],
            )

        openings = get_most_played_openings(temp_db, USERNAME_ONE, Colour.WHITE)
        assert openings[0] == OpeningRecord(
            opening_family=FRENCH_DEFENSE, record=Record(wins=2, draws=1, losses=1)
        )
        assert openings[1] == OpeningRecord(
            opening_family=CARO_KANN_DEFENSE, record=Record(wins=1, draws=0, losses=2)
        )

    def test_counts_unknown_as_a_family(
        self, temp_db: Path, build_fake_game_row: BuildFakeGameRow
    ) -> None:
        with get_connection(temp_db) as conn:
            add_games(
                conn,
                [
                    build_fake_game_row(
                        result=Result.WIN, opening_family=UNKNOWN_OPENING_FAMILY
                    ),
                    build_fake_game_row(
                        result=Result.WIN, opening_family=UNKNOWN_OPENING_FAMILY
                    ),
                    build_fake_game_row(
                        result=Result.DRAW, opening_family=UNKNOWN_OPENING_FAMILY
                    ),
                    build_fake_game_row(
                        result=Result.LOSS, opening_family=UNKNOWN_OPENING_FAMILY
                    ),
                ],
            )

        openings = get_most_played_openings(temp_db, USERNAME_ONE, Colour.WHITE)
        assert openings[0] == OpeningRecord(
            opening_family=UNKNOWN_OPENING_FAMILY,
            record=Record(wins=2, draws=1, losses=1),
        )

    def test_orders_by_total_not_wins(
        self, temp_db: Path, build_fake_game_row: BuildFakeGameRow
    ) -> None:
        with get_connection(temp_db) as conn:
            add_games(
                conn,
                [
                    build_fake_game_row(
                        opening_family=FRENCH_DEFENSE, result=Result.WIN
                    ),
                    build_fake_game_row(
                        opening_family=FRENCH_DEFENSE, result=Result.DRAW
                    ),
                    build_fake_game_row(
                        opening_family=FRENCH_DEFENSE, result=Result.LOSS
                    ),
                    build_fake_game_row(
                        opening_family=CARO_KANN_DEFENSE, result=Result.WIN
                    ),
                    build_fake_game_row(
                        opening_family=CARO_KANN_DEFENSE, result=Result.WIN
                    ),
                ],
            )

        openings = get_most_played_openings(temp_db, USERNAME_ONE, Colour.WHITE)
        assert openings[0].opening_family == FRENCH_DEFENSE
        assert openings[1].opening_family == CARO_KANN_DEFENSE


class TestGetMonthlyRatings:
    def test_averages_rating_per_month_and_time_class(
        self, temp_db: Path, build_fake_game_row: BuildFakeGameRow
    ) -> None:
        with get_connection(temp_db) as conn:
            add_games(
                conn,
                [
                    build_fake_game_row(white_rating=1200),
                    build_fake_game_row(white_rating=1201),
                ],
            )

        ratings = get_monthly_ratings(temp_db, USERNAME_ONE)
        assert ratings == [
            MonthlyRating(
                year=2026,
                month=11,
                time_class=TimeClass.RAPID,
                average_rating=1200.5,
                total_games=2,
            )
        ]

    def test_uses_players_own_rating_for_each_colour(
        self, temp_db: Path, build_fake_game_row: BuildFakeGameRow
    ) -> None:
        with get_connection(temp_db) as conn:
            add_games(
                conn,
                [
                    build_fake_game_row(
                        white_rating=1200, black_rating=400, colour=Colour.WHITE
                    ),
                    build_fake_game_row(
                        white_rating=400, black_rating=1200, colour=Colour.BLACK
                    ),
                ],
            )

        ratings = get_monthly_ratings(temp_db, USERNAME_ONE)
        assert ratings == [
            MonthlyRating(
                year=2026,
                month=11,
                time_class=TimeClass.RAPID,
                average_rating=1200,
                total_games=2,
            )
        ]

    def test_ignores_unrated_games(
        self, temp_db: Path, build_fake_game_row: BuildFakeGameRow
    ) -> None:
        with get_connection(temp_db) as conn:
            add_games(
                conn,
                [
                    build_fake_game_row(white_rating=1200, rated=True),
                    build_fake_game_row(white_rating=400, rated=False),
                ],
            )

        ratings = get_monthly_ratings(temp_db, USERNAME_ONE)
        assert ratings == [
            MonthlyRating(
                year=2026,
                month=11,
                time_class=TimeClass.RAPID,
                average_rating=1200,
                total_games=1,
            )
        ]

    def test_returns_empty_when_only_unrated_games(
        self, temp_db: Path, build_fake_game_row: BuildFakeGameRow
    ) -> None:
        with get_connection(temp_db) as conn:
            add_games(
                conn,
                [
                    build_fake_game_row(white_rating=400, rated=False),
                ],
            )

        ratings = get_monthly_ratings(temp_db, USERNAME_ONE)
        assert ratings == []

    def test_separates_same_month_in_different_years(
        self, temp_db: Path, build_fake_game_row: BuildFakeGameRow
    ) -> None:
        with get_connection(temp_db) as conn:
            add_games(
                conn,
                [
                    build_fake_game_row(white_rating=1200, end_date="2025-11-05"),
                    build_fake_game_row(white_rating=1200, end_date="2026-11-05"),
                ],
            )

        ratings = get_monthly_ratings(temp_db, USERNAME_ONE)
        assert ratings == [
            MonthlyRating(
                year=2025,
                month=11,
                time_class=TimeClass.RAPID,
                average_rating=1200,
                total_games=1,
            ),
            MonthlyRating(
                year=2026,
                month=11,
                time_class=TimeClass.RAPID,
                average_rating=1200,
                total_games=1,
            ),
        ]

    def test_separates_time_classes_in_same_month(
        self, temp_db: Path, build_fake_game_row: BuildFakeGameRow
    ) -> None:
        with get_connection(temp_db) as conn:
            add_games(
                conn,
                [
                    build_fake_game_row(white_rating=1200, time_class=TimeClass.BLITZ),
                    build_fake_game_row(white_rating=1200, time_class=TimeClass.RAPID),
                ],
            )

        ratings = get_monthly_ratings(temp_db, USERNAME_ONE)
        assert ratings == [
            MonthlyRating(
                year=2026,
                month=11,
                time_class=TimeClass.BLITZ,
                average_rating=1200,
                total_games=1,
            ),
            MonthlyRating(
                year=2026,
                month=11,
                time_class=TimeClass.RAPID,
                average_rating=1200,
                total_games=1,
            ),
        ]

    def test_orders_by_month_then_time_class(
        self, temp_db: Path, build_fake_game_row: BuildFakeGameRow
    ) -> None:
        with get_connection(temp_db) as conn:
            add_games(
                conn,
                [
                    build_fake_game_row(
                        white_rating=1200,
                        time_class=TimeClass.BLITZ,
                        end_date="2026-11-05",
                    ),
                    build_fake_game_row(
                        white_rating=1200,
                        time_class=TimeClass.BLITZ,
                        end_date="2026-10-05",
                    ),
                    build_fake_game_row(
                        white_rating=1200,
                        time_class=TimeClass.RAPID,
                        end_date="2026-11-05",
                    ),
                    build_fake_game_row(
                        white_rating=1200,
                        time_class=TimeClass.RAPID,
                        end_date="2026-10-05",
                    ),
                ],
            )

        ratings = get_monthly_ratings(temp_db, USERNAME_ONE)
        assert [(rating.month, rating.time_class) for rating in ratings] == [
            (10, TimeClass.BLITZ),
            (10, TimeClass.RAPID),
            (11, TimeClass.BLITZ),
            (11, TimeClass.RAPID),
        ]

    def test_counts_only_requested_player(
        self, temp_db: Path, build_fake_game_row: BuildFakeGameRow
    ) -> None:
        with get_connection(temp_db) as conn:
            add_games(
                conn,
                [
                    build_fake_game_row(white_rating=1200, username=USERNAME_ONE),
                    build_fake_game_row(white_rating=1000, username=USERNAME_TWO),
                ],
            )

        ratings = get_monthly_ratings(temp_db, USERNAME_ONE)
        assert ratings == [
            MonthlyRating(
                year=2026,
                month=11,
                time_class=TimeClass.RAPID,
                average_rating=1200,
                total_games=1,
            )
        ]
