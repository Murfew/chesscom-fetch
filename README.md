# chesscom-fetch

A command-line tool that downloads a player's Chess.com games into a local SQLite
database, fetching only the games it doesn't already have, then reports their
results, openings and rating history from that database.

> Not affiliated with or endorsed by Chess.com. It uses Chess.com's public,
> read-only [Published-Data API](https://www.chess.com/news/view/published-data-api).

Chess.com shows your games one page at a time, which makes it hard to answer
questions about your own play. This tool keeps a copy of your games in a SQLite
file you own. Three built-in reports answer the common questions, and you can query
the file with plain SQL for anything else. Later, a chess coach project will read
its games from this same database.

## Features

- Re-running adds only new games, never duplicates
- Skips finished months it already has, and uses `ETag`s so an unchanged month
  costs a quick `304`
- Groups every variation of an opening into one family, so the Najdorf and the
  Dragon both count as the Sicilian Defense
- Reports run offline, straight from the database

## Requirements

- Python 3.14+
- [uv](https://docs.astral.sh/uv/)

## Installation

```bash
git clone https://github.com/Murfew/chesscom-fetch.git
cd chesscom-fetch
uv sync
```

## Commands

| Command | What it does | Uses the network |
| ------- | ------------ | ---------------- |
| `fetch <username>` | Downloads the player's games into the database | Yes |
| `score <username>` | Wins, draws, losses and score as White and as Black | No |
| `top-openings <username>` | The five most-played opening families as White and as Black | No |
| `ratings <username>` | Average rating per month for each time class | No |

The three reports only read the database, so run `fetch` first. If there are no
saved games for that player, they say so and tell you the `fetch` command to run.

Usernames are case-insensitive and may only contain letters, digits, `_` and `-`.

## Configuration

| Setting | Default | How to set it |
| ------- | ------- | ------------- |
| Username | none (required) | The first argument to every command |
| Months to fetch | `1` (this month only) | `fetch --months N`, counting back from and including this month |
| Time classes in the fetch summary | all four | `fetch --time-class blitz`, repeat for more: `--time-class blitz --time-class rapid` |
| Database file | `app.db` in the app folder Typer picks for your OS (`~/.config/chesscom-fetch/` on Linux) | `--db PATH` before the command, or the `APP_DB_PATH` environment variable |
| Contact email in the User-Agent | the author's email | `USER_AGENT` in `src/chesscom_fetch/client.py`; change it if you run your own copy |

`--time-class` only filters the summary that's printed. Every standard game is
stored, whatever its time class. Months that are finished are never fetched again,
so if the option also filtered what gets stored, games left out on one run could
never be added on a later one.

## Usage

### Fetch games

```bash
uv run chesscom-fetch fetch <username>
uv run chesscom-fetch fetch <username> --months 3 --time-class blitz --time-class rapid
uv run chesscom-fetch --db ./games.db fetch <username>
```

Fetching the last two months for a public player:

```text
$ uv run chesscom-fetch fetch hikaru --months 2
Synced hikaru · Oct–Nov 2026 · all time classes

New games
  blitz   448
  bullet  479
  total   927
```

Running it again adds only games that weren't there before. October has ended, so
it's skipped without a request. November hasn't changed, so Chess.com answers with
a quick `304`:

```text
$ uv run chesscom-fetch fetch hikaru --months 2 --time-class blitz --time-class bullet
Synced hikaru · Oct–Nov 2026 · blitz, bullet

No new games.

Months  1 unchanged · 1 already complete
```

If any games are skipped (variants, unreadable PGNs, unknown result codes), a
`Skipped` line lists how many of each.

### Score by colour

Score counts a win as 1 point and a draw as ½, as a percentage of the games played
with that colour. Scores of 55% or more show in green and 45% or less in red.

```text
$ uv run chesscom-fetch score hikaru
Record for hikaru · 927 games

            White               Black
wins          380  82.4%          355  76.2%
draws          32   6.9%           37   7.9%
losses         49  10.6%           74  15.9%

score   396 / 461  85.9%  373.5 / 466  80.2%
```

### Top openings

The five opening families played most often with each colour, with the number of
games and the score in each. Ties are listed alphabetically.

```text
$ uv run chesscom-fetch top-openings hikaru
Top openings for hikaru · 927 games

As White                games  score
  English Opening          76  86.2%
  Sicilian Defense         56  84.8%
  Bishops Opening          44  95.5%
  Caro Kann Defense        43  82.6%
  French Defense           32  92.2%

As Black                games  score
  Sicilian Defense         66  84.8%
  Modern Defense           40  83.8%
  Scandinavian Defense     34  77.9%
  Queens Gambit            30  73.3%
  English Opening          24  91.7%
```

### Rating history

The player's own rating, averaged over the rated games they finished each month,
with one column per time class. Unrated games are left out, and so are time
classes the player never played rated. A month with no games in a time class
shows `—`.

```text
$ uv run chesscom-fetch ratings hikaru
Rating history for hikaru · 927 rated games

          blitz         bullet
            avg  games     avg  games
Oct 2026   3472    240    3398    343
Nov 2026   3455    208    3421    136
```

## What gets stored

Everything lives in one SQLite file with two tables.

**`games`**: one row per game, from the fetched player's side.

| Column | What it holds |
| ------ | ------------- |
| `url` | The game's Chess.com URL, used as its id |
| `username` | The player the row is seen from, lowercased |
| `end_date` | The date the game ended (UTC, `YYYY-MM-DD`) |
| `time_class` | `bullet`, `blitz`, `rapid` or `daily` |
| `rated` | Whether the game was rated |
| `colour` | The player's colour: `white` or `black` |
| `result` | The player's result: `win`, `draw` or `loss` |
| `white_rating`, `black_rating` | Both players' ratings when the game was played |
| `move_count` | The number of full moves played |
| `pgn` | The full PGN as Chess.com sent it |
| `fetch_date` | The date the game was fetched (UTC, `YYYY-MM-DD`) |
| `eco` | The ECO code from the PGN's `ECO` tag, if present |
| `eco_url` | The Chess.com opening page from the PGN's `ECOUrl` tag, if present |
| `opening_family` | The opening family named from `eco_url`, or `Unknown` if there isn't one |

**`archive_states`**: one row per archive month the tool has downloaded.

| Column | What it holds |
| ------ | ------------- |
| `url` | The archive month's URL |
| `etag` | The `ETag` Chess.com sent with that month, sent back as `If-None-Match` next time |
| `complete` | Whether the month has ended, so it can't gain new games |

### How results are mapped

Chess.com gives each side a result code. They map to:

- **win**: `win`
- **loss**: `checkmated`, `resigned`, `timeout`, `abandoned`, `lose`, plus the
  variant-only codes `kingofthehill`, `threecheck` and `bughousepartnerlose`
- **draw**: `agreed`, `repetition`, `stalemate`, `insufficient`, `50move`,
  `timevsinsufficient`

A game with any other code isn't stored. The summary lists that code and how often
it appeared, so a new code gets noticed instead of guessed.

### How opening families are named

Chess.com names a game's opening in the last part of its `ECOUrl`, such as
`Sicilian-Defense-Najdorf-Variation-6.Be3`. The family is the words up to and
including the first of `Opening`, `Defense`, `Game`, `Gambit`, `Attack` or
`System`, so that example becomes `Sicilian Defense`. If none of those words
appear, the family is the first two words. A game without an `ECOUrl` is stored
as `Unknown`.

The URL has no punctuation, so families read `Bishops Opening` and
`Caro Kann Defense` rather than `Bishop's Opening` and `Caro-Kann Defense`.

### What gets skipped

These games are skipped and counted in the summary, and the rest of the month is
still stored:

- variants such as Chess960 (only `rules: chess` is kept)
- games whose PGN can't be read
- games with a result code that isn't in the list above
- games in which the requested player is neither side

## How it treats Chess.com's API

- Sends requests one at a time, never in parallel
- Waits and retries once after a `429 Too Many Requests`, using `Retry-After`
  when it's a sensible number of seconds (up to 30) and 5 seconds otherwise
- Sends a User-Agent with the app's name and a contact email, as Chess.com asks
- Reuses each month's `ETag`, so unchanged archives aren't downloaded again
- Checks every response with Pydantic before anything is written to the database
- Only follows archive URLs on `api.chess.com`

Chess.com refreshes archives every 12 to 24 hours, so a game you just played may
not show up yet.

## Error handling

A network error, timeout, unknown username, unexpected response or unreadable
database file prints a one-line message and exits with code 1, never a traceback.
Invalid options, such as `--months 0` or a username with characters Chess.com
doesn't allow, exit with code 2.

```text
$ uv run chesscom-fetch fetch nosuchplayer-zq9x7
ERROR: [404] Player 'nosuchplayer-zq9x7' not found on Chess.com. Check the spelling.
$ echo $?
1
```

## Development

```bash
uv run pytest          # tests (none of them call Chess.com)
uv run ruff check .    # lint
uv run ruff format .   # format
uv run mypy .          # type check (strict)
```

The tests swap in a fake HTTP transport, so they run offline. Saved API data lives
in `tests/`: `archive_month.json` is a saved monthly archive response, including a
Chess960 game, and `fake_game.json` is a single game. Report tests build their
rows with the `build_fake_game_row` fixture in `tests/conftest.py` instead of
fetching anything.

Docstrings use Google style: full `Args`/`Returns`/`Raises` sections for public
functions, one line for private helpers. The full rule is in `pyproject.toml` next
to the pydoclint settings.

## Design decisions

**The database prevents duplicates.** The primary key on `games` is
`(url, username)`, and inserts use `ON CONFLICT DO NOTHING`. Duplicates are
refused by the database, not by checking first, so a re-run, a crash halfway
through or a repeated month can't create a second copy. The key includes the
username because a row is one player's view of a game: if you fetch both yourself
and an opponent, the game you played together is stored once for each of you,
with a different colour and result.

**Archive state lives next to the games.** Each month's `ETag` and `complete` flag
are kept in `archive_states` in the same database. A month's games and its state
are written in one transaction, so a month is never marked as fetched without its
games. A month counts as complete from the 2nd of the following month. That
leaves a day for Chess.com's archive refresh to pick up games finished late on
the last day of the month.

**Two kinds of model, one conversion point.** `ArchiveList`, `Archive`,
`ArchiveMonth`, `Game` and `Player` mirror Chess.com's JSON, and declare only the
fields this tool reads, so a change to a field it ignores can't break a sync.
`GameRow` mirrors the `games` table. `game_to_game_row` in `converter.py` is the
only place one becomes the other, and that's where variants, unreadable PGNs and
unknown result codes are turned away.

**One way to send a request.** Every request goes through `ChessClient` in
`client.py`. It sets the User-Agent, handles the single `429` retry and turns
network failures into the tool's own errors. The sync loop asks for one month at a
time and waits for each answer, so requests can't overlap.

**Opening families are worked out once, when a game is stored.** The family is
saved in its own column instead of being parsed from the URL each time a report
runs. The reports can then group by it in plain SQL, and the naming rule lives in
one function in `converter.py`.

**Reports read, they don't fetch.** `score`, `top-openings` and `ratings` only
query the database, so they run instantly, work offline and never touch
Chess.com's rate limits. Fetching stays a separate, deliberate step.

**Queries return data, rendering is separate.** `reports.py` returns plain
dataclasses (`Record`, `OpeningRecord`, `MonthlyRating`) and `render.py` decides
how they look. The SQL can be tested without the terminal, and the coach can reuse
the same queries later.

## Out of scope

- Lichess or other sites
- Fetching many players at once
- Filtering reports by date range or time class
- Game analysis (that comes later, in the coach)

## License

[MIT](LICENSE)
