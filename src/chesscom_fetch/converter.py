import io
from calendar import DECEMBER
from datetime import date

import chess.pgn
from pydantic import HttpUrl

from chesscom_fetch.models import APIResult, Colour, Game, GameRow, Result

STANDARD_CHESS_RULES_CODE = "chess"


class GameSkippedError(Exception):
    """Base for reasons a single game is skipped instead of stored."""

    def __init__(self, url: HttpUrl, message: str) -> None:
        self.url = url

        super().__init__(f"Skipped {url}: {message}.")


class VariantGameError(GameSkippedError):
    """Raised when a game uses variant rules, not standard chess."""

    def __init__(self, url: HttpUrl, rules: str) -> None:
        self.rules = rules
        super().__init__(url, f"'{rules}' is a variant, not standard chess")


class UnknownResultError(GameSkippedError):
    """Raised when a player's result code isn't one the converter can map."""

    def __init__(self, url: HttpUrl, result_code: str) -> None:
        self.result_code = result_code
        super().__init__(url, f"unknown result code '{result_code}'")


class BadPGNError(GameSkippedError):
    """Raised when a game's PGN is missing or can't be parsed."""

    def __init__(self, url: HttpUrl, pgn: str) -> None:
        self.pgn = pgn
        super().__init__(url, "couldn't read the game's moves (PGN)")


class UsernameMismatchError(GameSkippedError):
    """Raised when the requested player is neither side of the game."""

    def __init__(self, url: HttpUrl, username: str) -> None:
        self.username = username
        super().__init__(url, f"'{username}' isn't either player in this game")


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
        VariantGameError: The game isn't standard chess.
        BadPGNError: The PGN contains no game or has parse errors.
        UsernameMismatchError: `username` is neither player in the game.
        UnknownResultError: The player's result code isn't one we can map.
    """
    username = username.lower().strip()

    if game.rules != STANDARD_CHESS_RULES_CODE:
        raise VariantGameError(game.url, game.rules)

    game_pgn = chess.pgn.read_game(io.StringIO(game.pgn))
    if game_pgn is None or game_pgn.errors:
        raise BadPGNError(game.url, game.pgn)

    colour: Colour
    if game.white.username == username:
        colour = Colour.WHITE
    elif game.black.username == username:
        colour = Colour.BLACK
    else:
        raise UsernameMismatchError(game.url, username)

    api_result_code = game.white.result if colour == Colour.WHITE else game.black.result

    result_code = api_result_to_result(api_result_code)
    if result_code is None:
        raise UnknownResultError(game.url, api_result_code)

    return GameRow(
        url=str(game.url),
        username=username,
        end_date=game.end_time.date().isoformat(),
        time_class=game.time_class,
        rated=game.rated,
        colour=colour,
        result=result_code,
        white_rating=game.white.rating,
        black_rating=game.black.rating,
        no_moves=(game_pgn.end().ply() + 1) // 2,
        pgn=game.pgn,
        fetch_date=fetch_date.isoformat(),
    )


def api_result_to_result(api_result: str) -> Result | None:
    """Collapse a player's Chess.com result code into a win, loss or draw.

    Args:
        api_result: The result code from the API, such as "checkmated".

    Returns:
        The win, loss or draw it maps to, or None if the code isn't recognised.
    """
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
        case _:
            return None


def is_month_complete(year: int, month: int, today: date) -> bool:
    """Return whether an archive month can no longer change.

    Chess.com can still add games to a month for up to 24 hours after it
    ends, so a month counts as complete from 00:00 UTC on the 2nd of the
    following month.

    Args:
        year: The archive's year, e.g. 2026.
        month: The archive's month, 1-12.
        today: Today's date in UTC.

    Returns:
        True if the month is complete, False if it may still change.
    """
    if month == DECEMBER:
        next_month = 1
        next_year = year + 1
    else:
        next_month = month + 1
        next_year = year

    target_date = date(next_year, next_month, 2)

    return today >= target_date
