from pathlib import Path

import pytest

from chesscom_fetch.database import get_connection
from chesscom_fetch.domain import UNKNOWN_OPENING_FAMILY, Colour, Result
from chesscom_fetch.reports import (
    OpeningRecord,
    Record,
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
    USERNAME_BLACK,
    USERNAME_WHITE,
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

        record = get_record(temp_db, USERNAME_WHITE)

        assert record == Record(wins=3, draws=1, losses=2)

    def test_returns_zeros_when_no_games(self, temp_db: Path) -> None:
        record = get_record(temp_db, USERNAME_WHITE)

        assert record == Record()

    def test_counts_only_requested_player(
        self, temp_db: Path, build_fake_game_row: BuildFakeGameRow
    ) -> None:
        with get_connection(temp_db) as conn:
            add_games(
                conn,
                [
                    build_fake_game_row(username=USERNAME_WHITE),
                    build_fake_game_row(username=USERNAME_WHITE),
                    build_fake_game_row(username=USERNAME_BLACK),
                ],
            )

        white_record = get_record(temp_db, USERNAME_WHITE)

        assert white_record.total_games == 2


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

        openings = get_most_played_openings(temp_db, USERNAME_WHITE, Colour.WHITE)
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

        openings = get_most_played_openings(temp_db, USERNAME_WHITE, Colour.WHITE)
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
                temp_db, USERNAME_WHITE, Colour.WHITE
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
                    build_fake_game_row(opening_family=FRENCH_DEFENSE),
                ],
            )

        openings = get_most_played_openings(temp_db, USERNAME_WHITE, Colour.BLACK)
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

        openings = get_most_played_openings(temp_db, USERNAME_WHITE, Colour.BLACK)
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
                        username=USERNAME_WHITE, opening_family=FRENCH_DEFENSE
                    ),
                    build_fake_game_row(
                        username=USERNAME_BLACK, opening_family=CARO_KANN_DEFENSE
                    ),
                ],
            )

        openings = get_most_played_openings(temp_db, USERNAME_WHITE, Colour.WHITE)
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

        openings = get_most_played_openings(temp_db, USERNAME_WHITE, Colour.WHITE)
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

        openings = get_most_played_openings(temp_db, USERNAME_WHITE, Colour.WHITE)
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

        openings = get_most_played_openings(temp_db, USERNAME_WHITE, Colour.WHITE)
        assert openings[0].opening_family == FRENCH_DEFENSE
        assert openings[1].opening_family == CARO_KANN_DEFENSE
