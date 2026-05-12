"""Tests for kobo2ddi.cli — KoboToolbox CLI argument parsing and command dispatch."""

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
    def test_transform_creates_csv_and_xml(self, mock_client):
        client, tmp_path = mock_client
        with patch("kobo2ddi.cli.KoboClient", return_value=client):
            main(["--token", "fake", "transform", "abc123", "-o", str(tmp_path)])
        asset_dir = tmp_path / "abc123"
        assert (asset_dir / "abc123.csv").exists()
        assert (asset_dir / "abc123.xml").exists()

    def test_transform_refresh_calls_pull(self, mock_client):
        client, tmp_path = mock_client
        with patch("kobo2ddi.cli.KoboClient", return_value=client):
            main(["--token", "fake", "transform", "abc123", "-o", str(tmp_path), "--refresh"])
        client.pull.assert_called_once()

    def test_transform_with_title_skips_api(self, mock_client):
        """--title with cached files: no client constructed, no API hit."""
        client, tmp_path = mock_client
        kobo_client_mock = MagicMock(side_effect=AssertionError("KoboClient must not be instantiated"))
        with patch("kobo2ddi.cli.KoboClient", kobo_client_mock):
            main([
                "transform", "abc123",
                "-o", str(tmp_path),
                "--title", "My Cached Survey",
            ])
        kobo_client_mock.assert_not_called()
        asset_dir = tmp_path / "abc123"
        assert (asset_dir / "abc123.csv").exists()
        assert (asset_dir / "abc123.xml").exists()

    def test_transform_with_title_uses_title_in_output(self, mock_client):
        """--title value lands in DDI XML study title, not whatever get_asset would have returned."""
        client, tmp_path = mock_client
        with patch("kobo2ddi.cli.KoboClient", return_value=client):
            main([
                "transform", "abc123",
                "-o", str(tmp_path),
                "--title", "Custom Title",
            ])
        client.get_asset.assert_not_called()
        xml_text = (tmp_path / "abc123" / "abc123.xml").read_text()
        assert "<titl>Custom Title</titl>" in xml_text

    def test_transform_without_title_falls_back_to_api(self, mock_client, tmp_path):
        """No --title: get_asset is called for the survey name."""
        client, tmp_path = mock_client
        with patch("kobo2ddi.cli.KoboClient", return_value=client):
            main(["--token", "fake", "transform", "abc123", "-o", str(tmp_path)])
        client.get_asset.assert_called_once_with("abc123")

    def test_transform_with_csv_data(self, mock_client, tmp_path):
        """--data uses a CSV file instead of submissions.json."""
        client, tmp_path = mock_client
        asset_dir = tmp_path / "abc123"
        asset_dir.mkdir(parents=True, exist_ok=True)
        # Use semicolon as delimiter, XML values as headers (including group prefix)
        csv_path = tmp_path / "data.csv"
        csv_path.write_text("demo/full_name;demo/age\nAlice;25\nBob;30", encoding="utf-8")

        with patch("kobo2ddi.cli.KoboClient", return_value=client):
            main([
                "transform", "abc123",
                "-o", str(tmp_path),
                "--data", str(csv_path),
                "--title", "CSV Survey",
            ])

        assert (asset_dir / "abc123.csv").exists()
        assert (asset_dir / "abc123.xml").exists()

        # Verify CSV content
        result_csv = (asset_dir / "abc123.csv").read_text()
        assert "Alice" in result_csv
        assert "Bob" in result_csv


class TestCliNoCommand:
    def test_no_command_exits(self):
        with pytest.raises(SystemExit):
            main(["--token", "fake"])
