from pathlib import Path

import pytest
from httpx2 import ConnectError, ConnectTimeout, Response, codes
from pydantic import HttpUrl
from typer.testing import CliRunner

from chesscom_fetch.api_models import Game
from chesscom_fetch.cli import app
from chesscom_fetch.database import get_connection
from chesscom_fetch.domain import Colour, Result, TimeClass
from chesscom_fetch.sync_store import add_games
from tests.helpers import (
    ARCHIVE_LIST_URL,
    CARO_KANN_DEFENSE,
    FRENCH_DEFENSE,
    LONDON_SYSTEM,
    SCANDINAVIAN_DEFENSE,
    SICILIAN_DEFENSE,
    USERNAME_ONE,
    VIENNA_GAMBIT,
    BuildFakeGameRow,
    RunFetch,
    build_archive_list_response,
    build_archive_month_response,
    build_archive_url,
    count_games_table_rows,
)


@pytest.mark.usefixtures("patch_today_utc")
class TestFetch:
    NOVEMBER_URL = build_archive_url(2026, 11)

    def test_prints_summary(self, fake_game: Game, run_fetch: RunFetch) -> None:
        response_by_url = {
            ARCHIVE_LIST_URL: build_archive_list_response([self.NOVEMBER_URL]),
            self.NOVEMBER_URL: build_archive_month_response([fake_game]),
        }

        result = run_fetch(response_by_url)

        assert result.exit_code == 0
        assert f"Synced {USERNAME_ONE}" in result.stdout
        assert ["rapid", "1"] in [
            line.strip().split() for line in result.stdout.splitlines()
        ]
        assert "Skipped" not in result.stdout
        assert "Months" not in result.stdout

    @pytest.mark.parametrize(
        ("response"),
        [
            pytest.param(Response(codes.NOT_FOUND), id="not-found"),
            pytest.param(
                Response(codes.OK, text="not a json response"), id="non-json-body"
            ),
            pytest.param(
                Response(codes.OK, json={"wrong-key": "some-value"}),
                id="wrong-json-shape",
            ),
            pytest.param(ConnectTimeout("Timed out."), id="timeout"),
            pytest.param(ConnectError("Connection error."), id="network-error"),
        ],
    )
    def test_prints_one_line_on_fetch_error(
        self, response: Response, run_fetch: RunFetch
    ) -> None:
        result = run_fetch({ARCHIVE_LIST_URL: response})
        assert result.exit_code == 1
        assert "Traceback" not in result.stderr
        assert len(result.stderr.splitlines()) == 1

    def test_filters_summary_by_time_class(
        self, fake_game: Game, run_fetch: RunFetch, temp_db: Path
    ) -> None:
        fake_blitz_game = fake_game.model_copy(
            update={
                "url": HttpUrl("https://www.chess.com/game/live/234567890123"),
                "time_class": TimeClass.BLITZ,
            }
        )

        response_by_url = {
            ARCHIVE_LIST_URL: build_archive_list_response([self.NOVEMBER_URL]),
            self.NOVEMBER_URL: build_archive_month_response(
                [fake_game, fake_blitz_game]
            ),
        }

        result = run_fetch(response_by_url, ["--time-class", TimeClass.RAPID])
        assert TimeClass.RAPID in result.stdout
        assert TimeClass.BLITZ not in result.stdout
        assert count_games_table_rows(temp_db) == 2

    @pytest.mark.parametrize(
        ("arguments", "expected_message"),
        [
            pytest.param(
                [USERNAME_ONE, "--months", "0"],
                "Invalid value for '--months'",
                id="months-below-one",
            ),
            pytest.param(
                [USERNAME_ONE, "--time-class", "unknown"],
                "Invalid value for '--time-class'",
                id="unknown-time-class",
            ),
            pytest.param([], "Missing argument 'username'", id="missing-username"),
            pytest.param(
                ["asdasd/asdad/"],
                "Value can only be composed of letters, digits, '_' and '-'.",
                id="bad-username",
            ),
        ],
    )
    def test_rejects_invalid_arguments(
        self, arguments: list[str], expected_message: str, runner: CliRunner
    ) -> None:
        result = runner.invoke(app, ["fetch", *arguments])
        assert result.exit_code == 2
        assert expected_message in result.stderr


class TestScore:
    def test_prints_record_by_colour(
        self, build_fake_game_row: BuildFakeGameRow, temp_db: Path, runner: CliRunner
    ) -> None:
        with get_connection(temp_db) as conn:
            add_games(
                conn,
                [
                    build_fake_game_row(result=Result.WIN, colour=Colour.WHITE),
                    build_fake_game_row(result=Result.WIN, colour=Colour.WHITE),
                    build_fake_game_row(result=Result.DRAW, colour=Colour.WHITE),
                    build_fake_game_row(result=Result.LOSS, colour=Colour.WHITE),
                    build_fake_game_row(result=Result.WIN, colour=Colour.BLACK),
                    build_fake_game_row(result=Result.DRAW, colour=Colour.BLACK),
                    build_fake_game_row(result=Result.DRAW, colour=Colour.BLACK),
                    build_fake_game_row(result=Result.LOSS, colour=Colour.BLACK),
                ],
            )

        result = runner.invoke(app, ["score", USERNAME_ONE])

        assert result.exit_code == 0
        assert f"{USERNAME_ONE} · 8 games" in result.stdout

        rows = [line.strip().split() for line in result.stdout.splitlines()]

        assert ["wins", "2", "50.0%", "1", "25.0%"] in rows
        assert ["draws", "1", "25.0%", "2", "50.0%"] in rows
        assert ["losses", "1", "25.0%", "1", "25.0%"] in rows
        assert ["score", "2.5", "/", "4", "62.5%", "2", "/", "4", "50.0%"] in rows

    def test_prints_dash_for_colour_without_games(
        self, temp_db: Path, build_fake_game_row: BuildFakeGameRow, runner: CliRunner
    ) -> None:
        with get_connection(temp_db) as conn:
            add_games(
                conn,
                [
                    build_fake_game_row(result=Result.WIN),
                    build_fake_game_row(result=Result.DRAW),
                    build_fake_game_row(result=Result.LOSS),
                ],
            )

        result = runner.invoke(app, ["score", USERNAME_ONE])
        assert result.exit_code == 0

        rows = [line.strip().split() for line in result.stdout.splitlines()]

        assert ["wins", "1", "33.3%", "—"] in rows
        assert ["draws", "1", "33.3%", "—"] in rows
        assert ["losses", "1", "33.3%", "—"] in rows
        assert ["score", "1.5", "/", "3", "50.0%", "—"] in rows

    def test_prints_message_when_no_games(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["score", USERNAME_ONE])

        assert result.exit_code == 0
        assert f"No games saved for {USERNAME_ONE}" in result.stdout


class TestTopOpenings:
    def test_prints_openings_by_colour(
        self, temp_db: Path, build_fake_game_row: BuildFakeGameRow, runner: CliRunner
    ) -> None:
        with get_connection(temp_db) as conn:
            add_games(
                conn,
                [
                    build_fake_game_row(
                        colour=Colour.BLACK,
                        opening_family=CARO_KANN_DEFENSE,
                        result=Result.WIN,
                    ),
                    build_fake_game_row(
                        colour=Colour.BLACK,
                        opening_family=SCANDINAVIAN_DEFENSE,
                        result=Result.DRAW,
                    ),
                    build_fake_game_row(
                        colour=Colour.BLACK,
                        opening_family=SICILIAN_DEFENSE,
                        result=Result.LOSS,
                    ),
                    build_fake_game_row(
                        colour=Colour.BLACK,
                        opening_family=VIENNA_GAMBIT,
                        result=Result.WIN,
                    ),
                    build_fake_game_row(
                        colour=Colour.BLACK,
                        opening_family=LONDON_SYSTEM,
                        result=Result.WIN,
                    ),
                    build_fake_game_row(
                        colour=Colour.BLACK,
                        opening_family=FRENCH_DEFENSE,
                        result=Result.WIN,
                    ),
                    build_fake_game_row(
                        colour=Colour.WHITE,
                        opening_family=LONDON_SYSTEM,
                        result=Result.LOSS,
                    ),
                ],
            )

        result = runner.invoke(app, ["top-openings", USERNAME_ONE])

        assert result.exit_code == 0
        assert f"{USERNAME_ONE} · 7 games" in result.stdout

        rows = [line.strip().split() for line in result.stdout.splitlines()]

        assert ["As", "White", "games", "score"] in rows
        assert ["As", "Black", "games", "score"] in rows
        assert [*CARO_KANN_DEFENSE.split(" "), "1", "100.0%"] in rows
        assert [*SCANDINAVIAN_DEFENSE.split(" "), "1", "50.0%"] in rows
        assert [*SICILIAN_DEFENSE.split(" "), "1", "0.0%"] in rows
        assert VIENNA_GAMBIT not in result.stdout
        assert [*LONDON_SYSTEM.split(" "), "1", "100.0%"] in rows
        assert [*FRENCH_DEFENSE.split(" "), "1", "100.0%"] in rows
        assert [*LONDON_SYSTEM.split(" "), "1", "0.0%"] in rows

    def test_prints_no_games_row_for_missing_colour(
        self, temp_db: Path, build_fake_game_row: BuildFakeGameRow, runner: CliRunner
    ) -> None:
        with get_connection(temp_db) as conn:
            add_games(conn, [build_fake_game_row()])

        result = runner.invoke(app, ["top-openings", USERNAME_ONE])
        assert result.exit_code == 0
        assert "No games as Black." in result.stdout

    def test_prints_message_when_no_games(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["top-openings", USERNAME_ONE])

        assert result.exit_code == 0
        assert f"No games saved for {USERNAME_ONE}" in result.stdout


class TestRatings:
    def test_prints_rating_history(
        self, runner: CliRunner, temp_db: Path, build_fake_game_row: BuildFakeGameRow
    ) -> None:
        with get_connection(temp_db) as conn:
            add_games(
                conn,
                [
                    build_fake_game_row(
                        time_class=TimeClass.BLITZ,
                        end_date="2026-09-01",
                        white_rating=1000,
                    ),
                    build_fake_game_row(
                        time_class=TimeClass.BLITZ,
                        end_date="2026-09-01",
                        white_rating=1001,
                    ),
                    build_fake_game_row(
                        time_class=TimeClass.BLITZ,
                        end_date="2026-09-01",
                        white_rating=1001,
                    ),
                    build_fake_game_row(
                        time_class=TimeClass.RAPID,
                        end_date="2026-11-01",
                        white_rating=1200,
                    ),
                    build_fake_game_row(
                        time_class=TimeClass.RAPID,
                        end_date="2026-11-01",
                        white_rating=3000,
                        rated=False,
                    ),
                ],
            )

        result = runner.invoke(app, ["ratings", USERNAME_ONE])

        assert result.exit_code == 0
        assert f"{USERNAME_ONE} · 4 rated games" in result.stdout

        rows = [line.strip().split() for line in result.stdout.splitlines()]
        september_row = ["Sep", "2026", "—", "1001", "3"]
        november_row = ["Nov", "2026", "1200", "1", "—"]

        assert ["rapid", "blitz"] in rows
        assert september_row in rows
        assert november_row in rows
        assert rows.index(september_row) < rows.index(november_row)

    def test_prints_message_when_no_rated_games(
        self, runner: CliRunner, temp_db: Path, build_fake_game_row: BuildFakeGameRow
    ) -> None:
        with get_connection(temp_db) as conn:
            add_games(conn, [build_fake_game_row(rated=False)])

        result = runner.invoke(app, ["ratings", USERNAME_ONE])

        assert result.exit_code == 0
        assert f"No rated games saved for {USERNAME_ONE}" in result.stdout

    def test_prints_message_when_no_games(self, runner: CliRunner) -> None:
        result = runner.invoke(app, ["ratings", USERNAME_ONE])

        assert result.exit_code == 0
        assert f"No games saved for {USERNAME_ONE}" in result.stdout
