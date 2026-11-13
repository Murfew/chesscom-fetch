import sqlite3
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Annotated, NamedTuple, NoReturn

import typer
from httpx2 import Client
from rich.console import Console
from rich.table import Table

from chesscom_fetch import db
from chesscom_fetch.http import ChessClient, ChessFetcherError
from chesscom_fetch.models import TimeClass
from chesscom_fetch.sync import SyncSummary, get_first_month_in_window, sync

app = typer.Typer()

console = Console()
err_console = Console(stderr=True)

DATABASE_PATH = Path(typer.get_app_dir("chesscom-fetch")) / "app.db"


class CliConfig(NamedTuple):
    """Settings shared by every command, stored on the Typer context.

    Attributes:
        db_path: Path to the SQLite database file.
    """

    db_path: Path


def _as_cli_config(value: object) -> CliConfig:
    """Return `ctx.obj` as a `CliConfig`; reject anything else (`main` didn't run)."""
    if not isinstance(value, CliConfig):
        raise TypeError(f"expected CliConfig, got {type(value).__name__}")
    return value


def _non_empty_lowercase_string(value: str) -> str:
    """Typer callback for names: reject blank text, else strip and lowercase it."""
    if not value.strip():
        raise typer.BadParameter("Value must not be empty.")
    return value.lower().strip()


def _get_chess_client(http_client: Client, username: str) -> ChessClient:
    """Build the Chess.com client; a separate function so tests can swap in a mock."""
    return ChessClient(http_client, username)


def _get_today() -> date:
    """Return today's date in UTC; a separate function so tests can fix the date."""
    return datetime.now(tz=UTC).date()


def _handle_error(err: Exception, message: str) -> NoReturn:
    """Print a one-line error to stderr and exit with code 1, chained to the cause."""
    err_console.print(f"[red]ERROR:[/red] {message}")
    raise typer.Exit(1) from err


def _print_header(
    time_classes: list[TimeClass], username: str, months: int, today: date
) -> None:
    start_sync_year, start_sync_month = get_first_month_in_window(today, months)
    start_sync_format = "%b" if start_sync_year == today.year else "%b %Y"

    end_of_range = today.strftime("%b %Y")
    start_of_range = date(start_sync_year, start_sync_month, 1).strftime(
        start_sync_format
    )
    sync_range = (start_of_range + "–" if months > 1 else "") + end_of_range  # ruff: ignore[ambiguous-unicode-character-string]
    filtered_time_classes = (
        ", ".join(time_classes)
        if len(time_classes) < len(list(TimeClass))
        else "all time classes"
    )
    username_display = f"Synced [bold]{username}[/bold]"
    header_parts = [username_display, sync_range, filtered_time_classes]

    console.print(f"{' · '.join(header_parts)}")


def _print_games_grid(summary: SyncSummary, time_classes: list[TimeClass]) -> None:
    games_grid = Table.grid(padding=(0, 2))
    games_grid.add_column()
    games_grid.add_column(justify="right", style="green")

    filtered_new_games = {
        time_class: summary.new_games[time_class]
        for time_class in list(TimeClass)
        if time_class in time_classes
    }

    total_new_games = sum(filtered_new_games.values())
    if total_new_games == 0:
        games_grid.add_row("No new games.")
    else:
        console.print("New games")
        for time_class, amount in filtered_new_games.items():
            if amount != 0:
                games_grid.add_row(f"  [dim]{time_class}[/dim]", f"{amount}")
        games_grid.add_row("  [dim]total[/dim]", f"{total_new_games}")

    console.print(games_grid)


def _print_details_grid(summary: SyncSummary) -> None:
    details_grid = Table.grid(padding=(0, 2))
    details_grid.add_column()
    details_grid.add_column()

    months_info = []
    if summary.months_unchanged != 0:
        months_info.append(f"{summary.months_unchanged} unchanged")
    if summary.months_completed != 0:
        months_info.append(f"{summary.months_completed} already complete")
    if len(months_info) != 0:
        details_grid.add_row(
            "Months",
            f"{' · '.join(months_info)}",
        )

    skipped_info = []
    if summary.game_variants != 0:
        skipped_info.append(f"[yellow]{summary.game_variants}[/yellow] variants")
    if summary.unreadable_games != 0:
        skipped_info.append(f"[yellow]{summary.unreadable_games}[/yellow] unreadable")
    if summary.username_mismatches != 0:
        skipped_info.append(
            f"[yellow]{summary.username_mismatches}[/yellow] username mismatches"
        )
    if summary.other != 0:
        skipped_info.append(f"[yellow]{summary.other}[/yellow] other")
    if len(skipped_info) != 0:
        skipped_info.append("[dim]all time classes[/dim]")
        details_grid.add_row(
            "Skipped",
            f"{' · '.join(skipped_info)}",
        )

    unknown_codes = []
    for code, count in summary.unknown_result_codes.items():
        unknown_codes.append(f"[yellow]{code} ({count})[/yellow]")
    if len(unknown_codes) != 0:
        details_grid.add_row(
            "", f"[dim]unknown result codes[/dim]: {', '.join(unknown_codes)}"
        )

    console.print(details_grid)


def _print_summary(
    summary: SyncSummary,
    time_classes: list[TimeClass],
    username: str,
    months: int,
    today: date,
) -> None:
    _print_header(time_classes, username, months, today)
    console.print()
    _print_games_grid(summary, time_classes)
    console.print()
    _print_details_grid(summary)


@app.callback()
def main(
    ctx: typer.Context,
    db_path: Annotated[
        Path,
        typer.Option(
            "--db",
            envvar="APP_DB_PATH",
            help="Path to the SQLite database file. Put it before the command.",
        ),
    ] = DATABASE_PATH,
) -> None:
    """Fetch your chess.com games into a local SQLite database.

    \f
    Runs before every command. Creates the folder that holds the database
    file, stores the path on `ctx.obj` as a `CliConfig` so commands can
    read it, and creates or opens the database.

    Args:
        ctx: The Typer context. Commands read the settings from `ctx.obj`.
        db_path: Path to the SQLite database file. Set it with `--db` or
            the `APP_DB_PATH` environment variable. Defaults to
            `DATABASE_PATH`.
    """  # ruff: ignore[escape-sequence-in-docstring]
    try:
        db_path.parent.mkdir(parents=True, exist_ok=True)
    except PermissionError as err:
        _handle_error(
            err,
            f"Can't create the folder for {db_path}: permission denied. Pass --db to use another location.",
        )

    except FileExistsError as err:
        _handle_error(
            err, f"Can't create {db_path}: a file is in the way of one of its folders."
        )

    ctx.obj = CliConfig(db_path)

    try:
        db.init_db(db_path)
    except sqlite3.DatabaseError as err:
        _handle_error(
            err,
            f"Can't open {db_path} as a database. Check the path, or pass --db to use another file.",
        )


@app.command()
def fetch(
    ctx: typer.Context,
    username: Annotated[
        str,
        typer.Argument(
            callback=_non_empty_lowercase_string, help="Chess.com username."
        ),
    ],
    months: Annotated[
        int,
        typer.Option(
            min=1,
            help="Number of months of data to fetch, including this one.",
        ),
    ] = 1,
    time_classes: Annotated[
        list[TimeClass] | None,
        typer.Option(
            "--time-class",
            help="Time class to include in the report. Repeat for more. Defaults to all.",
        ),
    ] = None,
) -> None:
    """Download a player's games from chess.com and save them to the database.

    \f
    Args:
        ctx: The Typer context; settings are read from `ctx.obj`.
        username: Chess.com username, stripped and lowercased.
        months: How many months to fetch, counting back from this one.
        time_classes: Time classes to include in the report. Every standard
            game is stored either way. Defaults to all.
    """  # ruff: ignore[escape-sequence-in-docstring]
    config = _as_cli_config(ctx.obj)

    if time_classes is None:
        time_classes = list(TimeClass)

    today = _get_today()

    with Client() as http_client:
        try:
            summary = sync(
                chess_client=_get_chess_client(http_client, username),
                db_path=config.db_path,
                username=username,
                months=months,
                today=today,
            )
        except (ChessFetcherError, sqlite3.Error) as err:
            _handle_error(err, str(err))

    _print_summary(summary, time_classes, username, months, today)
