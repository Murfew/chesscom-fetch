"""Pydantic models that mirror the JSON from Chess.com's Published-Data API."""

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any
from urllib.parse import urlparse

from pydantic import (
    BaseModel,
    Field,
    HttpUrl,
    NonNegativeInt,
    PositiveInt,
    StringConstraints,
    model_validator,
)

from chesscom_fetch.domain import MAX_RATING, TimeClass


class APIResult(StrEnum):
    """Raw per-player result codes as returned by the Chess.com API."""

    WIN = "win"
    CHECKMATED = "checkmated"
    AGREED = "agreed"
    REPETITION = "repetition"
    TIMEOUT = "timeout"
    RESIGNED = "resigned"
    STALEMATE = "stalemate"
    LOSE = "lose"
    INSUFFICIENT = "insufficient"
    MOVE50 = "50move"
    ABANDONED = "abandoned"
    KINGOFTHEHILL = "kingofthehill"
    THREECHECK = "threecheck"
    TIMEVSINSUFFICIENT = "timevsinsufficient"
    BUGHOUSEPARTNERLOSE = "bughousepartnerlose"


class Game(BaseModel):
    """A single game as returned by the Chess.com API."""

    url: HttpUrl
    pgn: str
    end_time: datetime
    rated: bool
    time_class: TimeClass
    rules: str
    white: Player
    black: Player
    eco: HttpUrl | None = None


class Player(BaseModel):
    """One side of a game as returned by the API."""

    rating: NonNegativeInt = Field(le=MAX_RATING)
    result: str
    username: Annotated[str, StringConstraints(to_lower=True, strip_whitespace=True)]


class Archive(BaseModel):
    """One month in a player's archive list, parsed from its URL.

    Chess.com sends each archive as a URL ending in /YYYY/MM. The year and
    month are read from it so callers don't have to parse URLs themselves.
    """

    url: str
    year: NonNegativeInt
    month: PositiveInt = Field(le=12)

    @model_validator(mode="before")
    @classmethod
    def parse_url(cls, data: Any) -> dict[str, str | int]:
        """Turn the raw archive URL into url, year and month fields.

        Accepts the URL string Chess.com sends, or a dict with a "url" key
        (as when the model is built with keyword arguments). Year and month
        are always read from the URL so the three fields can't disagree.

        Returns:
            The url, year and month for normal field validation to check.

        Raises:
            ValueError: The input isn't a string or dict, has no url, or the
                URL doesn't end in a numeric /YYYY/MM.
        """
        if isinstance(data, dict):
            if "url" not in data:
                raise ValueError("'url' should be included")

            url = str(data["url"])
        elif isinstance(data, str):
            url = data
        else:
            raise ValueError("'data' must be either a dict or a string.")  # ruff: ignore[type-check-without-type-error]: Pydantic only converts ValueError into ValidationError

        parsed = urlparse(url)

        if parsed.hostname != "api.chess.com":
            raise ValueError("archive URL must have api.chess.com host")

        try:
            year, month = [int(value) for value in parsed.path.split("/")[-2:]]
        except ValueError as err:
            raise ValueError("archive URL must end in /YYYY/MM") from err

        return {"url": url, "year": year, "month": month}


class ArchiveList(BaseModel):
    """Response from the archives endpoint: one URL per month the player has games."""

    archives: list[Archive]


class ArchiveMonth(BaseModel):
    """Response from a monthly archive URL.

    Contains every game the player finished in that month.
    """

    games: list[Game]
