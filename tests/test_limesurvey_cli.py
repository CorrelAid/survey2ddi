"""Tests for limesurvey2ddi.cli — CLI argument parsing and command dispatch."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from limesurvey2ddi.cli import main


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

MINIMAL_TSV = (
    "class\ttype/scale\tname\trelevance\ttext\thelp\tlanguage\tvalidation\t"
    "em_validation_q\tmandatory\tother\tdefault\tsame_default\thidden\n"
    "S\t\t\t\t\t\ten\t\t\t\t\t\t\t\n"
    "SL\t\t\tTest Survey\t\ten\t\t\t\t\t\t\t\t\n"
    "G\t\tG1\t\tGroup 1\t\ten\t\t\t\t\t\t\t\n"
    "Q\tT\tq1\t\tQuestion 1\t\ten\t\t\tN\t\t\t\t\n"
)


def _make_tsv(path: Path) -> None:
    """Write a minimal valid LimeSurvey survey-structure TSV."""
    path.write_text(MINIMAL_TSV, encoding="utf-8")


@pytest.fixture
def mock_client(tmp_path):
    """Mocked LimeSurveyClient with pre-populated output directory."""
    client = MagicMock()
    client.list_surveys.return_value = [
        {"sid": "99", "surveyls_title": "Test Survey", "active": "Y"},
        {"sid": "100", "surveyls_title": "Inactive Survey", "active": "N"},
    ]
    client.pull.return_value = tmp_path / "99"

    survey_dir = tmp_path / "99"
    survey_dir.mkdir(parents=True, exist_ok=True)
    _make_tsv(survey_dir / "survey.tsv")
    (survey_dir / "responses.json").write_text(
        json.dumps([{"q1": "hello"}]), encoding="utf-8"
    )

    return client, tmp_path


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------

class TestCliList:
    def test_list_prints_surveys(self, mock_client, capsys):
        client, _ = mock_client
        with patch("limesurvey2ddi.cli.LimeSurveyClient", return_value=client):
            main(["--username", "u", "--password", "p", "list"])
        out = capsys.readouterr().out
        assert "99" in out
        assert "Test Survey" in out
        assert "active" in out

    def test_list_shows_inactive(self, mock_client, capsys):
        client, _ = mock_client
        with patch("limesurvey2ddi.cli.LimeSurveyClient", return_value=client):
            main(["--username", "u", "--password", "p", "list"])
        out = capsys.readouterr().out
        assert "inactive" in out

    def test_list_empty(self, capsys):
        client = MagicMock()
        client.list_surveys.return_value = []
        with patch("limesurvey2ddi.cli.LimeSurveyClient", return_value=client):
            main(["--username", "u", "--password", "p", "list"])
        assert "No surveys found" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# pull
# ---------------------------------------------------------------------------

class TestCliPull:
    def test_pull_calls_client(self, mock_client):
        client, tmp_path = mock_client
        with patch("limesurvey2ddi.cli.LimeSurveyClient", return_value=client):
            main(["--username", "u", "--password", "p", "pull", "99", "-o", str(tmp_path)])
        client.pull.assert_called_once_with(99, output_dir=tmp_path)

    def test_pull_uses_default_output_when_omitted(self, mock_client):
        client, _ = mock_client
        with patch("limesurvey2ddi.cli.LimeSurveyClient", return_value=client):
            main(["--username", "u", "--password", "p", "pull", "99"])
        client.pull.assert_called_once_with(99, output_dir=None)


# ---------------------------------------------------------------------------
# transform
# ---------------------------------------------------------------------------

class TestCliTransform:
    def test_transform_creates_csv_and_xml(self, mock_client):
        client, tmp_path = mock_client
        with patch("limesurvey2ddi.cli.LimeSurveyClient", return_value=client):
            main(["--username", "u", "--password", "p", "transform", "99", "-o", str(tmp_path)])
        survey_dir = tmp_path / "99"
        assert (survey_dir / "99.csv").exists()
        assert (survey_dir / "99.xml").exists()

    def test_transform_uses_title_arg(self, mock_client, capsys):
        client, tmp_path = mock_client
        with patch("limesurvey2ddi.cli.LimeSurveyClient", return_value=client):
            main(["--username", "u", "--password", "p", "transform", "99",
                  "--title", "My Survey", "-o", str(tmp_path)])
        assert "Wrote" in capsys.readouterr().out
        xml = (tmp_path / "99" / "99.xml").read_text()
        assert "<titl>My Survey</titl>" in xml

    def test_transform_defaults_title_to_survey_id(self, mock_client):
        client, tmp_path = mock_client
        with patch("limesurvey2ddi.cli.LimeSurveyClient", return_value=client):
            main(["--username", "u", "--password", "p", "transform", "99", "-o", str(tmp_path)])
        xml = (tmp_path / "99" / "99.xml").read_text()
        assert "<titl>99</titl>" in xml

    def test_transform_with_explicit_schema_arg(self, mock_client, tmp_path):
        client, _ = mock_client
        survey_dir = tmp_path / "102"
        survey_dir.mkdir(parents=True)
        custom_schema = tmp_path / "custom.tsv"
        _make_tsv(custom_schema)
        (survey_dir / "responses.json").write_text(
            json.dumps([{"q1": "world"}]), encoding="utf-8"
        )

        with patch("limesurvey2ddi.cli.LimeSurveyClient", return_value=client):
            main([
                "--username", "u", "--password", "p", "transform", "102",
                "--schema", str(custom_schema),
                "-o", str(tmp_path)
            ])

        assert (survey_dir / "102.xml").exists()

    def test_transform_without_client_instantiation(self, tmp_path):
        """Offline transform: no client constructed if files are present."""
        survey_dir = tmp_path / "103"
        survey_dir.mkdir(parents=True)
        _make_tsv(survey_dir / "survey.tsv")
        (survey_dir / "responses.json").write_text("[]", encoding="utf-8")

        lime_client_mock = MagicMock(side_effect=AssertionError("LimeSurveyClient must not be instantiated"))
        with patch("limesurvey2ddi.cli.LimeSurveyClient", lime_client_mock):
            main(["transform", "103", "-o", str(tmp_path)])

        lime_client_mock.assert_not_called()
        assert (survey_dir / "103.xml").exists()

    def test_transform_with_csv_data(self, mock_client, tmp_path):
        """--data uses a CSV file instead of responses.json."""
        client, _ = mock_client
        survey_dir = tmp_path / "104"
        survey_dir.mkdir(parents=True)
        _make_tsv(survey_dir / "survey.tsv")

        csv_path = tmp_path / "responses.csv"
        csv_path.write_text("id;submitdate;q1\n1;2025-06-01;Alice\n2;2025-06-02;Bob", encoding="utf-8")

        with patch("limesurvey2ddi.cli.LimeSurveyClient", return_value=client):
            main([
                "transform", "104",
                "-o", str(tmp_path),
                "--data", str(csv_path),
                "--title", "CSV Survey",
            ])

        assert (survey_dir / "104.csv").exists()
        assert (survey_dir / "104.xml").exists()
        csv_text = (survey_dir / "104.csv").read_text()
        assert "Alice" in csv_text
        assert "Bob" in csv_text

    def test_transform_missing_schema_exits(self, mock_client, tmp_path):
        client, _ = mock_client
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        (empty_dir / "77").mkdir()
        (empty_dir / "77" / "responses.json").write_text("[]")
        with patch("limesurvey2ddi.cli.LimeSurveyClient", return_value=client):
            with pytest.raises(SystemExit) as exc:
                main(["--username", "u", "--password", "p", "transform", "77",
                      "-o", str(empty_dir)])
        assert exc.value.code == 1

    def test_transform_missing_responses_exits(self, mock_client, tmp_path):
        client, _ = mock_client
        survey_dir = tmp_path / "88"
        survey_dir.mkdir()
        _make_tsv(survey_dir / "survey.tsv")
        with patch("limesurvey2ddi.cli.LimeSurveyClient", return_value=client):
            with pytest.raises(SystemExit) as exc:
                main(["--username", "u", "--password", "p", "transform", "88",
                      "-o", str(tmp_path)])
        assert exc.value.code == 1


# ---------------------------------------------------------------------------
# metadata
# ---------------------------------------------------------------------------

class TestCliMetadata:
    def test_metadata_emits_xml_only(self, tmp_path):
        tsv = tmp_path / "schema.tsv"
        _make_tsv(tsv)
        with patch("limesurvey2ddi.cli.LimeSurveyClient", side_effect=AssertionError):
            main(["metadata", str(tsv)])
        assert (tmp_path / "schema.xml").exists()


# ---------------------------------------------------------------------------
# no command
# ---------------------------------------------------------------------------

class TestCliNoCommand:
    def test_no_command_exits(self):
        with pytest.raises(SystemExit):
            main(["--username", "u", "--password", "p"])
