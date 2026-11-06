import sqlite3
from pathlib import Path
from typing import Annotated, NamedTuple

import typer
from rich.console import Console

from chesscom_fetch import db
from chesscom_fetch.models import TimeClass

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

    Raises:
        typer.Exit: With code 1 if the folder can't be created, a file is
            in the way of the folder, or the file isn't a valid database.
    """  # ruff: ignore[escape-sequence-in-docstring]
    try:
        db_path.parent.mkdir(parents=True, exist_ok=True)
    except PermissionError as err:
        err_console.print(
            f"[red]ERROR:[/red] Can't create the folder for {db_path}: permission denied. Pass --db to use another location."
        )
        raise typer.Exit(1) from err
    except FileExistsError as err:
        err_console.print(
            f"[red]ERROR:[/red] Can't create {db_path}: a file is in the way of one of its folders."
        )
        raise typer.Exit(1) from err

    ctx.obj = CliConfig(db_path)

    try:
        db.init_db(db_path)
    except sqlite3.DatabaseError as err:
        err_console.print(
            f"[red]ERROR:[/red] Can't open {db_path} as a database. Check the path, or pass --db to use another file."
        )
        raise typer.Exit(1) from err


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
    time_class: Annotated[
        TimeClass, typer.Option(help="Time control of the games to fetch.")
    ] = TimeClass.RAPID,
) -> None:
    """Download a player's games from chess.com and save them to the database.

    \f
    Args:
        ctx: The Typer context; settings are read from `ctx.obj`.
        username: Chess.com username, stripped and lowercased.
        months: How many months to fetch, counting back from this one.
        time_class: Only games of this time control are saved.
    """  # ruff: ignore[escape-sequence-in-docstring]
    config = _as_cli_config(ctx.obj)
