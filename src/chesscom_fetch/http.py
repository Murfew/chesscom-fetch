import math
import time
from collections.abc import Callable, Mapping
from typing import override

from httpx2 import (
    URL,
    Client,
    Headers,
    HTTPStatusError,
    RequestError,
    Response,
    TimeoutException,
    codes,
)
from pydantic import BaseModel, ValidationError

from chesscom_fetch.models import ArchiveList, ArchiveMonth

DEFAULT_RETRY_WAIT_TIME_SECONDS = 5
MAX_RETRY_WAIT_TIME_SECONDS = 30
USER_AGENT = "chesscom-fetch (matthew.hurley953@gmail.com)"


class ChessFetcherError(Exception):
    """Base for all fetcher errors."""

    def __init__(
        self,
        message: str | None = None,
        *,
        error_code: int,
        url: URL | None = None,
    ) -> None:
        self.error_code = error_code
        self.url = url
        if message is None:
            if url is not None:
                message = f"Unexpected response from {url}."
            else:
                message = "Unexpected error while fetching from Chess.com."
        super().__init__(message)

    @override
    def __str__(self) -> str:
        return f"[{self.error_code}] {super().__str__()}"


class InvalidResponseError(ChessFetcherError):
    """Raised when Chess.com's response isn't the JSON shape the models expect."""

    def __init__(self, url: URL, detail: str) -> None:
        self.detail = detail
        super().__init__(
            f"Response from {url} didn't match the expected format: {detail}",
            error_code=codes.BAD_GATEWAY,
            url=url,
        )


class FetchTimeoutError(ChessFetcherError):
    """Raised when Chess.com doesn't respond in time."""

    def __init__(self, url: URL) -> None:
        super().__init__(
            f"Request to {url} timed out.",
            error_code=codes.GATEWAY_TIMEOUT,
            url=url,
        )


class PlayerNotFoundError(ChessFetcherError):
    """Raised when Chess.com has no data for the player or archive."""

    def __init__(self, username: str) -> None:
        self.username = username
        super().__init__(
            f"No data found for '{username}'. Check the username or archive month.",
            error_code=codes.NOT_FOUND,
        )


class RateLimitExhaustedError(ChessFetcherError):
    """Raised when Chess.com still answers 429 after retrying."""

    def __init__(self, host: str, attempts: int = 1) -> None:
        self.host = host
        self.attempts = attempts
        plural = "" if attempts == 1 else "s"
        super().__init__(
            f"Rate limited by {host}; gave up after {attempts} attempt{plural}.",
            error_code=codes.TOO_MANY_REQUESTS,
        )


class ChessNetworkError(ChessFetcherError):
    """Raised when Chess.com can't be reached at all."""

    def __init__(self, host: str) -> None:
        self.host = host
        super().__init__(
            f"Couldn't reach {host}. Check your connection and try again.",
            error_code=codes.BAD_GATEWAY,
        )


def _retry_after_seconds(headers: Headers) -> float:
    """Return how many seconds to wait before retrying a 429.

    Reads the Retry-After header as a number of seconds. Falls back to the
    default wait when the header is missing, isn't a number, or is out of range.

    Args:
        headers: The headers of the 429 response.

    Returns:
        The number of seconds to wait.
    """
    try:
        time_to_wait = float(
            headers.get("retry-after", DEFAULT_RETRY_WAIT_TIME_SECONDS)
        )
    except ValueError:
        time_to_wait = DEFAULT_RETRY_WAIT_TIME_SECONDS

    if (
        not math.isfinite(time_to_wait)
        or time_to_wait < 0
        or time_to_wait > MAX_RETRY_WAIT_TIME_SECONDS
    ):
        time_to_wait = DEFAULT_RETRY_WAIT_TIME_SECONDS

    return time_to_wait


def _validate_response_format[T: BaseModel](response: Response, model: type[T]) -> T:
    try:
        return model.model_validate_json(response.text)
    except ValidationError as err:
        raise InvalidResponseError(response.url, err.errors()[0]["msg"]) from err


class ChessClient:
    """Fetch Chess.com archive data for one player, one request at a time.

    Wraps an injected httpx client so tests can swap in a fake transport.
    Sets the User-Agent and handles 429 responses.

    Args:
        client: The httpx client to send requests with. Tests pass one
            built on a mock transport.
        username: The Chess.com username, lowercased.
    """

    def __init__(
        self,
        client: Client,
        username: str,
        wait: Callable[[float], None] = time.sleep,
    ) -> None:
        self.client = client
        self.username = username
        self.wait = wait

        self.client.headers.update({"user-agent": USER_AGENT})
        self.client.base_url = f"https://api.chess.com/pub/player/{self.username}/games"

    def _get_once(self, url: str, headers: Mapping[str, str] | None = None) -> Response:
        """Send one GET request, turning network failures into fetcher errors.

        Args:
            url: The URL to fetch, absolute or relative to the player's base URL.
            headers: Extra request headers, such as If-None-Match.

        Returns:
            The response.

        Raises:
            FetchTimeoutError: Chess.com didn't respond in time.
            ChessNetworkError: Chess.com couldn't be reached.
        """
        try:
            return self.client.get(url, headers=headers)
        except TimeoutException as err:
            raise FetchTimeoutError(
                err.request.url,
            ) from err
        except RequestError as err:
            raise ChessNetworkError(err.request.url.host) from err

    def _get_with_retry(
        self, url: str, headers: dict[str, str] | None = None
    ) -> Response:
        """Send a GET request, retrying once if Chess.com answers 429.

        Waits for the time given in Retry-After, or the default wait if that header is
        missing, unreadable or out of range.

        Args:
            url: The URL to fetch, absolute or relative to the player's base URL.
            headers: Extra request headers, such as If-None-Match.

        Returns:
            The response for any status that isn't 429.

        Raises:
            RateLimitExhaustedError: Chess.com still answered 429 after the retry.
            HTTPStatusError: Any other error status, for the caller to interpret.
        """
        response = self._get_once(url, headers)
        if response.status_code == codes.TOO_MANY_REQUESTS:
            self.wait(_retry_after_seconds(response.headers))
            response = self._get_once(url, headers)

        try:
            response.raise_for_status()
        except HTTPStatusError as err:
            if err.response.status_code == codes.TOO_MANY_REQUESTS:
                raise RateLimitExhaustedError(err.response.url.host) from err

            raise
        else:
            return response

    def get_archive_list(self) -> ArchiveList:
        """Return the list of monthly archive URLs for the player.

        Returns:
            The player's archive list.

        Raises:
            PlayerNotFoundError: Chess.com has no player with this username.
            ChessFetcherError: Chess.com answered with any other error status.
        """
        try:
            response = self._get_with_retry("/archives")

        except HTTPStatusError as err:
            if err.response.status_code == codes.NOT_FOUND:
                raise PlayerNotFoundError(self.username) from err

            raise ChessFetcherError(
                url=err.request.url, error_code=err.response.status_code
            ) from err

        return _validate_response_format(response, ArchiveList)

    def get_archive_month(
        self, url: str, etag: str | None = None
    ) -> tuple[ArchiveMonth, str | None] | None:
        """Fetch one month's games, sending the stored ETag.

        Args:
            url: The archive URL for the month.
            etag: The ETag saved from the last fetch of this month.

        Returns:
            The games and the new ETag, or None if Chess.com answered
            304 Not Modified.

        Raises:
            ChessFetcherError: Chess.com answered with any other error status.
        """
        try:
            response = self._get_with_retry(
                url, {"if-none-match": etag} if etag else None
            )
        except HTTPStatusError as err:
            if err.response.status_code == codes.NOT_MODIFIED:
                return None

            raise ChessFetcherError(
                url=err.request.url, error_code=err.response.status_code
            ) from err

        return (
            _validate_response_format(response, ArchiveMonth),
            response.headers.get("etag"),
        )
