import io
from datetime import date
from typing import assert_never

import chess.pgn

from chesscom_fetch.models import APIResult, Colour, Game, GameRow, Result


def game_to_game_row(username: str, game: Game, fetch_date: date) -> GameRow:
    """Convert a Chess.com API game into a games-table row from one player's side.

    The player's colour and result are worked out from `username`. The move count
    comes from the game's PGN, and `fetch_date` is copied onto the row.

    Args:
        username: The player to view the game from.
        game: The game as returned by the Chess.com API.
        fetch_date: The date the game was fetched.

    Returns:
        The game as a row for the games table, from `username`'s side.

    Raises:
        ValueError: if the PGN contains no game or has parse errors, or if
            `username` is neither player in the game.
    """
    username = username.lower().strip()

    game_pgn = chess.pgn.read_game(io.StringIO(game.pgn))
    if game_pgn is None:
        raise ValueError("No game found in PGN")

    if game_pgn.errors:
        raise ValueError("Invalid game PGN")

    colour: Colour
    if game.white.username == username:
        colour = Colour.WHITE
    elif game.black.username == username:
        colour = Colour.BLACK
    else:
        raise ValueError("Username does not match that of the players in the game")

    result = game.white.result if colour == Colour.WHITE else game.black.result

    return GameRow(
        url=str(game.url),
        username=username,
        end_date=game.end_time.date().isoformat(),
        time_class=game.time_class,
        rated=game.rated,
        colour=colour,
        result=api_result_to_result(result),
        white_rating=game.white.rating,
        black_rating=game.black.rating,
        no_moves=(game_pgn.end().ply() + 1) // 2,
        pgn=game.pgn,
        fetch_date=fetch_date.isoformat(),
    )


def api_result_to_result(api_result: APIResult) -> Result:
    """Collapse a player's Chess.com result code into a win, loss or draw."""
    match api_result:
        case APIResult.WIN:
            return Result.WIN
        case (
            APIResult.CHECKMATED
            | APIResult.RESIGNED
            | APIResult.TIMEOUT
            | APIResult.ABANDONED
            | APIResult.LOSE
            | APIResult.KINGOFTHEHILL
            | APIResult.THREECHECK
            | APIResult.BUGHOUSEPARTNERLOSE
        ):
            return Result.LOSS
        case (
            APIResult.AGREED
            | APIResult.REPETITION
            | APIResult.INSUFFICIENT
            | APIResult.MOVE50
            | APIResult.TIMEVSINSUFFICIENT
            | APIResult.STALEMATE
        ):
            return Result.DRAW
        case _ as unreachable:
            assert_never(unreachable)
