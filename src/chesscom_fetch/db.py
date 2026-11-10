from collections.abc import Generator, Iterable
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from sqlite3 import Connection, Cursor, connect

from chesscom_fetch.models import GameRow


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
                etag TEXT,
                complete BOOLEAN NOT NULL
            );
            """
        )


@dataclass
class ArchiveStateRow:
    """One row of the `archive_states` table.

    Attributes:
        url: The archive month's URL, used as the primary key.
        etag: The ETag last returned for this archive.
        complete: Whether the month is finished and won't change again.
    """

    url: str
    etag: str | None
    complete: bool


def _to_archive_state_row(
    _cursor: Cursor, row: tuple[str, str | None, int]
) -> ArchiveStateRow:
    """Row factory that turns a raw result tuple into an `ArchiveStateRow`."""
    url, etag, complete = row

    return ArchiveStateRow(url, etag, bool(complete))


def get_archive_state(conn: Connection, url: str) -> ArchiveStateRow | None:
    """Fetch the stored state for one archive month.

    Args:
        conn: SQLite database connection.
        url: The archive month's URL.

    Returns:
        The stored state, or None if this month has never been fetched.
    """
    cur = conn.cursor()
    cur.execute("SELECT * FROM archive_states WHERE url = ?", (url,))
    cur.row_factory = _to_archive_state_row
    row: ArchiveStateRow | None = cur.fetchone()
    return row


def add_archive_state(conn: Connection, state: ArchiveStateRow) -> None:
    """Insert a new archive state.

    Args:
        conn: SQLite database connection.
        state: The archive state to store.
    """
    conn.execute(
        """
        INSERT INTO archive_states VALUES (:url, :etag, :complete)
        ON CONFLICT (url)
        DO UPDATE SET etag = EXCLUDED.etag, complete = EXCLUDED.complete
        """,
        asdict(state),
    )


def add_games(conn: Connection, games: Iterable[GameRow]) -> int:
    """Insert games, skipping any already stored for this player.

    Args:
        conn: SQLite database connection.
        games: The games to store.

    Returns:
        How many games were newly inserted. Duplicates are not counted.
    """
    cur = conn.cursor()
    game_data = (game.model_dump() for game in games)

    cur.executemany(
        """
        INSERT INTO games VALUES
            (:url, :username, :end_date, :time_class, :rated, :colour, :result,
            :white_rating, :black_rating, :no_moves, :pgn, :fetch_date)
        ON CONFLICT DO NOTHING
        """,
        game_data,
    )

    return cur.rowcount
