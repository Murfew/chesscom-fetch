from pathlib import Path

import pytest
from httpx2 import ConnectError, ConnectTimeout, Response, codes
from pydantic import HttpUrl
from typer.testing import CliRunner

from chesscom_fetch.cli import app
from chesscom_fetch.models import Game, TimeClass
from tests.helpers import (
    ARCHIVE_LIST_URL,
    TEST_USERNAME_WHITE,
    GetFetchResult,
    build_archive_list_response,
    build_archive_month_response,
    build_archive_url,
    count_games_table_rows,
)


@pytest.mark.usefixtures("patch_get_today")
class TestFetch:
    NOVEMBER_URL = build_archive_url(2026, 11)

    def test_prints_summary(
        self, fake_game: Game, get_fetch_result: GetFetchResult
    ) -> None:
        response_by_url = {
            ARCHIVE_LIST_URL: build_archive_list_response([self.NOVEMBER_URL]),
            self.NOVEMBER_URL: build_archive_month_response([fake_game]),
        }

        result = get_fetch_result(response_by_url)

        assert result.exit_code == 0
        assert f"Synced {TEST_USERNAME_WHITE}" in result.stdout
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
        self, response: Response, get_fetch_result: GetFetchResult
    ) -> None:
        result = get_fetch_result({ARCHIVE_LIST_URL: response})
        assert result.exit_code == 1
        assert "Traceback" not in result.stderr
        assert len(result.stderr.splitlines()) == 1

    def test_filters_report_by_time_class(
        self, fake_game: Game, get_fetch_result: GetFetchResult, temp_db: Path
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

        result = get_fetch_result(response_by_url, ["--time-class", TimeClass.RAPID])
        assert TimeClass.RAPID in result.stdout
        assert TimeClass.BLITZ not in result.stdout
        assert count_games_table_rows(temp_db) == 2

    @pytest.mark.parametrize(
        ("arguments", "expected_message"),
        [
            pytest.param(
                [TEST_USERNAME_WHITE, "--months", "0"],
                "Invalid value for '--months'",
                id="months-below-one",
            ),
            pytest.param(
                [TEST_USERNAME_WHITE, "--time-class", "unknown"],
                "Invalid value for '--time-class'",
                id="unknown-time-class",
            ),
            pytest.param([], "Missing argument 'username'", id="missing-username"),
        ],
    )
    def test_rejects_invalid_arguments(
        self, arguments: list[str], expected_message: str, runner: CliRunner
    ) -> None:
        result = runner.invoke(app, ["fetch", *arguments])
        assert result.exit_code == 2
        assert expected_message in result.stderr
