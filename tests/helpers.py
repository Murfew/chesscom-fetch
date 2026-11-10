from collections.abc import Callable
from datetime import date
from typing import Protocol
from unittest.mock import MagicMock

from httpx2 import Request, Response, codes

from chesscom_fetch.http import ChessClient
from chesscom_fetch.models import Archive

type Handler = Callable[[Request], Response]

TEST_USERNAME_WHITE = "testplayerwhite"
TEST_USERNAME_BLACK = "testplayerblack"
TEST_FETCH_DATE = date(2026, 11, 9)
TEST_ETAG = '"33a64df551425fcc55e4d42a148795d9f25f89d4"'
TEST_ARCHIVE_MONTH_URLS = [
    f"https://api.chess.com/pub/player/{TEST_USERNAME_WHITE}/games/2026/01",
    f"https://api.chess.com/pub/player/{TEST_USERNAME_WHITE}/games/2026/02",
    f"https://api.chess.com/pub/player/{TEST_USERNAME_WHITE}/games/2026/03",
]
TEST_ARCHIVES = [
    Archive(
        url=TEST_ARCHIVE_MONTH_URLS[0],
        year=2026,
        month=1,
    ),
    Archive(
        url=TEST_ARCHIVE_MONTH_URLS[1],
        year=2026,
        month=2,
    ),
    Archive(
        url=TEST_ARCHIVE_MONTH_URLS[2],
        year=2026,
        month=3,
    ),
]


class MakeChessClient(Protocol):
    def __call__(
        self, handler: Handler, wait_mock: MagicMock | None = ...
    ) -> ChessClient: ...


def build_429_response(retry_after: float) -> Response:
    return Response(
        status_code=codes.TOO_MANY_REQUESTS,
        headers={"retry-after": str(retry_after)},
    )
