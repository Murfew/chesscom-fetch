"""Typer commands and options that connect sync and the reports to the terminal."""

import re
import sqlite3
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Annotated, NamedTuple, NoReturn

import typer
from httpx2 import Client

from chesscom_fetch.client import ChessClient, ChessClientError
from chesscom_fetch.database import init_db
from chesscom_fetch.domain import Colour, TimeClass
from chesscom_fetch.render import (
    err_console,
    print_rating_history,
    print_record,
    print_sync_summary,
    print_top_openings,
)
from chesscom_fetch.reports import (
    get_monthly_ratings,
    get_most_played_openings,
    get_record,
)
from chesscom_fetch.sync import sync

app = typer.Typer()


DEFAULT_DB_PATH = Path(typer.get_app_dir("chesscom-fetch")) / "app.db"


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


def _parse_username(value: str) -> str:
    """Typer callback for names: reject blank text, else strip and lowercase it."""
    if not value.strip():
        raise typer.BadParameter("Value must not be empty.")
    if not bool(re.fullmatch(r"[A-Za-z0-9_-]+", value.strip())):
        raise typer.BadParameter(
            "Value can only be composed of letters, digits, '_' and '-'."
        )
    return value.lower().strip()


def _make_chess_client(http_client: Client, username: str) -> ChessClient:
    """Build the Chess.com client; a separate function so tests can swap in a mock."""
    return ChessClient(http_client, username)


def _today_utc() -> date:
    """Return today's date in UTC; a separate function so tests can fix the date."""
    return datetime.now(tz=UTC).date()


def _handle_error(err: Exception, message: str) -> NoReturn:
    """Print a one-line error to stderr and exit with code 1, chained to the cause."""
    err_console.print(f"[red]ERROR:[/red] {message}")
    raise typer.Exit(1) from err


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
    ] = DEFAULT_DB_PATH,
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
            `DEFAULT_DB_PATH`.
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
        init_db(db_path)
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
        typer.Argument(callback=_parse_username, help="Chess.com username."),
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

    today = _today_utc()

    with Client() as http_client:
        try:
            summary = sync(
                chess_client=_make_chess_client(http_client, username),
                db_path=config.db_path,
                username=username,
                months=months,
                today=today,
            )
        except (ChessClientError, sqlite3.Error) as err:
            _handle_error(err, str(err))

    print_sync_summary(summary, time_classes, username, months, today)


@app.command()
def score(
    ctx: typer.Context,
    username: Annotated[
        str,
        typer.Argument(callback=_parse_username, help="Chess.com username."),
    ],
) -> None:
    """Show a player's wins, draws, losses and score from saved games.

    Score counts a win as 1 point and a draw as ½, as a percentage of games played.

    Run `fetch` first; this command reads only the local database.

    \f
    Args:
        ctx: The Typer context; settings are read from `ctx.obj`.
        username: Chess.com username, stripped and lowercased.
    """  # ruff: ignore[escape-sequence-in-docstring]
    config = _as_cli_config(ctx.obj)
    print_record(username, get_record(config.db_path, username))


@app.command()
def top_openings(
    ctx: typer.Context,
    username: Annotated[
        str,
        typer.Argument(callback=_parse_username, help="Chess.com username."),
    ],
) -> None:
    """Show a player's five most-played opening families as White and as Black.

    Score counts a win as 1 point and a draw as ½, as a percentage of
    games played. Run `fetch` first; this command reads only the local
    database.

    \f
    Args:
        ctx: The Typer context; settings are read from `ctx.obj`.
        username: Chess.com username, stripped and lowercased.
    """  # ruff: ignore[escape-sequence-in-docstring]
    config = _as_cli_config(ctx.obj)
    record = get_record(config.db_path, username)
    white_openings = get_most_played_openings(config.db_path, username, Colour.WHITE)
    black_openings = get_most_played_openings(config.db_path, username, Colour.BLACK)
    print_top_openings(username, white_openings, black_openings, record)


@app.command()
def ratings(
    ctx: typer.Context,
    username: Annotated[
        str,
        typer.Argument(callback=_parse_username, help="Chess.com username."),
    ],
) -> None:
    """Show a player's average rating per month for each time class.

    Only rated games count, and the rating is the player's own, averaged
    over the games they finished that month. Time classes the player never
    played rated are left out. Run `fetch` first; this command reads only
    the local database.

    \f
    Args:
        ctx: The Typer context; settings are read from `ctx.obj`.
        username: Chess.com username, stripped and lowercased.
    """  # ruff: ignore[escape-sequence-in-docstring]
    config = _as_cli_config(ctx.obj)
    monthly_ratings = get_monthly_ratings(config.db_path, username)
    record = get_record(config.db_path, username)
    print_rating_history(username, monthly_ratings, record)
