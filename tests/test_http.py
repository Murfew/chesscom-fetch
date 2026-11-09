from typing import ClassVar

import httpx2

from chesscom_fetch.http import USER_AGENT
from tests.helpers import MakeHttpClient

TEST_USERNAME = "test-player"


class TestGetArchiveList:
    URLS: ClassVar[list[str]] = [
        f"https://api.chess.com/pub/player/{TEST_USERNAME}/games/2026/01",
        f"https://api.chess.com/pub/player/{TEST_USERNAME}/games/2026/02",
        f"https://api.chess.com/pub/player/{TEST_USERNAME}/games/2026/03",
    ]

    def test_returns_archives(
        self,
        make_http_client: MakeHttpClient,
    ) -> None:
        def handler(request: httpx2.Request) -> httpx2.Response:
            assert (
                request.url
                == f"https://api.chess.com/pub/player/{TEST_USERNAME}/games/archives"
            )

            return httpx2.Response(
                httpx2.codes.OK,
                json={"archives": self.URLS},
            )

        client = make_http_client(handler)
        archive_list = client.get_archive_list()

        assert [str(url) for url in archive_list.archives] == self.URLS

    def test_sends_user_agent(
        self,
        make_http_client: MakeHttpClient,
    ) -> None:
        def handler(request: httpx2.Request) -> httpx2.Response:

            assert request.headers.get("user-agent") == USER_AGENT

            return httpx2.Response(
                httpx2.codes.OK,
                json={"archives": self.URLS},
            )

        client = make_http_client(handler)
        client.get_archive_list()

    def test_raises_player_not_found_on_404(
        self,
        make_http_client: MakeHttpClient,
    ) -> None: ...
    def test_includes_url_and_status_on_unexpected_error(
        self,
        make_http_client: MakeHttpClient,
    ) -> None: ...


def test_get_with_retry_retries_once_after_429() -> None: ...
def test_get_with_retry_gives_up_after_second_429() -> None: ...
def test_get_archive_month_sends_if_none_match() -> None: ...
def test_get_archive_month_returns_none_on_304() -> None: ...
def test_retry_after_seconds_falls_back_on_bad_values() -> None: ...
