from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any, Self
from urllib.parse import urlparse
from uuid import UUID

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    NonNegativeInt,
    PositiveInt,
    StringConstraints,
    model_validator,
)

MAX_RATING = 4_000
MAX_NO_MOVES = 10_000


def _both_colours(d: dict[Colour, float]) -> dict[Colour, float]:
    """Reject an accuracies dict unless it has a value for both white and black."""
    missing = set(Colour) - d.keys()
    if missing:
        raise ValueError(f"missing keys: {sorted(missing)}")
    return d


class TimeClass(StrEnum):
    """Chess.com time controls, matching the API's time_class values."""

    BULLET = "bullet"
    BLITZ = "blitz"
    RAPID = "rapid"
    DAILY = "daily"


class Colour(StrEnum):
    """The side a player took in a game."""

    BLACK = "black"
    WHITE = "white"


class Result(StrEnum):
    """Outcome of a game from one player's perspective."""

    WIN = "win"
    LOSS = "loss"
    DRAW = "draw"


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


class GameRow(BaseModel):
    """One row of the games table, seen from the fetched player's side (username)."""

    model_config = ConfigDict(frozen=True)

    url: str
    username: str
    end_date: str  # YYYY-MM-DD
    time_class: TimeClass
    rated: bool
    colour: Colour
    result: Result
    white_rating: NonNegativeInt = Field(le=MAX_RATING)
    black_rating: NonNegativeInt = Field(le=MAX_RATING)
    no_moves: NonNegativeInt = Field(le=MAX_NO_MOVES)
    pgn: str
    fetch_date: str  # YYYY-MM-DD


class Game(BaseModel):
    """A single game as returned by the Chess.com API.

    Optional fields are left out by the API when they don't apply: accuracies only
    appears for analysed games, start_time only for daily games, and tournament or
    match only for games played as part of one.
    """

    url: HttpUrl
    pgn: str
    time_control: str
    end_time: datetime
    rated: bool
    accuracies: Annotated[dict[Colour, float], AfterValidator(_both_colours)] | None = (
        None
    )
    tcn: str
    uuid: UUID
    initial_setup: str
    fen: str
    start_time: datetime | None = None
    time_class: TimeClass
    rules: str
    white: Player
    black: Player
    eco: HttpUrl | None = None
    tournament: HttpUrl | None = None
    match: HttpUrl | None = None

    @model_validator(mode="after")
    def check_start_time_before_end_time(self) -> Self:
        """Reject games whose start_time is later than their end_time."""
        if self.start_time is not None and self.start_time > self.end_time:
            raise ValueError("Start time after end time")
        return self


class Player(BaseModel):
    """One side of a game as returned by the API.

    Holds the player's identity, their rating at the time, and their result code.
    """

    rating: NonNegativeInt = Field(le=MAX_RATING)
    result: str
    id: HttpUrl = Field(alias="@id")
    username: Annotated[str, StringConstraints(to_lower=True, strip_whitespace=True)]
    uuid: UUID


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
