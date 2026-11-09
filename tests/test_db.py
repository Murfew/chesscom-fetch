from pathlib import Path
from typing import ClassVar

import pytest

from chesscom_fetch import db
from chesscom_fetch.models import GameRow
from tests.helpers import (
    TEST_ARCHIVE_MONTH_URLS,
    TEST_ETAG,
    TEST_USERNAME_BLACK,
)


def _count_games_table_rows(db_path: Path) -> int:
    with db.get_connection(db_path) as conn:
        return int(conn.execute("SELECT COUNT(*) FROM games").fetchone()[0])


class TestAddGames:
    def test_returns_number_of_new_games(
        self, fake_game_row: GameRow, temp_db: Path
    ) -> None:
        with db.get_connection(temp_db) as conn:
            assert db.add_games(conn, [fake_game_row]) == 1

        assert _count_games_table_rows(temp_db) == 1

    def test_skips_games_already_stored(
        self, fake_game_row: GameRow, temp_db: Path
    ) -> None:
        with db.get_connection(temp_db) as conn:
            assert db.add_games(conn, [fake_game_row]) == 1
            assert db.add_games(conn, [fake_game_row]) == 0

        assert _count_games_table_rows(temp_db) == 1

    def test_stores_same_game_for_each_player(
        self, fake_game_row: GameRow, temp_db: Path
    ) -> None:
        with db.get_connection(temp_db) as conn:
            assert db.add_games(conn, [fake_game_row]) == 1

            fake_game_row_black_player = fake_game_row.model_copy(
                update={"username": TEST_USERNAME_BLACK}
            )
            assert db.add_games(conn, [fake_game_row_black_player]) == 1


class TestAddArchiveState:
    ARCHIVE_STATE: ClassVar[db.ArchiveStateRow] = db.ArchiveStateRow(
        TEST_ARCHIVE_MONTH_URLS[0], TEST_ETAG, False
    )

    def test_inserts_new_state(self, temp_db: Path) -> None:
        with db.get_connection(temp_db) as conn:
            db.add_archive_state(conn, self.ARCHIVE_STATE)

        saved_state = db.get_archive_states(temp_db)[0]
        assert saved_state == self.ARCHIVE_STATE
        assert type(saved_state.complete) is bool

    def test_updates_existing_state(self, temp_db: Path) -> None:
        with db.get_connection(temp_db) as conn:
            db.add_archive_state(conn, self.ARCHIVE_STATE)

            new_state = db.ArchiveStateRow(
                TEST_ARCHIVE_MONTH_URLS[0], '"new-etag"', True
            )
            db.add_archive_state(conn, new_state)

        saved_state = db.get_archive_states(temp_db)[0]
        assert saved_state == new_state


class TestGetConnection:
    @pytest.mark.skip("not written yet")
    def test_rolls_back_on_error(self) -> None: ...


class TestInitDb:
    @pytest.mark.skip("not written yet")
    def test_can_run_twice(self) -> None: ...
    @pytest.mark.skip("not written yet")
    def test_check_accepts_every_enum_value(self) -> None: ...
    @pytest.mark.skip("not written yet")
    def test_check_rejects_unknown_value(self) -> None: ...
