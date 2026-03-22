"""Unit tests for CLI functionality"""

import pytest
from typer.testing import CliRunner

from aws_fleet_scout import __version__
from aws_fleet_scout.cli import app

runner = CliRunner()


class TestVersionFlag:
    """Test version flag functionality."""

    def test_version_flag_long(self):
        """Should display version with --version flag."""
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert __version__ in result.stdout
        assert "aws-fleet-scout version" in result.stdout

    def test_version_flag_short(self):
        """Should display version with -v flag."""
        result = runner.invoke(app, ["-v"])
        assert result.exit_code == 0
        assert __version__ in result.stdout
        assert "aws-fleet-scout version" in result.stdout

    def test_version_matches_package(self):
        """Version flag should match package version."""
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert __version__ in result.stdout


class TestCLIHelp:
    """Test CLI help functionality."""

    def test_help_flag(self):
        """Should display help with --help flag."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "AWS Fleet Scout" in result.stdout

    def test_spot_command_exists(self):
        """Should have spot command."""
        result = runner.invoke(app, ["--help"])
        assert "spot" in result.stdout

    def test_capacity_command_exists(self):
        """Should have capacity command."""
        result = runner.invoke(app, ["--help"])
        assert "capacity" in result.stdout

    def test_fleet_command_exists(self):
        """Should have fleet command."""
        result = runner.invoke(app, ["--help"])
        assert "fleet" in result.stdout

    def test_compare_command_exists(self):
        """Should have compare command."""
        result = runner.invoke(app, ["--help"])
        assert "compare" in result.stdout
