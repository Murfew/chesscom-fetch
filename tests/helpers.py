from collections.abc import Callable
from typing import Protocol
from unittest.mock import MagicMock

import httpx2

from chesscom_fetch.http import HttpClient

type Handler = Callable[[httpx2.Request], httpx2.Response]


class MakeHttpClient(Protocol):
    def __call__(
        self, handler: Handler, wait_mock: MagicMock | None = ...
    ) -> HttpClient: ...
