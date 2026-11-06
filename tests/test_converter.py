from datetime import date

import pytest

from chesscom_fetch.converter import api_result_to_result, game_to_game_row
from chesscom_fetch.models import APIResult, Colour, Game, Result

TODAY = date.fromisoformat("2026-10-24")


@pytest.mark.parametrize(
    ("username", "expected_colour", "expected_result"),
    [
        pytest.param("TestPlayerWhite", Colour.WHITE, Result.LOSS),
        pytest.param("TestPlayerBlack", Colour.BLACK, Result.WIN),
    ],
)
def test_game_to_game_row_sets_colour_from_username(
    fake_game: Game, username: str, expected_colour: Colour, expected_result: Result
) -> None:
    game_row = game_to_game_row(username, fake_game, TODAY)
    assert game_row.colour == expected_colour
    assert game_row.result == expected_result


def test_game_to_game_row_rejects_username_not_in_game(fake_game: Game) -> None:
    with pytest.raises(
        ValueError, match="Username does not match that of the players in the game"
    ):
        game_to_game_row("TestPlayerNotInGame", fake_game, TODAY)


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
def test_game_to_game_row_counts_moves(
    fake_game: Game, new_pgn: str, expected_no_moves: int
) -> None:
    fake_game_with_modified_moves = fake_game.model_copy(update={"pgn": new_pgn})
    game_row = game_to_game_row("TestPlayerWhite", fake_game_with_modified_moves, TODAY)
    assert game_row.no_moves == expected_no_moves


def test_game_to_game_row_rejects_invalid_pgn(fake_game: Game) -> None:
    fake_game_with_illegal_pgn = fake_game.model_copy(
        update={"pgn": "1. e4 c6 2. d4 d5 3. e5 Bf5 4. Nf3 e6 5. Qh5 c5 6. O-O Nc6 0-1"}
    )

    with pytest.raises(ValueError, match="Invalid game PGN"):
        game_to_game_row("TestPlayerWhite", fake_game_with_illegal_pgn, TODAY)


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
def test_api_result_to_result_maps_each_code(
    api_result: APIResult, result: Result
) -> None:
    assert api_result_to_result(api_result) == result
