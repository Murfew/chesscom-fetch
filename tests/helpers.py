from collections.abc import Callable, Mapping
from datetime import date
from pathlib import Path
from typing import Protocol
from unittest.mock import MagicMock

from httpx2 import Request, Response, codes
from typer.testing import Result as RunnerResult

from chesscom_fetch.api_models import Game
from chesscom_fetch.client import ChessClient
from chesscom_fetch.database import GameRow, get_connection
from chesscom_fetch.domain import Colour, Result, TimeClass

# Players & Dates

USERNAME_WHITE = "testplayerwhite"  # white player from fake_game.json
USERNAME_BLACK = "testplayerblack"  # black player from fake_game.json
FETCH_DATE = date(2026, 11, 9)

# Chess.com API

PLAYER_GAMES_URL = f"https://api.chess.com/pub/player/{USERNAME_WHITE}/games"
ARCHIVE_MONTH_URLS = [
    f"{PLAYER_GAMES_URL}/2026/01",
    f"{PLAYER_GAMES_URL}/2026/02",
    f"{PLAYER_GAMES_URL}/2026/03",
]
ARCHIVE_LIST_URL = f"{PLAYER_GAMES_URL}/archives"
ETAG = '"33a64df551425fcc55e4d42a148795d9f25f89d4"'
UNKNOWN_API_RESULT_CODE = "unknown"

# Opening Families

FRENCH_DEFENSE = "French Defense"
CARO_KANN_DEFENSE = "Caro Kann Defense"
SCANDINAVIAN_DEFENSE = "Scandinavian Defense"
SICILIAN_DEFENSE = "Sicilian Defense"
VIENNA_GAMBIT = "Vienna Gambit"
LONDON_SYSTEM = "London System"

type Handler = Callable[[Request], Response]
type ResponseByUrl = Mapping[str, Response | Exception]
type PatchMakeChessClient = Callable[[ResponseByUrl], list[str]]


class MakeChessClient(Protocol):
    def __call__(
        self, handler: Handler, wait_mock: MagicMock | None = ...
    ) -> ChessClient: ...


class RunFetch(Protocol):
    def __call__(
        self,
        response_by_url: ResponseByUrl,
        extra_args: list[str] | None = ...,
    ) -> RunnerResult: ...


class BuildFakeGameRow(Protocol):
    def __call__(
        self,
        *,
        result: Result = ...,
        username: str = ...,
        opening_family: str = ...,
        colour: Colour = ...,
        end_date: str = ...,
        time_class: TimeClass = ...,
        rated: bool = ...,
        white_rating: int = ...,
        black_rating: int = ...,
    ) -> GameRow: ...


def count_games_table_rows(db_path: Path) -> int:
    with get_connection(db_path) as conn:
        return int(conn.execute("SELECT COUNT(*) FROM games").fetchone()[0])


def build_archive_month_response(
    games: list[Game], etag: str | None = None
) -> Response:
    headers = None if etag is None else {"etag": etag}

    return Response(
        codes.OK,
        json={"games": [game.model_dump(mode="json", by_alias=True) for game in games]},
        headers=headers,
    )


def build_archive_list_response(urls: list[str]) -> Response:
    return Response(codes.OK, json={"archives": urls})


def build_handler(response_by_url: ResponseByUrl, requested_urls: list[str]) -> Handler:
    def _handler(request: Request) -> Response:
        requested_urls.append(str(request.url))
        result = response_by_url.get(str(request.url), Response(codes.NOT_FOUND))
        if isinstance(result, Exception):
            raise result
        return result

    return _handler


def build_archive_url(year: int, month: int) -> str:
    return f"{PLAYER_GAMES_URL}/{year}/{month:02d}"
