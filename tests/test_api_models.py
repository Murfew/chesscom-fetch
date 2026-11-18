import pytest
from pydantic import ValidationError

from chesscom_fetch.api_models import Archive, ArchiveMonth
from tests.helpers import USERNAME_ONE


def test_parses_saved_archive_month(archive_month_json: str) -> None:
    model = ArchiveMonth.model_validate_json(archive_month_json)

    assert len(model.games) == 3
    assert model.games[0].rules == "chess960"
    assert model.games[0].white.username == USERNAME_ONE


def test_rejects_when_url_has_bad_host() -> None:
    with pytest.raises(ValidationError, match=r"api.chess.com host"):
        Archive.model_validate(
            {
                "url": f"https://api.not-chess.com/pub/player/{USERNAME_ONE}/games/2026/01",
                "year": 2004,
                "month": 10,
            }
        )
