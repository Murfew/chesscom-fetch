# chesscom-fetch

A command-line tool that downloads a player's Chess.com games into a local SQLite
database, fetching only the games it doesn't already have.

> Not affiliated with or endorsed by Chess.com. It uses Chess.com's public,
> read-only [Published-Data API](https://www.chess.com/news/view/published-data-api).

<!-- TODO: one short paragraph on why this exists: your games in your own database,
     ready for SQL reports now and for the chess coach's importer later. -->

## Features

- Downloads games month by month from the player's Chess.com archives
- Re-running adds only new games, never duplicates
- Skips months it has already stored, and asks for the current month with
  `If-None-Match` so an unchanged archive costs a quick `304`
- Stores standard chess only; variants such as Chess960 are skipped and counted
- Turns each side's result code into a win, draw or loss, and reports any code it
  doesn't recognise
- SQL reports: your score as White and as Black, your most-played openings, and
  your rating by month

## Requirements

- Python 3.14+
- [uv](https://docs.astral.sh/uv/)

## Installation

```bash
git clone https://github.com/Murfew/chesscom-fetch.git
cd chesscom-fetch
uv sync
```

<!-- TODO: check these steps in a fresh clone before you commit them. -->

## Configuration

<!-- TODO: list each setting, its default, and how to change it (an option, an
     environment variable or a config file). The spec says these are settings,
     not hard-coded values:
       - username
       - how many months back to fetch
       - which time classes to keep (bullet, blitz, rapid, daily)
       - the database file's path
       - the contact email sent in the User-Agent -->

| Setting | Default | How to set it |
| ------- | ------- | ------------- |
| TODO    | TODO    | TODO          |

## Usage

### Fetch games

```bash
uv run chesscom-fetch fetch <username>
```

<!-- TODO: paste real output from your terminal, including the variants-skipped
     count. Add one example that uses the months-back and time-class options. -->

```text
TODO: real output
```

Running it again adds only games that weren't there before:

```text
TODO: real output from a second run
```

### Reports

<!-- TODO: one subsection per report command: what question it answers, the
     command, and real output. Explain how the score works: a draw counts as
     half a point. -->

#### Score by colour

```bash
TODO
```

#### Most-played openings

```bash
TODO
```

#### Rating by month

```bash
TODO
```

## What gets stored

<!-- TODO: describe your tables in plain language once you've designed them. The
     spec says one row per game, with: its URL (the id), end date, time class,
     rated or not, your colour, the result (win, draw or loss), both ratings, the
     ECO code and opening, the number of moves, the PGN, and when it was fetched.
     Also mention the per-month archive state (ETag and whether the month is
     complete). -->

## How it treats Chess.com's API

- Sends requests one at a time, never in parallel
- Waits and retries once after a `429 Too Many Requests`
- Sends a User-Agent with the app's name and a contact email, as Chess.com asks
- Reuses each month's `ETag` so unchanged archives aren't downloaded again
- Checks every response with Pydantic before anything is written to the database

Chess.com refreshes archives every 12 to 24 hours, so a game you just played may
not show up yet.

## Error handling

A network error, timeout, unknown username or unexpected response prints a
one-line message and exits with a non-zero code instead of a traceback.

<!-- TODO: show one real example, such as an unknown username. -->

## Development

```bash
uv run pytest          # tests (none of them call Chess.com)
uv run ruff check .    # lint
uv run ruff format .   # format
uv run mypy .          # type check (strict)
```

<!-- TODO: say where the saved archive files the tests parse are kept. -->

## Design decisions

<!-- TODO: a few lines each, explaining *why*:
     - Primary key: why the game URL, and how `ON CONFLICT DO NOTHING` prevents
       duplicates without checking first
     - Archive state: where each month's ETag and "complete" flag live
     - Models: which Pydantic models match Chess.com's JSON, which match your
       table, and where one is converted into the other
     - HTTP layer: why all requests go through one place (User-Agent, one at a
       time, the 429 retry) -->

## Out of scope

- Lichess or other sites
- Fetching many players at once
- Game analysis (that comes later, in the coach)

## License

[MIT](LICENSE)
