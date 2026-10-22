import pytest
from typer.testing import CliRunner

from safetylens import __version__
from safetylens.cli import app
from safetylens.validate import is_valid_odino

runner = CliRunner()


def test_version_command_prints_version() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_help_lists_version_command() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "version" in result.output


@pytest.mark.xfail(strict=True, raises=NotImplementedError, reason="TODO(you): implement")
def test_is_valid_odino() -> None:
    assert is_valid_odino("11500123")
    assert not is_valid_odino("")
    assert not is_valid_odino(" 123")
    assert not is_valid_odino("12a")
