import json
from datetime import date
from pathlib import Path

import pytest
from httpx2 import Request, Response, codes
from pydantic import HttpUrl

from chesscom_fetch.db import (
    ArchiveStateRow,
    add_archive_state,
    get_archive_state,
    get_connection,
)
from chesscom_fetch.http import ChessClient
from chesscom_fetch.models import Archive, Game, TimeClass
from chesscom_fetch.sync import (
    SyncSummary,
    _is_archive_in_window,
    _is_month_complete,
    sync,
)
from tests.helpers import (
    ARCHIVE_LIST_URL,
    TEST_ETAG,
    TEST_USERNAME_WHITE,
    UNKNOWN_API_RESULT_CODE,
    MakeChessClient,
    ResponseByUrl,
    build_archive_list_response,
    build_archive_month_response,
    build_archive_url,
    build_handler,
    count_games_table_rows,
)


class TestIsMonthComplete:
    @pytest.mark.parametrize(
        ("year", "month", "today", "expected"),
        [
            pytest.param(
                2026,
                3,
                date(2026, 3, 15),
                False,
                id="during-month",
            ),
            pytest.param(
                2026,
                3,
                date(2026, 4, 1),
                False,
                id="just-before-boundary",
            ),
            pytest.param(
                2026,
                3,
                date(2026, 4, 2),
                True,
                id="exactly-at-boundary",
            ),
            pytest.param(
                2026,
                12,
                date(2027, 1, 2),
                True,
                id="december-rolls-into-next-year",
            ),
            pytest.param(
                2028,
                2,
                date(2028, 3, 1),
                False,
                id="february-leap-year",
            ),
            pytest.param(
                2026,
                12,
                date(2026, 12, 15),
                False,
                id="december-before-boundary",
            ),
            pytest.param(
                2026,
                11,
                date(2026, 12, 2),
                True,
                id="november-stays-in-same-year",
            ),
        ],
    )
    def test_returns_correct_value(
        self, year: int, month: int, today: date, expected: bool
    ) -> None:
        assert (
            _is_month_complete(
                Archive(url=build_archive_url(year, month), year=year, month=month),
                today,
            )
            == expected
        )


class TestIsArchiveInWindow:
    TODAY = date(2027, 2, 10)

    @pytest.mark.parametrize(
        ("months", "year", "month", "expected"),
        [
            pytest.param(
                1,
                2027,
                2,
                True,
                id="current-month",
            ),
            pytest.param(
                1,
                2027,
                1,
                False,
                id="previous-month-excluded-when-one",
            ),
            pytest.param(
                3,
                2026,
                12,
                True,
                id="earliest-month-in-window",
            ),
            pytest.param(
                3,
                2026,
                11,
                False,
                id="just-outside-window",
            ),
            pytest.param(
                14,
                2026,
                1,
                True,
                id="window-spans-year-boundary",
            ),
        ],
    )
    def test_returns_correct_value(
        self, months: int, year: int, month: int, expected: bool
    ) -> None:
        assert (
            _is_archive_in_window(
                months,
                Archive(url=build_archive_url(year, month), year=year, month=month),
                self.TODAY,
            )
            == expected
        )


class TestSync:
    SEPTEMBER_URL = build_archive_url(2026, 9)
    OCTOBER_URL = build_archive_url(2026, 10)
    NOVEMBER_URL = build_archive_url(2026, 11)
    TODAY = date(2026, 11, 10)

    def make_client(
        self,
        make_chess_client: MakeChessClient,
        response_by_url: ResponseByUrl,
    ) -> tuple[ChessClient, list[str]]:
        requests: list[str] = []
        handler = build_handler(response_by_url, requests)
        client = make_chess_client(handler)

        return client, requests

    def run_sync(
        self, *, chess_client: ChessClient, db_path: Path, months: int
    ) -> SyncSummary:
        return sync(
            chess_client=chess_client,
            db_path=db_path,
            username=TEST_USERNAME_WHITE,
            months=months,
            today=self.TODAY,
        )

    def test_stores_games_from_months_in_window(
        self, fake_game: Game, make_chess_client: MakeChessClient, temp_db: Path
    ) -> None:
        response_by_url = {
            ARCHIVE_LIST_URL: build_archive_list_response(
                [self.SEPTEMBER_URL, self.OCTOBER_URL, self.NOVEMBER_URL]
            ),
            self.OCTOBER_URL: build_archive_month_response([fake_game]),
            self.NOVEMBER_URL: build_archive_month_response([]),
        }
        client, requests = self.make_client(make_chess_client, response_by_url)
        summary = self.run_sync(chess_client=client, db_path=temp_db, months=2)
        assert summary.new_games[TimeClass.RAPID] == 1
        assert count_games_table_rows(temp_db) == 1
        assert self.SEPTEMBER_URL not in requests

    def test_skips_complete_months_without_request(
        self, fake_game: Game, make_chess_client: MakeChessClient, temp_db: Path
    ) -> None:
        with get_connection(temp_db) as conn:
            add_archive_state(
                conn,
                ArchiveStateRow(url=self.NOVEMBER_URL, etag=TEST_ETAG, complete=True),
            )

        response_by_url = {
            ARCHIVE_LIST_URL: build_archive_list_response([self.NOVEMBER_URL]),
            self.NOVEMBER_URL: build_archive_month_response([fake_game]),
        }

        client, requests = self.make_client(make_chess_client, response_by_url)

        summary = self.run_sync(chess_client=client, db_path=temp_db, months=1)

        assert summary.months_completed == 1
        assert self.NOVEMBER_URL not in requests

    def test_sends_stored_etag_and_counts_unchanged_month(
        self, fake_game: Game, make_chess_client: MakeChessClient, temp_db: Path
    ) -> None:
        with get_connection(temp_db) as conn:
            add_archive_state(
                conn,
                ArchiveStateRow(url=self.NOVEMBER_URL, etag=TEST_ETAG, complete=False),
            )

        def handler(request: Request) -> Response:
            if request.url == ARCHIVE_LIST_URL:
                return build_archive_list_response([self.NOVEMBER_URL])

            etag = request.headers.get("if-none-match")
            if etag == TEST_ETAG:
                return Response(codes.NOT_MODIFIED)

            return build_archive_month_response([fake_game])

        client = make_chess_client(handler)

        summary = self.run_sync(chess_client=client, db_path=temp_db, months=1)

        assert sum(summary.new_games.values()) == 0
        assert summary.months_unchanged == 1

    def test_counts_skipped_games(
        self, fake_game: Game, make_chess_client: MakeChessClient, temp_db: Path
    ) -> None:
        fake_game_with_variant = fake_game.model_copy(
            update={
                "url": HttpUrl("https://www.chess.com/game/live/123456789013"),
                "rules": "chess960",
            }
        )
        player_with_unknown_result = fake_game.white.model_copy(
            update={"result": UNKNOWN_API_RESULT_CODE}
        )
        fake_game_with_unknown_result = fake_game.model_copy(
            update={
                "url": HttpUrl("https://www.chess.com/game/live/123456789014"),
                "white": player_with_unknown_result,
            }
        )

        response_by_url = {
            ARCHIVE_LIST_URL: build_archive_list_response([self.NOVEMBER_URL]),
            self.NOVEMBER_URL: build_archive_month_response(
                [fake_game, fake_game_with_variant, fake_game_with_unknown_result]
            ),
        }

        client, _ = self.make_client(make_chess_client, response_by_url)

        summary = self.run_sync(chess_client=client, db_path=temp_db, months=1)

        assert sum(summary.new_games.values()) == 1
        assert summary.game_variants == 1
        assert summary.unknown_result_codes[UNKNOWN_API_RESULT_CODE] == 1
        assert count_games_table_rows(temp_db) == 1

    def test_saves_new_etag_and_completeness(
        self, fake_game: Game, make_chess_client: MakeChessClient, temp_db: Path
    ) -> None:
        response_by_url = {
            ARCHIVE_LIST_URL: build_archive_list_response(
                [self.SEPTEMBER_URL, self.OCTOBER_URL, self.NOVEMBER_URL]
            ),
            self.OCTOBER_URL: build_archive_month_response([fake_game], TEST_ETAG),
            self.NOVEMBER_URL: build_archive_month_response([]),
        }

        client, _ = self.make_client(make_chess_client, response_by_url)

        self.run_sync(chess_client=client, db_path=temp_db, months=2)

        with get_connection(temp_db) as conn:
            october_state = get_archive_state(conn, self.OCTOBER_URL)
            november_state = get_archive_state(conn, self.NOVEMBER_URL)

        assert october_state is not None
        assert october_state.etag == TEST_ETAG
        assert october_state.complete

        assert november_state is not None
        assert november_state.etag is None
        assert not november_state.complete

    def test_second_run_stores_no_duplicates(
        self, fake_game: Game, make_chess_client: MakeChessClient, temp_db: Path
    ) -> None:
        response_by_url = {
            ARCHIVE_LIST_URL: build_archive_list_response(
                [self.SEPTEMBER_URL, self.OCTOBER_URL, self.NOVEMBER_URL]
            ),
            self.OCTOBER_URL: build_archive_month_response([]),
            self.NOVEMBER_URL: build_archive_month_response([fake_game]),
        }

        client, requests = self.make_client(make_chess_client, response_by_url)

        first_run_summary = self.run_sync(
            chess_client=client, db_path=temp_db, months=1
        )
        second_run_summary = self.run_sync(
            chess_client=client, db_path=temp_db, months=1
        )

        assert requests.count(self.NOVEMBER_URL) == 2
        assert sum(first_run_summary.new_games.values()) == 1
        assert sum(second_run_summary.new_games.values()) == 0

    def test_skips_variants_in_saved_archive(
        self, archive_month_json: str, make_chess_client: MakeChessClient, temp_db: Path
    ) -> None:
        response_by_url = {
            ARCHIVE_LIST_URL: build_archive_list_response([self.NOVEMBER_URL]),
            self.NOVEMBER_URL: Response(
                codes.OK,
                json=json.loads(archive_month_json),
            ),
        }

        client, _ = self.make_client(make_chess_client, response_by_url)

        summary = self.run_sync(chess_client=client, db_path=temp_db, months=2)

        assert summary.game_variants == 1
        assert sum(summary.new_games.values()) == 2
