"""Read-only questions about a player's stored games."""

from dataclasses import dataclass
from pathlib import Path
from sqlite3 import Cursor

from chesscom_fetch.database import get_connection
from chesscom_fetch.domain import Colour, Result, TimeClass


@dataclass
class Record:
    """Win, draw and loss counts for a set of a player's games.

    The set can be every stored game or a slice of them, such as one
    opening family played as one colour.

    Attributes:
        wins: Number of games the player won.
        draws: Number of games that ended in a draw.
        losses: Number of games the player lost.
    """

    wins: int = 0
    draws: int = 0
    losses: int = 0

    @property
    def points(self) -> float:
        """Points scored, counting 1 for a win and ½ for a draw, as chess does."""
        return self.wins + self.draws * 0.5

    @property
    def total_games(self) -> int:
        """Number of games in the record: wins, draws and losses together."""
        return self.wins + self.draws + self.losses

    @property
    def score(self) -> float | None:
        """Points as a fraction of games played, from 0 to 1; None if no games."""
        if self.total_games == 0:
            return None

        return self.points / self.total_games


@dataclass
class OpeningRecord:
    """A player's record in one opening family, played as one colour.

    Attributes:
        opening_family: The opening's family, such as "Sicilian Defense",
            so that all its variations count together. "Unknown" when the
            game had no opening URL.
        record: The player's wins, draws and losses in that family.
    """

    opening_family: str
    record: Record


def _to_opening_record(
    _cursor: Cursor, row: tuple[str, int, int, int]
) -> OpeningRecord:
    """Row factory that turns a raw result tuple into an `OpeningRecord`."""
    opening_family, wins, draws, losses = row
    return OpeningRecord(
        opening_family=opening_family,
        record=Record(wins=wins, draws=draws, losses=losses),
    )


@dataclass
class MonthlyRating:
    """A player's average rating in one time class over one calendar month.

    Attributes:
        year: Calendar year, such as 2026.
        month: Month number, 1 for January to 12 for December.
        time_class: The time class the rating belongs to.
        average_rating: Mean of the player's own rating across the month's
            rated games in this time class.
        total_games: How many rated games the average is taken over.
    """

    year: int
    month: int
    time_class: TimeClass
    average_rating: float
    total_games: int


def _to_monthly_rating(
    _cursor: Cursor, row: tuple[str, str, str, float, int]
) -> MonthlyRating:
    """Row factory that turns a raw result tuple into a `MonthlyRating`."""
    year, month, time_class, average_rating, total_games = row
    return MonthlyRating(
        year=int(year),
        month=int(month),
        time_class=TimeClass(time_class),
        average_rating=average_rating,
        total_games=total_games,
    )


def get_record(db_path: Path, username: str) -> Record:
    """Count a player's wins, draws and losses in the database.

    Only games already saved by `fetch` are counted; nothing is downloaded.

    Args:
        db_path: Path to the SQLite database file.
        username: Chess.com username, lowercased to match stored rows.

    Returns:
        The player's record. Every count is 0 if no games are stored.
    """
    with get_connection(db_path) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT result, COUNT(*) AS count FROM games
            WHERE username = ?
            GROUP BY result
            """,
            (username,),
        )
        raw_counts = dict(cur.fetchall())
        return Record(
            wins=raw_counts.get(Result.WIN, 0),
            draws=raw_counts.get(Result.DRAW, 0),
            losses=raw_counts.get(Result.LOSS, 0),
        )


def get_most_played_openings(
    db_path: Path, username: str, colour: Colour
) -> list[OpeningRecord]:
    """Return the five most-played opening families for one colour.

    Only games already saved by `fetch` are counted; nothing is downloaded.

    Args:
        db_path: Path to the SQLite database file.
        username: Chess.com username, lowercased to match stored rows.
        colour: The side the player had in the games to count.

    Returns:
        Up to five opening records, most-played first, with ties in
        alphabetical order of family. Empty if the player has no stored
        games as that colour.
    """
    with get_connection(db_path) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                opening_family,
                SUM(CASE WHEN result = :win THEN 1 ELSE 0 END) AS wins,
                SUM(CASE WHEN result = :draw THEN 1 ELSE 0 END) AS draws,
                SUM(CASE WHEN result = :loss THEN 1 ELSE 0 END) AS losses
            FROM games
            WHERE username = :username AND colour = :colour
            GROUP BY opening_family
            ORDER BY COUNT(*) DESC, opening_family
            LIMIT 5
            """,
            {
                "win": Result.WIN,
                "draw": Result.DRAW,
                "loss": Result.LOSS,
                "username": username,
                "colour": colour,
            },
        )
        cur.row_factory = _to_opening_record
        rows: list[OpeningRecord] = cur.fetchall()
        return rows


def get_monthly_ratings(db_path: Path, username: str) -> list[MonthlyRating]:
    """Average a player's rating per month and time class, from rated games only.

    The rating used is the player's own, from whichever side they played.
    Only games already saved by `fetch` are counted; nothing is downloaded.

    Args:
        db_path: Path to the SQLite database file.
        username: Chess.com username, lowercased to match stored rows.

    Returns:
        One entry per month and time class the player has rated games in,
        oldest month first, then time classes alphabetically. Display order is up to the
        caller. Empty if the player has no rated games.
    """
    with get_connection(db_path) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                strftime('%Y', end_date) AS year,
                strftime('%m', end_date) AS month,
                time_class,
                AVG(CASE WHEN colour = :white
                    THEN white_rating ELSE black_rating END) AS average_rating,
                COUNT(*) AS total_games FROM games
            WHERE username = :username AND rated = TRUE
            GROUP BY year, month, time_class
            ORDER BY year ASC, month ASC, time_class ASC
            """,
            {"username": username, "white": Colour.WHITE},
        )
        cur.row_factory = _to_monthly_rating
        rows: list[MonthlyRating] = cur.fetchall()
        return rows
