import math
import time
from collections.abc import Callable

import httpx2
from httpx2 import URL
from pydantic import ValidationError

from chesscom_fetch.models import ArchiveList, ArchiveMonth

DEFAULT_RETRY_WAIT_TIME_SECONDS = 5
MAX_RETRY_WAIT_TIME_SECONDS = 30


class ChessFetcherError(Exception):
    """Base for all fetcher errors."""


class InvalidResponseError(ChessFetcherError):
    """Raised when Chess.com's response isn't the JSON shape the models expect."""

    def __init__(self, url: URL, detail: str) -> None:
        super().__init__(
            f"Response from {url} didn't match the expected format: {detail}"
        )


class FetchTimeoutError(ChessFetcherError):
    """Raised when Chess.com doesn't respond in time."""

    def __init__(self, url: URL) -> None:
        super().__init__(f"Request to {url} timed out.")


class PlayerNotFoundError(ChessFetcherError):
    """Raised when Chess.com has no data for the player or archive."""

    def __init__(self, username: str) -> None:
        super().__init__(
            f"No data found for '{username}'. Check the username or archive month."
        )


class RateLimitExhaustedError(ChessFetcherError):
    """Raised when Chess.com still answers 429 after retrying."""

    def __init__(self, host: str, attempts: int = 1) -> None:
        super().__init__(f"Rate limited by {host}; gave up after {attempts} retries.")


class ChessNetworkError(ChessFetcherError):
    """Raised when Chess.com can't be reached at all."""

    def __init__(self, host: str) -> None:
        super().__init__(f"Couldn't reach {host}. Check your connection and try again.")


def _retry_after_seconds(headers: httpx2.Headers) -> float:
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
            headers.get("Retry-After", DEFAULT_RETRY_WAIT_TIME_SECONDS)
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


class HttpClient:
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
        client: httpx2.Client,
        username: str,
        wait: Callable[[float], None] = time.sleep,
    ) -> None:
        self.client = client
        self.username = username
        self.wait = wait

        self.client.headers.update(
            {"User-Agent": "chesscom-fetch (matthew.hurley953@gmail.com)"}
        )
        self.client.base_url = f"https://api.chess.com/pub/player/{self.username}/games"

    def _get_once(self, url: str) -> httpx2.Response:
        """Send one GET request, turning network failures into fetcher errors.

        Args:
            url: The URL to fetch, absolute or relative to the player's base URL.

        Returns:
            The response.

        Raises:
            FetchTimeoutError: Chess.com didn't respond in time.
            ChessNetworkError: Chess.com couldn't be reached.
        """
        try:
            return self.client.get(url)
        except httpx2.TimeoutException as err:
            raise FetchTimeoutError(
                err.request.url,
            ) from err
        except httpx2.RequestError as err:
            raise ChessNetworkError(err.request.url.host) from err

    def _get_with_retry(self, url: str) -> httpx2.Response:
        """Send a GET request, retrying once if Chess.com answers 429.

        Waits for the time given in Retry-After, or the default wait if that header is
        missing, unreadable or out of range.

        Args:
            url: The URL to fetch, absolute or relative to the player's base URL.

        Returns:
            The response for any status that isn't 429.

        Raises:
            RateLimitExhaustedError: Chess.com still answered 429 after the retry.
            httpx2.HTTPStatusError: Any other error status, for the caller to interpret.
        """
        response = self._get_once(url)
        if response.status_code == httpx2.codes.TOO_MANY_REQUESTS:
            self.wait(_retry_after_seconds(response.headers))
            response = self._get_once(url)

        try:
            response.raise_for_status()
        except httpx2.HTTPStatusError as err:
            if err.response.status_code == httpx2.codes.TOO_MANY_REQUESTS:
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
            InvalidResponseError: The response body didn't match the expected format.
        """
        try:
            response = self._get_with_retry("/archives")

        except httpx2.HTTPStatusError as err:
            if err.response.status_code == httpx2.codes.NOT_FOUND:
                raise PlayerNotFoundError(self.username) from err

            raise ChessFetcherError(
                f"Unexpected response from {err.request.url}: HTTP {err.response.status_code}."
            ) from err
        try:
            return ArchiveList.model_validate_json(response.text)
        except ValidationError as err:
            raise InvalidResponseError(response.url, err.errors()[0]["msg"]) from err

    def get_archive_month(self, url: str, etag: str) -> tuple[ArchiveMonth, str] | None:
        """Fetch one month's games, sending the stored ETag.

        Args:
            url: The archive URL for the month.
            etag: The ETag saved from the last fetch of this month.

        Returns:
            The games and the new ETag, or None if Chess.com answered
            304 Not Modified.
        """
