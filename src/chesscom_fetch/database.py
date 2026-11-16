"""SQLite connection and schema, and the GameRow model that mirrors the games table."""

from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from sqlite3 import Connection, connect

from pydantic import BaseModel, ConfigDict, Field, NonNegativeInt

from chesscom_fetch.domain import MAX_RATING, Colour, Result, TimeClass

MAX_MOVE_COUNT = 10_000


class GameRow(BaseModel):
    """One row of the games table, seen from the fetched player's side."""

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
    move_count: NonNegativeInt = Field(le=MAX_MOVE_COUNT)
    pgn: str
    fetch_date: str  # YYYY-MM-DD
    eco: str | None = None
    eco_url: str | None = None
    opening_family: str = "Unknown"


@contextmanager
def get_connection(db_path: Path) -> Generator[Connection]:
    """Open a connection as one transaction.

    The transaction commits if the block finishes and rolls back if it raises.
    The connection is always closed afterwards.

    Args:
        db_path: Path to the SQLite database file.

    Yields:
        An open connection to the database.
    """
    conn = connect(db_path)

    try:
        with conn:
            yield conn
    finally:
        conn.close()


def init_db(db_path: Path) -> None:
    """Create the `games` and `archive_states` tables if they don't exist yet.

    Safe to call on every run: existing tables and data are left alone.

    Args:
        db_path: Path to the SQLite database file. Created if missing.
    """
    with get_connection(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS games (
                url TEXT NOT NULL,
                username TEXT NOT NULL,
                end_date TEXT NOT NULL,
                time_class TEXT NOT NULL
                    CHECK (time_class in ('bullet', 'blitz', 'rapid', 'daily')),
                rated BOOLEAN NOT NULL,
                colour TEXT NOT NULL CHECK (colour in ('black', 'white')),
                result TEXT NOT NULL CHECK (result in ('win', 'loss', 'draw')),
                white_rating INTEGER NOT NULL
                    CHECK (white_rating >= 0 AND white_rating <= 4000),
                black_rating INTEGER NOT NULL
                    CHECK (black_rating >= 0 AND black_rating <= 4000),
                move_count INTEGER NOT NULL CHECK (move_count >= 0 AND move_count <= 10000),
                pgn TEXT NOT NULL,
                fetch_date TEXT NOT NULL,
                eco TEXT,
                eco_url TEXT,
                opening_family TEXT NOT NULL DEFAULT 'Unknown',
                CONSTRAINT PK_games PRIMARY KEY (url, username)
            );
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS archive_states (
                url TEXT NOT NULL PRIMARY KEY,
                etag TEXT,
                complete BOOLEAN NOT NULL
            );
            """
        )
