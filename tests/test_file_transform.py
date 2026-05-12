"""End-to-end pipeline tests from local files only — no API client instantiated.

Track 0.1 baseline + Track B alignment: exercises parse_xlsform → build_ddi_xml
+ build_data_csv for both kobo2ddi and limesurvey2ddi. Asserts CSV header lines
up exactly with ``<var name="">`` in the XML and (optionally) XSD validity.
Tests must pass with all platform credentials removed from the environment.
"""

import csv
import io
import json
import subprocess
import sys
from pathlib import Path
from xml.etree.ElementTree import fromstring

import pytest
from openpyxl import Workbook

from kobo2ddi import ddi_xml as kobo_ddi
from kobo2ddi import transform as kobo_tx
from kobo2ddi.data import build_data_csv
from limesurvey2ddi import transform as lime_tx

NS = {"ddi": "ddi:codebook:2_5"}
SCHEMA_PATH = Path(__file__).parent / "schemas" / "codebook.xsd"


@pytest.fixture
def no_credentials(monkeypatch):
    """Strip every platform credential so any client construction would raise."""
    for var in (
        "KOBO_API_TOKEN", "KOBO_SERVER_URL",
        "LIME_USERNAME", "LIME_PASSWORD", "LIME_SERVER_URL",
    ):
        monkeypatch.delenv(var, raising=False)
    for mod in ("kobo2ddi.client", "limesurvey2ddi.client"):
        sys.modules.pop(mod, None)


def _xml_var_names(xml_str: str) -> list[str]:
    root = fromstring(xml_str)
    return [v.get("name") for v in root.findall(".//ddi:dataDscr/ddi:var", NS)]


def _csv_header(csv_str: str) -> list[str]:
    return next(csv.reader(io.StringIO(csv_str)))


# ---------------------------------------------------------------------------
# Kobo file-based pipeline
# ---------------------------------------------------------------------------


@pytest.fixture
def submissions_json_path(tmp_path, submissions):
    path = tmp_path / "submissions.json"
    path.write_text(json.dumps(submissions), encoding="utf-8")
    return path


class TestKoboFilePipeline:
    def test_build_ddi_xml_from_disk(
        self, xlsform_path, submissions_json_path, no_credentials,
    ):
        survey_rows, choices, settings = kobo_tx.parse_xlsform(xlsform_path)
        submissions = json.loads(submissions_json_path.read_text())

        xml = kobo_ddi.build_ddi_xml(
            "File Pipeline", survey_rows, choices, settings, submissions,
        )
        root = fromstring(xml)
        assert root.tag == "{ddi:codebook:2_5}codeBook"
        titl = root.find(".//ddi:stdyDscr/ddi:citation/ddi:titlStmt/ddi:titl", NS)
        assert titl.text == "File Pipeline"
        assert root.findall(".//ddi:dataDscr/ddi:var", NS)

    def test_csv_header_matches_xml_var_names_set(
        self, xlsform_path, submissions_json_path, no_credentials,
    ):
        survey_rows, choices, settings = kobo_tx.parse_xlsform(xlsform_path)
        submissions = json.loads(submissions_json_path.read_text())
        variables = kobo_tx.extract_variables(survey_rows, choices)

        csv_str = build_data_csv(variables, submissions)
        xml = kobo_ddi.build_ddi_xml(
            "CSV", survey_rows, choices, settings, submissions,
        )

        header = _csv_header(csv_str)
        xml_names = _xml_var_names(xml)
        # Set-equal: every CSV column maps to exactly one <var name=""> and
        # vice versa. Ordering may diverge (CSV follows survey order; XML
        # groups grid/multi-resp blocks first).
        assert set(header) == set(xml_names)
        assert len(header) == len(xml_names)

    def test_csv_select_multiple_binary_expanded(
        self, xlsform_path, submissions_json_path, no_credentials,
    ):
        """``hobbies`` is select_multiple with 3 choices → 3 binary cols of 0/1."""
        survey_rows, choices, _ = kobo_tx.parse_xlsform(xlsform_path)
        submissions = json.loads(submissions_json_path.read_text())
        variables = kobo_tx.extract_variables(survey_rows, choices)

        csv_str = build_data_csv(variables, submissions)
        rows = list(csv.DictReader(io.StringIO(csv_str)))

        # The original column is gone; binary cols replace it.
        assert "hobbies" not in rows[0]
        for col in ("hobbies_sports", "hobbies_music", "hobbies_reading"):
            assert col in rows[0]
            assert rows[0][col] in {"0", "1"}

        # Alice ticked "sports music"; "reading" should be 0.
        alice = rows[0]
        assert alice["hobbies_sports"] == "1"
        assert alice["hobbies_music"] == "1"
        assert alice["hobbies_reading"] == "0"

    @pytest.mark.skipif(
        subprocess.run(["which", "xmllint"], capture_output=True).returncode != 0,
        reason="xmllint not available",
    )
    def test_ddi_xml_validates_against_xsd(
        self, tmp_path, xlsform_path, submissions_json_path, no_credentials,
    ):
        survey_rows, choices, settings = kobo_tx.parse_xlsform(xlsform_path)
        submissions = json.loads(submissions_json_path.read_text())
        xml = kobo_ddi.build_ddi_xml(
            "XSD", survey_rows, choices, settings, submissions,
        )
        path = tmp_path / "out.xml"
        path.write_text(xml, encoding="utf-8")
        result = subprocess.run(
            ["xmllint", "--noout", "--schema", str(SCHEMA_PATH), str(path)],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, f"XSD validation failed:\n{result.stderr}"


# ---------------------------------------------------------------------------
# LimeSurvey file-based pipeline (survey-structure TSV)
# ---------------------------------------------------------------------------

LIME_TSV_FIXTURE = Path(__file__).parent / "fixtures" / "lstsv" / "basic_survey.tsv"


class TestLimeFilePipeline:
    def test_build_ddi_xml_from_tsv(self, no_credentials):
        xml = lime_tx.build_ddi_xml("Lime TSV", LIME_TSV_FIXTURE, [])
        root = fromstring(xml)
        assert root.tag == "{ddi:codebook:2_5}codeBook"
        names = {v.get("name") for v in root.findall(".//ddi:dataDscr/ddi:var", NS)}
        assert names  # at least one variable extracted

    def test_csv_header_matches_xml_var_names_set(self, no_credentials):
        csv_str = lime_tx.build_data_csv(LIME_TSV_FIXTURE, [])
        xml = lime_tx.build_ddi_xml("CSV", LIME_TSV_FIXTURE, [])
        header = _csv_header(csv_str)
        xml_names = _xml_var_names(xml)
        assert set(header) == set(xml_names)
        assert len(header) == len(xml_names)

    @pytest.mark.skipif(
        subprocess.run(["which", "xmllint"], capture_output=True).returncode != 0,
        reason="xmllint not available",
    )
    def test_ddi_xml_validates_against_xsd(self, tmp_path, no_credentials):
        xml = lime_tx.build_ddi_xml("Lime XSD", LIME_TSV_FIXTURE, [])
        path = tmp_path / "lime.xml"
        path.write_text(xml, encoding="utf-8")
        result = subprocess.run(
            ["xmllint", "--noout", "--schema", str(SCHEMA_PATH), str(path)],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, f"XSD validation failed:\n{result.stderr}"
