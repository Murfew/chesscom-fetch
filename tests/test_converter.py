from datetime import date

import pytest

from chesscom_fetch.converter import (
    BadPGNError,
    UnknownResultError,
    UsernameMismatchError,
    VariantGameError,
    api_result_to_result,
    game_to_game_row,
    is_month_complete,
)
from chesscom_fetch.models import APIResult, Colour, Game, Result
from tests.helpers import TEST_USERNAME_BLACK, TEST_USERNAME_WHITE

TODAY = date.fromisoformat("2026-10-24")
UNKNOWN_API_RESULT_CODE = "unknown"


class TestGameToGameRow:
    @pytest.mark.parametrize(
        ("username", "expected_colour", "expected_result"),
        [
            pytest.param(TEST_USERNAME_WHITE, Colour.WHITE, Result.LOSS),
            pytest.param(TEST_USERNAME_BLACK, Colour.BLACK, Result.WIN),
        ],
    )
    def test_sets_colour_from_username(
        self,
        fake_game: Game,
        username: str,
        expected_colour: Colour,
        expected_result: Result,
    ) -> None:
        game_row = game_to_game_row(username, fake_game, TODAY)
        assert game_row.colour == expected_colour
        assert game_row.result == expected_result

    def test_rejects_username_not_in_game(self, fake_game: Game) -> None:
        bad_username = "testplayernotingame"

        with pytest.raises(
            UsernameMismatchError, match=f"{fake_game.url}.*{bad_username}"
        ) as exc_info:
            game_to_game_row(bad_username, fake_game, TODAY)

        assert exc_info.value.username == bad_username

    @pytest.mark.parametrize(
        ("new_pgn", "expected_no_moves"),
        [
            pytest.param(
                "*",
                0,
                id="zero-moves",
            ),
            pytest.param(
                "1. e4 c6 2. d4 *",
                2,
                id="white-moves-last",
            ),
            pytest.param(
                "1. e4 c6 2. d4 d5 *",
                2,
                id="black-moves-last",
            ),
        ],
    )
    def test_counts_moves(
        self, fake_game: Game, new_pgn: str, expected_no_moves: int
    ) -> None:
        fake_game_with_modified_moves = fake_game.model_copy(update={"pgn": new_pgn})
        game_row = game_to_game_row(
            TEST_USERNAME_WHITE, fake_game_with_modified_moves, TODAY
        )
        assert game_row.no_moves == expected_no_moves

    @pytest.mark.parametrize(
        "bad_pgn",
        [
            pytest.param(
                "1. e4 c6 2. d4 d5 3. e5 Bf5 4. Nf3 e6 5. Qh5 c5 6. O-O Nc6 0-1",
                id="illegal-pgn",
            ),
            pytest.param("", id="empty-pgn"),
        ],
    )
    def test_rejects_invalid_pgn(self, fake_game: Game, bad_pgn: str) -> None:
        fake_game_with_illegal_pgn = fake_game.model_copy(update={"pgn": bad_pgn})

        with pytest.raises(BadPGNError, match=f"{fake_game.url}.*PGN") as exc_info:
            game_to_game_row(TEST_USERNAME_WHITE, fake_game_with_illegal_pgn, TODAY)

        assert exc_info.value.pgn == fake_game_with_illegal_pgn.pgn

    def test_rejects_invalid_game_variant(self, fake_game: Game) -> None:
        fake_game_with_invalid_game_rules = fake_game.model_copy(
            update={"rules": "chess960"}
        )

        with pytest.raises(
            VariantGameError,
            match=f"{fake_game_with_invalid_game_rules.url}.*{fake_game_with_invalid_game_rules.rules}",
        ) as exc_info:
            game_to_game_row(
                TEST_USERNAME_WHITE, fake_game_with_invalid_game_rules, TODAY
            )

        assert exc_info.value.rules == fake_game_with_invalid_game_rules.rules

    def test_rejects_unknown_result_code(self, fake_game: Game) -> None:
        player_with_unknown_result_code = fake_game.white.model_copy(
            update={"result": UNKNOWN_API_RESULT_CODE}
        )
        fake_game_with_unknown_result_code = fake_game.model_copy(
            update={"white": player_with_unknown_result_code}
        )

        with pytest.raises(
            UnknownResultError,
            match=f"{fake_game_with_unknown_result_code.url}.*{fake_game_with_unknown_result_code.white.result}",
        ) as exc_info:
            game_to_game_row(
                TEST_USERNAME_WHITE, fake_game_with_unknown_result_code, TODAY
            )

        assert exc_info.value.result_code == UNKNOWN_API_RESULT_CODE


class TestApiResultToResult:
    @pytest.mark.parametrize(
        ("api_result", "result"),
        [
            pytest.param(APIResult.WIN, Result.WIN, id="win"),
            pytest.param(APIResult.CHECKMATED, Result.LOSS, id="checkmated"),
            pytest.param(APIResult.RESIGNED, Result.LOSS, id="resigned"),
            pytest.param(APIResult.TIMEOUT, Result.LOSS, id="timeout"),
            pytest.param(APIResult.ABANDONED, Result.LOSS, id="abandoned"),
            pytest.param(APIResult.LOSE, Result.LOSS, id="lose"),
            pytest.param(APIResult.KINGOFTHEHILL, Result.LOSS, id="kingofthehill"),
            pytest.param(APIResult.THREECHECK, Result.LOSS, id="threecheck"),
            pytest.param(
                APIResult.BUGHOUSEPARTNERLOSE, Result.LOSS, id="bughousepartnerlose"
            ),
            pytest.param(APIResult.AGREED, Result.DRAW, id="agreed"),
            pytest.param(APIResult.REPETITION, Result.DRAW, id="repetition"),
            pytest.param(APIResult.INSUFFICIENT, Result.DRAW, id="insufficient"),
            pytest.param(APIResult.MOVE50, Result.DRAW, id="50move"),
            pytest.param(
                APIResult.TIMEVSINSUFFICIENT, Result.DRAW, id="timevsinsufficient"
            ),
            pytest.param(APIResult.STALEMATE, Result.DRAW, id="stalemate"),
        ],
    )
    def test_maps_each_code(self, api_result: APIResult, result: Result) -> None:
        assert api_result_to_result(api_result) == result

    def test_returns_none_for_unknown_code(self) -> None:
        assert api_result_to_result(UNKNOWN_API_RESULT_CODE) is None


class TestIsMonthComplete:
    @pytest.mark.parametrize(
        ("year", "month", "today", "expected"),
        [
            pytest.param(2026, 3, date(2026, 3, 15), False, id="during-month"),
            pytest.param(2026, 3, date(2026, 4, 1), False, id="just-before-boundary"),
            pytest.param(2026, 3, date(2026, 4, 2), True, id="exactly-at-boundary"),
            pytest.param(
                2026, 12, date(2027, 1, 2), True, id="december-rolls-into-next-year"
            ),
            pytest.param(2028, 2, date(2028, 3, 1), False, id="february-leap-year"),
            pytest.param(
                2026, 12, date(2026, 12, 15), False, id="december-before-boudary"
            ),
            pytest.param(
                2026, 11, date(2026, 12, 2), True, id="november-stays-in-same-year"
            ),
        ],
    )
    def test_returns_correct_value(
        self, year: int, month: int, today: date, expected: bool
    ) -> None:
        assert is_month_complete(year, month, today) == expected
