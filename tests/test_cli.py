"""Tests for kobo2ddi.cli — CLI argument parsing and command dispatch."""

import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from kobo2ddi.cli import main


@pytest.fixture
def mock_client(survey_rows, choices_by_list, settings, submissions, xlsform_path, tmp_path):
    """Return a mocked KoboClient and set up cached pull data."""
    client = MagicMock()
    client.list_assets.return_value = [
        {"uid": "abc123", "name": "Test Survey", "has_deployment": True},
    ]
    client.get_asset.return_value = {"uid": "abc123", "name": "Test Survey"}
    client.get_submissions.return_value = submissions
    client.pull.return_value = tmp_path / "abc123"

    # Pre-populate cached files so transform doesn't need to actually pull
    asset_dir = tmp_path / "abc123"
    asset_dir.mkdir(parents=True, exist_ok=True)

    # Copy fixture xlsform
    (asset_dir / "form.xlsx").write_bytes(xlsform_path.read_bytes())
    (asset_dir / "submissions.json").write_text(
        json.dumps(submissions, indent=2), encoding="utf-8"
    )

    return client, tmp_path


class TestCliList:
    def test_list_prints_assets(self, mock_client, capsys):
        client, _ = mock_client
        with patch("kobo2ddi.cli.KoboClient", return_value=client):
            main(["--token", "fake", "list"])
        out = capsys.readouterr().out
        assert "abc123" in out
        assert "Test Survey" in out
        assert "deployed" in out

    def test_list_empty(self, capsys):
        client = MagicMock()
        client.list_assets.return_value = []
        with patch("kobo2ddi.cli.KoboClient", return_value=client):
            main(["--token", "fake", "list"])
        assert "No assets found" in capsys.readouterr().out


class TestCliPull:
    def test_pull_calls_client(self, mock_client):
        client, _ = mock_client
        with patch("kobo2ddi.cli.KoboClient", return_value=client):
            main(["--token", "fake", "pull", "abc123"])
        client.pull.assert_called_once()


class TestCliTransform:
    def test_transform_creates_xlsx_and_xml(self, mock_client):
        client, tmp_path = mock_client
        with patch("kobo2ddi.cli.KoboClient", return_value=client):
            main(["--token", "fake", "transform", "abc123", "-o", str(tmp_path)])
        asset_dir = tmp_path / "abc123"
        assert (asset_dir / "abc123.xlsx").exists()
        assert (asset_dir / "abc123.xml").exists()

    def test_transform_refresh_calls_pull(self, mock_client):
        client, tmp_path = mock_client
        with patch("kobo2ddi.cli.KoboClient", return_value=client):
            main(["--token", "fake", "transform", "abc123", "-o", str(tmp_path), "--refresh"])
        client.pull.assert_called_once()


class TestCliNoCommand:
    def test_no_command_exits(self):
        with pytest.raises(SystemExit):
            main(["--token", "fake"])
