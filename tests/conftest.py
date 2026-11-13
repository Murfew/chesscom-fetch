from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from httpx2 import Client, MockTransport
from pytest_mock import MockFixture
from rich.console import Console
from typer.testing import CliRunner, Result

import chesscom_fetch.cli
from chesscom_fetch import db
from chesscom_fetch.cli import app
from chesscom_fetch.converter import game_to_game_row
from chesscom_fetch.http import ChessClient
from chesscom_fetch.models import Game, GameRow
from tests.helpers import (
    TEST_FETCH_DATE,
    TEST_USERNAME_WHITE,
    GetFetchResult,
    Handler,
    MakeChessClient,
    PatchGetChessClient,
    ResponseByUrl,
    build_handler,
)


@pytest.fixture(autouse=True)
def temp_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("APP_DB_PATH", str(db_path))
    db.init_db(db_path)
    return db_path


@pytest.fixture(autouse=True)
def setup_terminal(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COLUMNS", "1000")
    monkeypatch.setenv("TERMINAL_WIDTH", "1000")
    monkeypatch.setattr(
        chesscom_fetch.cli,
        "console",
        Console(force_terminal=False, color_system=None),
    )
    monkeypatch.setattr(
        chesscom_fetch.cli,
        "err_console",
        Console(stderr=True, force_terminal=False, color_system=None),
    )


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def archive_month_json() -> str:
    return (Path(__file__).resolve().parent / Path("./archive_month.json")).read_text(
        encoding="utf-8"
    )


@pytest.fixture
def patch_get_today(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(chesscom_fetch.cli, "_get_today", lambda: date(2026, 11, 1))


@pytest.fixture
def patch_get_chess_client(
    monkeypatch: pytest.MonkeyPatch,
    make_chess_client: MakeChessClient,
) -> PatchGetChessClient:
    def _patch_get_chess_client(response_by_url: ResponseByUrl) -> list[str]:
        requests_record: list[str] = []
        handler = build_handler(response_by_url, requests_record)

        def _get_chess_client(_http_client: Client, _username: str) -> ChessClient:
            return make_chess_client(handler)

        monkeypatch.setattr(chesscom_fetch.cli, "_get_chess_client", _get_chess_client)
        return requests_record

    return _patch_get_chess_client


@pytest.fixture
def fake_game() -> Game:
    json_str = (Path(__file__).resolve().parent / Path("./fake_game.json")).read_text(
        encoding="utf-8"
    )

    return Game.model_validate_json(json_str)


@pytest.fixture
def fake_game_row(fake_game: Game) -> GameRow:
    return game_to_game_row(TEST_USERNAME_WHITE, fake_game, TEST_FETCH_DATE)


@pytest.fixture
def make_chess_client(mocker: MockFixture) -> MakeChessClient:
    def _make_chess_client(
        handler: Handler, wait_mock: MagicMock | None = None
    ) -> ChessClient:
        return ChessClient(
            Client(transport=MockTransport(handler)),
            TEST_USERNAME_WHITE,
            wait_mock if wait_mock is not None else mocker.MagicMock(),
        )

    return _make_chess_client


@pytest.fixture
def get_fetch_result(
    patch_get_chess_client: PatchGetChessClient, runner: CliRunner
) -> GetFetchResult:
    def _get_fetch_result(
        response_by_url: ResponseByUrl, extra_args: list[str] | None = None
    ) -> Result:
        patch_get_chess_client(response_by_url)
        return runner.invoke(app, ["fetch", TEST_USERNAME_WHITE, *(extra_args or [])])

    return _get_fetch_result
