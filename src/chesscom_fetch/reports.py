"""Read-only questions about a player's stored games."""

from dataclasses import dataclass
from pathlib import Path
from sqlite3 import Cursor

from chesscom_fetch.database import get_connection
from chesscom_fetch.domain import Colour, Result


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
