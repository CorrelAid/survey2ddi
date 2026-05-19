"""Tests for the LimeSurvey survey-structure TSV parser and pipeline."""

from pathlib import Path
from xml.etree.ElementTree import fromstring

import pytest

from limesurvey2ddi.lstsv import parse_lstsv
from limesurvey2ddi.transform import (
    build_data_csv,
    build_ddi_xml,
)

from _helpers import DDI_NS as NS
from _helpers.xsd import requires_xmllint, validate_with_xsd

FIXTURES = Path(__file__).parent / "fixtures" / "lstsv"


def _types(survey_rows):
    return [r["type"] for r in survey_rows]


def _names(survey_rows):
    return [r["name"] for r in survey_rows if r["name"]]


# ---------------------------------------------------------------------------
# parse_lstsv — unit tests
# ---------------------------------------------------------------------------


class TestParseLstsvBasic:
    @pytest.fixture
    def parsed(self):
        return parse_lstsv(FIXTURES / "basic_survey.tsv")

    def test_settings_title_and_language(self, parsed):
        _, _, settings = parsed
        assert settings["default_language"] == "en"
        assert settings["id_string"] == "Basic Survey"

    def test_questions_extracted(self, parsed):
        survey_rows, _, _ = parsed
        names = _names(survey_rows)
        assert "respondentname" in names
        assert "age" in names
        assert "consent" in names
        assert "thankyou" in names

    def test_type_mapping(self, parsed):
        survey_rows, _, _ = parsed
        by_name = {r["name"]: r for r in survey_rows if r["name"]}
        assert by_name["respondentname"]["type"] == "text"
        assert by_name["age"]["type"] == "decimal"
        assert by_name["consent"]["type"].startswith("select_one ")
        assert by_name["thankyou"]["type"] == "note"

    def test_choices_attached_to_select_one(self, parsed):
        _, choices, _ = parsed
        assert "consent_list" in choices
        codes = [c.name for c in choices["consent_list"]]
        assert "yes" in codes and "no" in codes

    def test_required_flag(self, parsed):
        survey_rows, _, _ = parsed
        by_name = {r["name"]: r for r in survey_rows if r["name"]}
        assert by_name["respondentname"]["required"] == "true"
        assert by_name["consent"]["required"] == "true"


class TestParseLstsvAllTypes:
    @pytest.fixture
    def parsed(self):
        return parse_lstsv(FIXTURES / "all_types_survey.tsv")

    def test_full_type_coverage(self, parsed):
        survey_rows, _, _ = parsed
        by_name = {r["name"]: r for r in survey_rows if r["name"]}
        # text / numeric / date
        assert by_name["qtext"]["type"] == "text"
        assert by_name["qmultilinetext"]["type"] == "text"
        assert by_name["qinteger"]["type"] == "decimal"
        assert by_name["qdecimal"]["type"] == "decimal"
        assert by_name["qdate"]["type"] == "date"
        assert by_name["qdatetime"]["type"] == "date"
        # selects
        assert by_name["qselectone"]["type"].startswith("select_one ")
        assert by_name["qminimal"]["type"].startswith("select_one ")
        assert by_name["qselectmulti"]["type"].startswith("select_multiple ")
        assert by_name["qrank"]["type"].startswith("rank ")
        # special
        assert by_name["qnote"]["type"] == "note"
        assert by_name["calc1"]["type"] == "calculate"

    def test_select_multiple_subquestions_become_choices(self, parsed):
        _, choices, _ = parsed
        codes = [c.name for c in choices["qselectmulti_list"]]
        assert codes == ["red", "blue", "green"]

    def test_rank_answers_become_choices(self, parsed):
        _, choices, _ = parsed
        codes = [c.name for c in choices["qrank_list"]]
        assert codes == ["fam", "work", "fun"]

    def test_matrix_emits_table_list_group(self, parsed):
        survey_rows, _, _ = parsed
        # Find the begin_group for the matrix
        matrix_groups = [
            r for r in survey_rows
            if r["type"] == "begin_group" and r.get("appearance") == "table-list"
        ]
        assert len(matrix_groups) == 1
        assert matrix_groups[0]["name"] == "matrixheader"

    def test_matrix_subquestions_emit_select_one(self, parsed):
        survey_rows, _, _ = parsed
        names = _names(survey_rows)
        for sq in ("skillpython", "skilljs", "skillsql"):
            assert sq in names
        by_name = {r["name"]: r for r in survey_rows if r["name"]}
        for sq in ("skillpython", "skilljs", "skillsql"):
            assert by_name[sq]["type"] == "select_one matrixheader_list"

    def test_matrix_choices_from_a_rows(self, parsed):
        _, choices, _ = parsed
        codes = [c.name for c in choices["matrixheader_list"]]
        assert codes == ["none", "basic", "adv", "exp"]


class TestParseLstsvComplex:
    @pytest.fixture
    def parsed(self):
        return parse_lstsv(FIXTURES / "complex_survey.tsv")

    def test_groups_open_and_close(self, parsed):
        survey_rows, _, _ = parsed
        types = _types(survey_rows)
        assert types.count("begin_group") >= 3
        # Every begin_group eventually closed
        assert types.count("begin_group") == types.count("end_group")

    def test_select_multiple_choices(self, parsed):
        _, choices, _ = parsed
        codes = [c.name for c in choices["favoritecolors_list"]]
        assert set(codes) == {"red", "blue", "green", "yello"}

    def test_rank_choices(self, parsed):
        _, choices, _ = parsed
        codes = [c.name for c in choices["lifepriorities_list"]]
        assert codes == ["famil", "caree", "healt", "frien"]


# ---------------------------------------------------------------------------
# End-to-end: build_ddi_xml produces XSD-valid XML
# ---------------------------------------------------------------------------


@requires_xmllint
@pytest.mark.parametrize("fixture", ["basic_survey", "all_types_survey", "complex_survey"])
def test_lstsv_pipeline_validates_against_xsd(fixture, tmp_path):
    xml = build_ddi_xml(fixture, FIXTURES / f"{fixture}.tsv", [])
    out = tmp_path / f"{fixture}.xml"
    out.write_text(xml, encoding="utf-8")
    validate_with_xsd(out)


def test_build_data_csv_smoke():
    csv_str = build_data_csv(FIXTURES / "basic_survey.tsv", [])
    # Header line only (no responses)
    assert csv_str.endswith("\r\n")
    header = csv_str.splitlines()[0].split(",")
    # Variables from basic_survey.tsv (note ``thankyou`` is a note → not in CSV)
    for name in ("respondentname", "age", "consent"):
        assert name in header
    assert "thankyou" not in header


def test_build_ddi_xml_has_vars():
    xml = build_ddi_xml("Basic", FIXTURES / "basic_survey.tsv", [])
    root = fromstring(xml)
    names = {v.get("name") for v in root.findall(".//ddi:dataDscr/ddi:var", NS)}
    # respondentname and age should be present
    assert "respondentname" in names
    assert "age" in names
