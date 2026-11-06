from enum import StrEnum


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
