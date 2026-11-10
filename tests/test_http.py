from typing import ClassVar

import pytest
from httpx2 import Headers, Request, Response, codes
from pytest_mock import MockerFixture

from chesscom_fetch.http import (
    DEFAULT_RETRY_WAIT_TIME_SECONDS,
    MAX_RETRY_WAIT_TIME_SECONDS,
    USER_AGENT,
    ChessFetcherError,
    PlayerNotFoundError,
    RateLimitExhaustedError,
    _retry_after_seconds,
)
from chesscom_fetch.models import Archive, Game
from tests.helpers import (
    TEST_ARCHIVE_MONTH_URLS,
    TEST_ETAG,
    TEST_USERNAME_WHITE,
    MakeChessClient,
    build_429_response,
)

ARCHIVE_LIST_URL = (
    f"https://api.chess.com/pub/player/{TEST_USERNAME_WHITE}/games/archives"
)


class TestGetArchiveList:
    def test_returns_archives(
        self,
        make_http_client: MakeChessClient,
    ) -> None:
        def handler(request: Request) -> Response:
            assert request.url == ARCHIVE_LIST_URL

            return Response(
                codes.OK,
                json={"archives": TEST_ARCHIVE_MONTH_URLS},
            )

        client = make_http_client(handler)
        archive_list = client.get_archive_list()

        assert archive_list.archives == [
            Archive.model_validate(url) for url in TEST_ARCHIVE_MONTH_URLS
        ]

    def test_sends_user_agent(
        self,
        make_http_client: MakeChessClient,
    ) -> None:
        def handler(request: Request) -> Response:

            assert request.headers.get("user-agent") == USER_AGENT

            return Response(
                codes.OK,
                json={"archives": TEST_ARCHIVE_MONTH_URLS},
            )

        client = make_http_client(handler)
        client.get_archive_list()

    def test_raises_player_not_found_on_404(
        self,
        make_http_client: MakeChessClient,
    ) -> None:
        def handler(request: Request) -> Response:
            return Response(status_code=codes.NOT_FOUND)

        client = make_http_client(handler)
        with pytest.raises(
            PlayerNotFoundError,
            match=f"404.*{TEST_USERNAME_WHITE}",
        ):
            client.get_archive_list()

    def test_includes_url_and_status_on_unexpected_error(
        self,
        make_http_client: MakeChessClient,
    ) -> None:
        def handler(request: Request) -> Response:
            return Response(status_code=codes.INTERNAL_SERVER_ERROR)

        client = make_http_client(handler)
        with pytest.raises(ChessFetcherError, match=f"500.*{ARCHIVE_LIST_URL}"):
            client.get_archive_list()


class TestGetWithRetry:
    RETRY_AFTER: ClassVar[int] = 10

    def test_retries_once_after_429(
        self, make_http_client: MakeChessClient, mocker: MockerFixture
    ) -> None:
        requests: list[Request] = []
        responses = iter(
            [
                build_429_response(self.RETRY_AFTER),
                Response(
                    status_code=codes.OK, json={"archives": TEST_ARCHIVE_MONTH_URLS}
                ),
            ]
        )

        def handler(request: Request) -> Response:
            requests.append(request)
            return next(responses)

        wait_mock = mocker.MagicMock()
        client = make_http_client(handler, wait_mock)
        client.get_archive_list()

        wait_mock.assert_called_once_with(self.RETRY_AFTER)
        assert len(requests) == 2

    def test_gives_up_after_second_429(
        self, make_http_client: MakeChessClient, mocker: MockerFixture
    ) -> None:
        requests: list[Request] = []
        responses = iter(
            [
                build_429_response(self.RETRY_AFTER),
                build_429_response(self.RETRY_AFTER),
                Response(
                    status_code=codes.OK, json={"archives": TEST_ARCHIVE_MONTH_URLS}
                ),
            ]
        )

        def handler(request: Request) -> Response:
            requests.append(request)
            return next(responses)

        wait_mock = mocker.MagicMock()
        client = make_http_client(handler, wait_mock)

        with pytest.raises(RateLimitExhaustedError):
            client.get_archive_list()

        wait_mock.assert_called_once_with(self.RETRY_AFTER)
        assert len(requests) == 2


class TestGetArchiveMonth:
    def test_sends_if_none_match(
        self, make_http_client: MakeChessClient, fake_game: Game
    ) -> None:

        def handler(request: Request) -> Response:
            assert request.headers.get("if-none-match") == TEST_ETAG

            return Response(
                status_code=codes.OK,
                json={"games": [fake_game.model_dump(mode="json", by_alias=True)]},
            )

        client = make_http_client(handler)
        client.get_archive_month(TEST_ARCHIVE_MONTH_URLS[0], TEST_ETAG)

    def test_returns_none_on_304(self, make_http_client: MakeChessClient) -> None:
        def handler(request: Request) -> Response:
            return Response(
                status_code=codes.NOT_MODIFIED,
            )

        client = make_http_client(handler)
        assert client.get_archive_month(TEST_ARCHIVE_MONTH_URLS[0]) is None


class TestRetryAfterSeconds:
    @pytest.mark.parametrize(
        ("header_value", "expected_seconds"),
        [
            pytest.param("10", 10, id="normal-number"),
            pytest.param(
                str(MAX_RETRY_WAIT_TIME_SECONDS),
                MAX_RETRY_WAIT_TIME_SECONDS,
                id="exactly-maximum",
            ),
            pytest.param(
                str(MAX_RETRY_WAIT_TIME_SECONDS + 1),
                DEFAULT_RETRY_WAIT_TIME_SECONDS,
                id="just-over-maximum",
            ),
            pytest.param("-1", DEFAULT_RETRY_WAIT_TIME_SECONDS, id="negative-number"),
            pytest.param("nan", DEFAULT_RETRY_WAIT_TIME_SECONDS, id="nan"),
            pytest.param("inf", DEFAULT_RETRY_WAIT_TIME_SECONDS, id="inf"),
            pytest.param(
                "Mon, 09 Nov 2026 16:26:00 GMT",
                DEFAULT_RETRY_WAIT_TIME_SECONDS,
                id="HTTP-date",
            ),
            pytest.param(
                "sadasdasdafadfsd",
                DEFAULT_RETRY_WAIT_TIME_SECONDS,
                id="nonsense-string",
            ),
            pytest.param(None, DEFAULT_RETRY_WAIT_TIME_SECONDS, id="empty-header"),
        ],
    )
    def test_parses_or_falls_back(
        self, header_value: str | None, expected_seconds: float
    ) -> None:
        assert (
            _retry_after_seconds(
                Headers({"retry-after": header_value})
                if header_value is not None
                else Headers()
            )
            == expected_seconds
        )
