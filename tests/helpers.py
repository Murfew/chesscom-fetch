from collections.abc import Callable, Mapping
from datetime import date
from pathlib import Path
from typing import Protocol
from unittest.mock import MagicMock

from httpx2 import Request, Response, codes
from typer.testing import Result

from chesscom_fetch.db import get_connection
from chesscom_fetch.http import ChessClient
from chesscom_fetch.models import Game

type Handler = Callable[[Request], Response]
type PatchGetChessClient = Callable[[Mapping[str, Response]], list[str]]

TEST_USERNAME_WHITE = "testplayerwhite"
TEST_USERNAME_BLACK = "testplayerblack"
TEST_FETCH_DATE = date(2026, 11, 9)
TEST_ETAG = '"33a64df551425fcc55e4d42a148795d9f25f89d4"'
TEST_ARCHIVE_MONTH_URLS = [
    f"https://api.chess.com/pub/player/{TEST_USERNAME_WHITE}/games/2026/01",
    f"https://api.chess.com/pub/player/{TEST_USERNAME_WHITE}/games/2026/02",
    f"https://api.chess.com/pub/player/{TEST_USERNAME_WHITE}/games/2026/03",
]
ARCHIVE_LIST_URL = (
    f"https://api.chess.com/pub/player/{TEST_USERNAME_WHITE}/games/archives"
)
UNKNOWN_API_RESULT_CODE = "unknown"


class MakeChessClient(Protocol):
    def __call__(
        self, handler: Handler, wait_mock: MagicMock | None = ...
    ) -> ChessClient: ...


class GetFetchResult(Protocol):
    def __call__(
        self,
        response_by_url: Mapping[str, Response],
        extra_args: list[str] | None = ...,
    ) -> Result: ...


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


def count_games_table_rows(db_path: Path) -> int:
    with get_connection(db_path) as conn:
        return int(conn.execute("SELECT COUNT(*) FROM games").fetchone()[0])


def build_handler(
    response_by_url: Mapping[str, Response], requests_record: list[str]
) -> Handler:
    def _handler(request: Request) -> Response:
        requests_record.append(str(request.url))
        return response_by_url.get(str(request.url), Response(codes.NOT_FOUND))

    return _handler


def build_archive_url(year: int, month: int) -> str:
    return f"https://api.chess.com/pub/player/{TEST_USERNAME_WHITE}/games/{year}/{month:02d}"
