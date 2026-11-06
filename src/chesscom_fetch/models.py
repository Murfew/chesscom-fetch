from enum import StrEnum


class TimeClass(StrEnum):
    """Chess.com time controls, matching the API's time_class values."""

    BULLET = "bullet"
    BLITZ = "blitz"
    RAPID = "rapid"
    DAILY = "daily"
