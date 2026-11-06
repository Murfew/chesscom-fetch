import pytest
from typer.testing import CliRunner

from chesscom_fetch.cli import app


def test_fetch_rejects_months_below_one(runner: CliRunner) -> None:
    result = runner.invoke(
        app,
        [
            "fetch",
            "murfew",
            "--months",
            "0",
        ],
    )

    assert result.exit_code == 2
    assert "Invalid value for '--months': 0 is not in the range x>=1." in result.stderr


def test_fetch_rejects_unknown_time_class(runner: CliRunner) -> None:
    result = runner.invoke(
        app,
        [
            "fetch",
            "murfew",
            "--time-class",
            "unknown",
        ],
    )

    assert result.exit_code == 2
    assert "Invalid value for '--time-class': 'unknown'" in result.stderr


def test_fetch_rejects_blank_username(runner: CliRunner) -> None:
    result = runner.invoke(
        app,
        [
            "fetch",
        ],
    )

    assert result.exit_code == 2
    assert "Missing argument 'username'." in result.stderr


def test_fetch_accepts_months_of_one(runner: CliRunner) -> None:
    result = runner.invoke(
        app,
        [
            "fetch",
            "murfew",
            "--months",
            "1",
        ],
    )

    assert result.exit_code == 0
    assert "Invalid value for '--months': 1" not in result.stderr


@pytest.mark.skip(reason="No way to test until functionality implemented.")
def test_fetch_defaults_to_one_month() -> None: ...


@pytest.mark.skip(reason="No way to test until functionality implemented.")
def test_fetch_defaults_to_rapid_time_class() -> None: ...
