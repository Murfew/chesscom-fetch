from collections.abc import Callable
from typing import Protocol
from unittest.mock import MagicMock

from httpx2 import Request, Response, codes

from chesscom_fetch.http import HttpClient

type Handler = Callable[[Request], Response]

TEST_USERNAME = "test-player"


class MakeHttpClient(Protocol):
    def __call__(
        self, handler: Handler, wait_mock: MagicMock | None = ...
    ) -> HttpClient: ...


def build_429_response(retry_after: float) -> Response:
    return Response(
        status_code=codes.TOO_MANY_REQUESTS,
        headers={"retry-after": str(retry_after)},
    )
