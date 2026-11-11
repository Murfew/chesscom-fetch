from pathlib import Path
from sqlite3 import IntegrityError
from typing import ClassVar, NoReturn

import pytest

from chesscom_fetch.db import (
    ArchiveStateRow,
    add_archive_state,
    add_games,
    get_archive_state,
    get_connection,
    init_db,
)
from chesscom_fetch.models import Colour, GameRow, Result, TimeClass
from tests.helpers import (
    TEST_ARCHIVE_MONTH_URLS,
    TEST_ETAG,
    TEST_USERNAME_BLACK,
    count_games_table_rows,
)

VALID_ENUM_FIELD_VALUES = (
    [pytest.param("result", result, id=f"result-{result}") for result in list(Result)]
    + [
        pytest.param("time_class", time_class, id=f"time_class-{time_class}")
        for time_class in list(TimeClass)
    ]
    + [pytest.param("colour", colour, id=f"colour-{colour}") for colour in list(Colour)]
)


class DummyError(Exception):
    pass


class TestAddGames:
    def test_returns_number_of_new_games(
        self, fake_game_row: GameRow, temp_db: Path
    ) -> None:
        with get_connection(temp_db) as conn:
            assert add_games(conn, [fake_game_row]) == 1

        assert count_games_table_rows(temp_db) == 1

    def test_skips_games_already_stored(
        self, fake_game_row: GameRow, temp_db: Path
    ) -> None:
        with get_connection(temp_db) as conn:
            assert add_games(conn, [fake_game_row]) == 1
            assert add_games(conn, [fake_game_row]) == 0

        assert count_games_table_rows(temp_db) == 1

    def test_stores_same_game_for_each_player(
        self, fake_game_row: GameRow, temp_db: Path
    ) -> None:
        with get_connection(temp_db) as conn:
            assert add_games(conn, [fake_game_row]) == 1

            fake_game_row_black_player = fake_game_row.model_copy(
                update={"username": TEST_USERNAME_BLACK}
            )
            assert add_games(conn, [fake_game_row_black_player]) == 1

        assert count_games_table_rows(temp_db) == 2


class TestAddArchiveState:
    ARCHIVE_STATE: ClassVar[ArchiveStateRow] = ArchiveStateRow(
        TEST_ARCHIVE_MONTH_URLS[0], TEST_ETAG, False
    )

    def test_inserts_new_state(self, temp_db: Path) -> None:
        with get_connection(temp_db) as conn:
            add_archive_state(conn, self.ARCHIVE_STATE)

            saved_state = get_archive_state(conn, self.ARCHIVE_STATE.url)
            assert saved_state == self.ARCHIVE_STATE
            assert type(saved_state.complete) is bool

    def test_updates_existing_state(self, temp_db: Path) -> None:
        with get_connection(temp_db) as conn:
            add_archive_state(conn, self.ARCHIVE_STATE)

            new_state = ArchiveStateRow(TEST_ARCHIVE_MONTH_URLS[0], '"new-etag"', True)
            add_archive_state(conn, new_state)

            saved_state = get_archive_state(conn, new_state.url)
            assert saved_state == new_state


class TestGetConnection:
    def _add_fake_game_row_and_raise_exception(
        self, db_path: Path, row: GameRow
    ) -> NoReturn:
        with get_connection(db_path) as conn:
            add_games(conn, [row])
            raise DummyError("TEST EXCEPTION")

    def test_rolls_back_on_error(self, temp_db: Path, fake_game_row: GameRow) -> None:
        with pytest.raises(DummyError):
            self._add_fake_game_row_and_raise_exception(temp_db, fake_game_row)

        assert count_games_table_rows(temp_db) == 0


class TestInitDb:
    def test_can_run_twice(self, temp_db: Path, fake_game_row: GameRow) -> None:
        with get_connection(temp_db) as conn:
            add_games(conn, [fake_game_row])

        assert count_games_table_rows(temp_db) == 1
        init_db(temp_db)
        assert count_games_table_rows(temp_db) == 1

    @pytest.mark.parametrize(("field", "value"), VALID_ENUM_FIELD_VALUES)
    def test_check_accepts_every_enum_value(
        self,
        temp_db: Path,
        fake_game_row: GameRow,
        field: str,
        value: Result | TimeClass | Colour,
    ) -> None:
        updated_game_row = fake_game_row.model_copy(update={field: value})

        with get_connection(temp_db) as conn:
            assert add_games(conn, [updated_game_row]) == 1

        assert count_games_table_rows(temp_db) == 1

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            pytest.param("result", "resigned", id="invalid-result"),
            pytest.param("time_class", "classical", id="invalid-time class"),
            pytest.param("colour", "blue", id="invalid-color"),
        ],
    )
    @pytest.mark.filterwarnings("ignore:Pydantic serializer")
    def test_check_rejects_unknown_value(
        self, temp_db: Path, fake_game_row: GameRow, field: str, value: str
    ) -> None:
        updated_game_row = fake_game_row.model_copy(update={field: value})

        with pytest.raises(IntegrityError), get_connection(temp_db) as conn:
            add_games(conn, [updated_game_row])

        assert count_games_table_rows(temp_db) == 0
