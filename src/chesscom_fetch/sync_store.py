"""Reads and writes that sync needs: archive month states and new games."""

from collections.abc import Iterable
from dataclasses import asdict, dataclass
from sqlite3 import Connection, Cursor

from chesscom_fetch.database import GameRow


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
    """Return the stored state for one archive month.

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


def upsert_archive_state(conn: Connection, state: ArchiveStateRow) -> None:
    """Store an archive month's state, replacing any state already stored for it.

    Args:
        conn: SQLite database connection.
        state: The archive state to store. Its `url` decides which row is replaced.
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
            :white_rating, :black_rating, :move_count, :pgn, :fetch_date, :eco, :eco_url, :opening_family)
        ON CONFLICT DO NOTHING
        """,
        game_data,
    )

    return cur.rowcount
