"""Terminal output: turns sync summaries and reports into Rich tables."""

from datetime import date

from rich.console import Console
from rich.table import Table

from chesscom_fetch.domain import BAD_SCORE, GOOD_SCORE, TimeClass
from chesscom_fetch.reports import Record
from chesscom_fetch.sync import SyncSummary, first_month_in_window

console = Console()
err_console = Console(stderr=True)


def _print_sync_header(
    time_classes: list[TimeClass], username: str, months: int, today: date
) -> None:
    """Print the player, the months covered and the time classes shown."""
    start_sync_year, start_sync_month = first_month_in_window(today, months)
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


def _print_new_games(summary: SyncSummary, time_classes: list[TimeClass]) -> None:
    """Print new games per time class, or one line saying there were none."""
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


def _print_sync_details(summary: SyncSummary) -> None:
    """Print months left alone, games skipped and any unknown result codes."""
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


def _print_no_games(username: str) -> None:
    """Print a dim line saying the player has no saved games, and how to fetch them."""
    console.print(
        f"[dim]No games saved for {username}. Run `chesscom-fetch fetch {username}` to download them.[/dim]"
    )


def _print_report_header(title: str, username: str, total_games: int) -> None:
    """Print a report's title: its name, the player and its game count."""
    console.print(f"{title} for [bold]{username}[/bold] · {total_games} games")


def _report_grid() -> Table:
    """Return an empty grid: a dim label column, then two right-aligned columns."""
    grid = Table.grid(padding=(0, 2))
    grid.add_column(style="dim")
    grid.add_column(justify="right")
    grid.add_column(justify="right")

    return grid


def _score_style(score: float) -> str:
    """Return green for a good score, red for a bad one, else the default style."""
    if score >= GOOD_SCORE:
        return "green"
    if score <= BAD_SCORE:
        return "red"
    return "default"


def print_sync_summary(
    summary: SyncSummary,
    time_classes: list[TimeClass],
    username: str,
    months: int,
    today: date,
) -> None:
    """Print what a fetch run did: header, new games, then months and skips.

    Args:
        summary: What the sync run did.
        time_classes: Time classes to show new games for; the rest are hidden,
            though they were still stored.
        username: The player that was synced.
        months: How many months the run covered, for the header's date range.
        today: Today's date, the end of that range.
    """
    _print_sync_header(time_classes, username, months, today)
    console.print()
    _print_new_games(summary, time_classes)
    console.print()
    _print_sync_details(summary)


def print_record(username: str, record: Record) -> None:
    """Print a player's wins, draws, losses and score, or how to fetch games first.

    Args:
        username: The player, for the header and the empty-state hint.
        record: The player's record across all saved games.
    """
    if record.total_games == 0:
        _print_no_games(username)
        return

    _print_report_header("Record", username, record.total_games)
    console.print()

    record_grid = _report_grid()

    record_grid.add_row(
        "wins",
        str(record.wins),
        f"{record.wins / record.total_games:.1%}",
        style="green",
    )
    record_grid.add_row(
        "draws", str(record.draws), f"{record.draws / record.total_games:.1%}"
    )
    record_grid.add_row(
        "losses",
        str(record.losses),
        f"{record.losses / record.total_games:.1%}",
        style="red",
    )
    record_grid.add_row()

    score = record.score
    assert score is not None  # ruff: ignore[assert] -- the total_games == 0 return above rules out None
    score_style = _score_style(score)
    record_grid.add_row(
        "score",
        f"{record.points:g} / {record.total_games}",
        f"[{score_style}]{score:.1%}[/{score_style}]",
    )

    console.print(record_grid)
