from calendar import DECEMBER
from collections import Counter, defaultdict
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from chesscom_fetch.converter import (
    BadPGNError,
    GameSkippedError,
    UnknownResultError,
    UsernameMismatchError,
    VariantGameError,
    game_to_game_row,
)
from chesscom_fetch.db import (
    ArchiveStateRow,
    add_archive_state,
    add_games,
    get_archive_state,
    get_connection,
)
from chesscom_fetch.http import ChessClient
from chesscom_fetch.models import Archive, Game, GameRow, TimeClass

MONTHS_PER_YEAR = 12


def _is_archive_in_window(months: int, archive: Archive, today: date) -> bool:
    """Return whether an archive is within the last months months, inclusive."""
    archive_total_months = archive.year * MONTHS_PER_YEAR + archive.month
    today_total_months = today.year * MONTHS_PER_YEAR + today.month

    return archive_total_months >= (today_total_months - (months - 1))


def _is_month_complete(archive: Archive, today: date) -> bool:
    """Return whether an archive month can no longer change."""
    if archive.month == DECEMBER:
        month = 1
        year = archive.year + 1
    else:
        month = archive.month + 1
        year = archive.year

    target_date = date(year, month, 2)

    return today >= target_date


def _group_games_by_time_class(
    games: list[Game], username: str, today: date, summary: SyncSummary
) -> Mapping[TimeClass, list[GameRow]]:
    game_rows_by_time_class: defaultdict[TimeClass, list[GameRow]] = defaultdict(list)

    for game in games:
        try:
            game_row = game_to_game_row(username, game, today)
        except VariantGameError:
            summary.game_variants += 1
        except UnknownResultError as err:
            summary.unknown_result_codes[err.result_code] += 1
        except BadPGNError:
            summary.unreadable_games += 1
        except UsernameMismatchError:
            summary.username_mismatches += 1
        except GameSkippedError:
            summary.other += 1
        else:
            game_rows_by_time_class[game_row.time_class].append(game_row)

    return game_rows_by_time_class


@dataclass
class SyncSummary:
    """What one sync run did, filled in as it goes.

    Attributes:
        new_games: Newly stored games, per time class.
        months_unchanged: Months Chess.com answered 304 Not Modified for.
        months_skipped_completed: Months skipped without a request because
            they can no longer change.
        variants_skipped: Games skipped for not being standard chess.
        unreadable_games: Games skipped because their PGN couldn't be read.
        username_mismatches: Games skipped because the player wasn't in them.
        unknown_result_codes: Result codes that couldn't be mapped, with how
            often each appeared.
    """

    new_games: Counter[TimeClass] = field(default_factory=Counter)
    months_unchanged: int = 0
    months_completed: int = 0
    game_variants: int = 0
    unreadable_games: int = 0
    username_mismatches: int = 0
    unknown_result_codes: Counter[str] = field(default_factory=Counter)
    other: int = 0


def sync(
    *,
    chess_client: ChessClient,
    db_path: Path,
    username: str,
    months: int,
    today: date,
) -> SyncSummary:
    """Bring the database up to date with a player's Chess.com archives.

    Looks at the archive months in the `months` window. Months already
    marked complete are skipped without a request, and months Chess.com
    reports as unchanged (304) are left alone. For every other month, the
    standard games are stored and the month's state is saved in one
    transaction. Games that can't be stored are skipped and counted.

    Args:
        chess_client: Client for the player's Chess.com archives.
        db_path: Path to the SQLite database file.
        username: The player, lowercased.
        months: How many months to look at, including the current one.
        today: Today's date in UTC.

    Returns:
        What the run did: new games per time class, and what was skipped.
    """
    summary = SyncSummary()

    archive_list = chess_client.get_archive_list()
    for archive in archive_list.archives:
        if not _is_archive_in_window(months, archive, today):
            continue

        with get_connection(db_path) as conn:
            month_state = get_archive_state(conn, archive.url)

        if month_state is None:
            etag = None
        else:
            if month_state.complete:
                summary.months_completed += 1
                continue
            etag = month_state.etag

        archive_month_response = chess_client.get_archive_month(archive.url, etag)
        if archive_month_response is None:
            summary.months_unchanged += 1
            continue

        archive_month, new_etag = archive_month_response
        game_rows_by_time_class = _group_games_by_time_class(
            archive_month.games, username, today, summary
        )

        with get_connection(db_path) as conn:
            add_archive_state(
                conn,
                ArchiveStateRow(
                    url=archive.url,
                    etag=new_etag,
                    complete=_is_month_complete(archive, today),
                ),
            )

            for time_class, game_rows in game_rows_by_time_class.items():
                summary.new_games[time_class] += add_games(
                    conn,
                    game_rows,
                )

    return summary
