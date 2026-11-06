import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def get_connection(db_path: Path) -> Generator[sqlite3.Connection]:
    """Open a connection with foreign keys enforced, as one transaction.

    The transaction commits if the block finishes and rolls back if it raises.
    The connection is always closed afterwards.

    Args:
        db_path: Path to the SQLite database file.

    Yields:
        An open connection to the database.
    """
    conn = sqlite3.connect(db_path)

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
                time_class TEXT NOT NULL CHECK (time_class in ('bullet', 'blitz', 'rapid', 'daily')),
                rated BOOLEAN NOT NULL,
                colour TEXT NOT NULL CHECK (colour in ('black', 'white')),
                result TEXT NOT NULL CHECK (result in ('win', 'loss', 'draw')),
                white_rating INTEGER NOT NULL CHECK (white_rating >= 0 AND white_rating <= 4000),
                black_rating INTEGER NOT NULL CHECK (black_rating >= 0 AND black_rating <= 4000),
                no_moves INTEGER NOT NULL CHECK (no_moves >= 0 AND no_moves <= 10000),
                pgn TEXT NOT NULL,
                fetch_date TEXT NOT NULL,
                CONSTRAINT PK_games PRIMARY KEY (url, username)
            );
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS archive_states (
                url TEXT NOT NULL PRIMARY KEY,
                etag TEXT NOT NULL,
                complete BOOLEAN NOT NULL
            );
            """
        )
