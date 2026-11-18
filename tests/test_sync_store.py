from pathlib import Path
from typing import ClassVar

from chesscom_fetch.database import get_connection
from chesscom_fetch.sync_store import (
    ArchiveStateRow,
    add_games,
    get_archive_state,
    upsert_archive_state,
)
from tests.helpers import (
    ARCHIVE_MONTH_URLS,
    ETAG,
    USERNAME_TWO,
    BuildFakeGameRow,
    count_games_table_rows,
)


class TestAddGames:
    def test_returns_number_of_new_games(
        self, build_fake_game_row: BuildFakeGameRow, temp_db: Path
    ) -> None:
        with get_connection(temp_db) as conn:
            assert add_games(conn, [build_fake_game_row()]) == 1

        assert count_games_table_rows(temp_db) == 1

    def test_skips_games_already_stored(
        self, build_fake_game_row: BuildFakeGameRow, temp_db: Path
    ) -> None:
        with get_connection(temp_db) as conn:
            game_row = build_fake_game_row()
            assert add_games(conn, [game_row]) == 1
            assert add_games(conn, [game_row]) == 0

        assert count_games_table_rows(temp_db) == 1

    def test_stores_same_game_for_each_player(
        self, build_fake_game_row: BuildFakeGameRow, temp_db: Path
    ) -> None:
        with get_connection(temp_db) as conn:
            assert add_games(conn, [build_fake_game_row()]) == 1
            assert add_games(conn, [build_fake_game_row(username=USERNAME_TWO)]) == 1

        assert count_games_table_rows(temp_db) == 2


class TestUpsertArchiveState:
    ARCHIVE_STATE: ClassVar[ArchiveStateRow] = ArchiveStateRow(
        ARCHIVE_MONTH_URLS[0], ETAG, False
    )

    def test_inserts_new_state(self, temp_db: Path) -> None:
        with get_connection(temp_db) as conn:
            upsert_archive_state(conn, self.ARCHIVE_STATE)

            saved_state = get_archive_state(conn, self.ARCHIVE_STATE.url)
            assert saved_state == self.ARCHIVE_STATE
            assert type(saved_state.complete) is bool

    def test_updates_existing_state(self, temp_db: Path) -> None:
        with get_connection(temp_db) as conn:
            upsert_archive_state(conn, self.ARCHIVE_STATE)

            new_state = ArchiveStateRow(ARCHIVE_MONTH_URLS[0], '"new-etag"', True)
            upsert_archive_state(conn, new_state)

            saved_state = get_archive_state(conn, new_state.url)
            assert saved_state == new_state
