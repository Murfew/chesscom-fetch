from datetime import date
from itertools import count
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from httpx2 import Client, MockTransport
from pytest_mock import MockFixture
from rich.console import Console
from typer.testing import CliRunner
from typer.testing import Result as RunnerResult

import chesscom_fetch.cli
from chesscom_fetch.api_models import Game
from chesscom_fetch.cli import app
from chesscom_fetch.client import ChessClient
from chesscom_fetch.converter import game_to_game_row
from chesscom_fetch.database import GameRow, init_db
from chesscom_fetch.domain import Colour, Result, TimeClass
from tests.helpers import (
    CARO_KANN_DEFENSE,
    FETCH_DATE,
    USERNAME_ONE,
    BuildFakeGameRow,
    Handler,
    MakeChessClient,
    PatchMakeChessClient,
    ResponseByUrl,
    RunFetch,
    build_handler,
)

# autouse


@pytest.fixture(autouse=True)
def temp_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("APP_DB_PATH", str(db_path))
    init_db(db_path)
    return db_path


@pytest.fixture(autouse=True)
def plain_consoles(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COLUMNS", "1000")
    monkeypatch.setenv("TERMINAL_WIDTH", "1000")
    monkeypatch.setattr(
        chesscom_fetch.render,
        "console",
        Console(force_terminal=False, color_system=None),
    )
    monkeypatch.setattr(
        chesscom_fetch.cli,
        "err_console",
        Console(stderr=True, force_terminal=False, color_system=None),
    )


# Game Data


@pytest.fixture
def archive_month_json() -> str:
    return (Path(__file__).resolve().parent / Path("./archive_month.json")).read_text(
        encoding="utf-8"
    )


@pytest.fixture
def fake_game() -> Game:
    json_str = (Path(__file__).resolve().parent / Path("./fake_game.json")).read_text(
        encoding="utf-8"
    )

    return Game.model_validate_json(json_str)


@pytest.fixture
def build_fake_game_row() -> BuildFakeGameRow:
    """Return a builder for game rows that sets only the fields a test names.

    A bare row is a rated rapid game that `USERNAME_ONE` lost as White in the
    Caro-Kann on 2026-11-05, with White rated below Black. Each row gets a
    unique URL, so rows never collide on insert.
    """

    counter = count(1)

    def _build_fake_game_row(
        *,
        result: Result = Result.LOSS,
        username: str = USERNAME_ONE,
        opening_family: str = CARO_KANN_DEFENSE,
        colour: Colour = Colour.WHITE,
        end_date: str = "2026-11-05",
        time_class: TimeClass = TimeClass.RAPID,
        rated: bool = True,
        white_rating: int = 1000,
        black_rating: int = 1200,
    ) -> GameRow:
        return GameRow(
            url=f"https://www.chess.com/game/live/{next(counter)}",
            result=result,
            username=username,
            opening_family=opening_family,
            colour=colour,
            end_date=end_date,
            time_class=time_class,
            rated=rated,
            white_rating=white_rating,
            black_rating=black_rating,
            pgn="",
            move_count=0,
            fetch_date=FETCH_DATE.isoformat(),
        )

    return _build_fake_game_row


# HTTP


@pytest.fixture
def make_chess_client(mocker: MockFixture) -> MakeChessClient:
    def _make_chess_client(
        handler: Handler, wait_mock: MagicMock | None = None
    ) -> ChessClient:
        return ChessClient(
            Client(transport=MockTransport(handler)),
            USERNAME_ONE,
            wait_mock if wait_mock is not None else mocker.MagicMock(),
        )

    return _make_chess_client


@pytest.fixture
def patch_make_chess_client(
    monkeypatch: pytest.MonkeyPatch,
    make_chess_client: MakeChessClient,
) -> PatchMakeChessClient:
    def _patch_make_chess_client(response_by_url: ResponseByUrl) -> list[str]:
        requested_urls: list[str] = []
        handler = build_handler(response_by_url, requested_urls)

        def _make_chess_client(_http_client: Client, _username: str) -> ChessClient:
            return make_chess_client(handler)

        monkeypatch.setattr(
            chesscom_fetch.cli, "_make_chess_client", _make_chess_client
        )
        return requested_urls

    return _patch_make_chess_client


# CLI


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def patch_today_utc(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(chesscom_fetch.cli, "_today_utc", lambda: date(2026, 11, 1))


@pytest.fixture
def run_fetch(
    patch_make_chess_client: PatchMakeChessClient, runner: CliRunner
) -> RunFetch:
    def _run_fetch(
        response_by_url: ResponseByUrl, extra_args: list[str] | None = None
    ) -> RunnerResult:
        patch_make_chess_client(response_by_url)
        return runner.invoke(app, ["fetch", USERNAME_ONE, *(extra_args or [])])

    return _run_fetch
