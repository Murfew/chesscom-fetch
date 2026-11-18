"""Chess vocabulary shared by the Chess.com side and the database side."""

from enum import StrEnum

MAX_RATING = 4_000
GOOD_SCORE = 0.55  # Scores at or above this are shown in green.
BAD_SCORE = 0.45  # Scores at or below this are shown in red.
UNKNOWN_OPENING_FAMILY = (
    "Unknown"  # Stored when a game has no opening URL to name its family.
)


class TimeClass(StrEnum):
    """Chess.com time controls, matching the API's time_class values."""

    # Declaration order is the display order in reports and the fetch summary.

    DAILY = "daily"
    RAPID = "rapid"
    BLITZ = "blitz"
    BULLET = "bullet"


class Colour(StrEnum):
    """The side a player took in a game."""

    BLACK = "black"
    WHITE = "white"


class Result(StrEnum):
    """Outcome of a game from one player's perspective."""

    WIN = "win"
    LOSS = "loss"
    DRAW = "draw"
