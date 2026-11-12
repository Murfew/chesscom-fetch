from chesscom_fetch.models import ArchiveMonth
from tests.helpers import TEST_USERNAME_WHITE


def test_parses_saved_archive_month(archive_month_json: str) -> None:
    model = ArchiveMonth.model_validate_json(archive_month_json)

    assert len(model.games) == 3
    assert model.games[0].rules == "chess960"
    assert model.games[0].white.username == TEST_USERNAME_WHITE
