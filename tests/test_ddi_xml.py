"""Tests for kobo2ddi.ddi_xml — DDI-Codebook 2.5 XML generation (qwacback-compliant)."""

import subprocess
from pathlib import Path
from xml.etree.ElementTree import fromstring

import pytest

from kobo2ddi.ddi_xml import build_ddi_xml

NS = {"ddi": "ddi:codebook:2_5"}
SCHEMA_DIR = Path(__file__).parent / "schemas"
SCHEMA_PATH = SCHEMA_DIR / "codebook.xsd"


def _parse(xml_str: str):
    """Parse XML string and return root element."""
    return fromstring(xml_str)


def _vars_by_name(root):
    """Return {name: element} for all <var> elements."""
    return {v.get("name"): v for v in root.findall(".//ddi:dataDscr/ddi:var", NS)}


class TestBuildDdiXml:
    def test_returns_valid_xml(self, survey_rows, choices_by_list, settings, submissions):
        xml = build_ddi_xml("Test", survey_rows, choices_by_list, settings, submissions)
        root = _parse(xml)
        assert root.tag == "{ddi:codebook:2_5}codeBook"

    def test_codebook_attributes(self, survey_rows, choices_by_list, settings, submissions):
        xml = build_ddi_xml("Test", survey_rows, choices_by_list, settings, submissions)
        root = _parse(xml)
        assert root.get("version") == "2.5"

    def test_study_title(self, survey_rows, choices_by_list, settings, submissions):
        xml = build_ddi_xml("My Survey Title", survey_rows, choices_by_list, settings, submissions)
        root = _parse(xml)
        titl = root.find(".//ddi:stdyDscr/ddi:citation/ddi:titlStmt/ddi:titl", NS)
        assert titl is not None
        assert titl.text == "My Survey Title"

    def test_study_id(self, survey_rows, choices_by_list, settings, submissions):
        xml = build_ddi_xml("Test", survey_rows, choices_by_list, settings, submissions)
        root = _parse(xml)
        idno = root.find(".//ddi:stdyDscr/ddi:citation/ddi:titlStmt/ddi:IDNo", NS)
        assert idno is not None
        assert idno.text == "test_survey_2025"

    def test_version(self, survey_rows, choices_by_list, settings, submissions):
        xml = build_ddi_xml("Test", survey_rows, choices_by_list, settings, submissions)
        root = _parse(xml)
        ver = root.find(".//ddi:stdyDscr/ddi:citation/ddi:verStmt/ddi:version", NS)
        assert ver is not None
        assert ver.text == "1.0"

    def test_no_idno_when_missing(self, survey_rows, choices_by_list, submissions):
        xml = build_ddi_xml("Test", survey_rows, choices_by_list, {}, submissions)
        root = _parse(xml)
        idno = root.find(".//ddi:stdyDscr/ddi:citation/ddi:titlStmt/ddi:IDNo", NS)
        assert idno is None


class TestConceptInsteadOfLabl:
    """Variables use <concept> not <labl>."""

    def test_var_has_concept(self, survey_rows, choices_by_list, settings, submissions):
        xml = build_ddi_xml("Test", survey_rows, choices_by_list, settings, submissions)
        root = _parse(xml)
        by_name = _vars_by_name(root)
        concept = by_name["full_name"].find("ddi:concept", NS)
        assert concept is not None
        assert concept.text == "Full name"

    def test_var_has_no_labl(self, survey_rows, choices_by_list, settings, submissions):
        xml = build_ddi_xml("Test", survey_rows, choices_by_list, settings, submissions)
        root = _parse(xml)
        by_name = _vars_by_name(root)
        assert by_name["full_name"].find("ddi:labl", NS) is None

    def test_category_still_has_labl(self, survey_rows, choices_by_list, settings, submissions):
        xml = build_ddi_xml("Test", survey_rows, choices_by_list, settings, submissions)
        root = _parse(xml)
        by_name = _vars_by_name(root)
        catgries = by_name["gender"].findall("ddi:catgry", NS)
        assert all(c.find("ddi:labl", NS) is not None for c in catgries)


class TestResponseDomainType:
    """Every <qstn> has responseDomainType."""

    def test_select_one_category(self, survey_rows, choices_by_list, settings, submissions):
        xml = build_ddi_xml("Test", survey_rows, choices_by_list, settings, submissions)
        root = _parse(xml)
        by_name = _vars_by_name(root)
        assert by_name["gender"].find("ddi:qstn", NS).get("responseDomainType") == "category"

    def test_text_type(self, survey_rows, choices_by_list, settings, submissions):
        xml = build_ddi_xml("Test", survey_rows, choices_by_list, settings, submissions)
        root = _parse(xml)
        by_name = _vars_by_name(root)
        assert by_name["full_name"].find("ddi:qstn", NS).get("responseDomainType") == "text"

    def test_integer_numeric(self, survey_rows, choices_by_list, settings, submissions):
        xml = build_ddi_xml("Test", survey_rows, choices_by_list, settings, submissions)
        root = _parse(xml)
        by_name = _vars_by_name(root)
        assert by_name["age"].find("ddi:qstn", NS).get("responseDomainType") == "numeric"


class TestElementOrdering:
    """XSD requires: qstn → catgry* → concept → varFormat."""

    def test_var_element_order(self, survey_rows, choices_by_list, settings, submissions):
        xml = build_ddi_xml("Test", survey_rows, choices_by_list, settings, submissions)
        root = _parse(xml)
        by_name = _vars_by_name(root)
        gender = by_name["gender"]
        children = [c.tag.split("}")[-1] for c in gender]
        # qstn comes first, then catgry elements, then concept, then varFormat
        qstn_idx = children.index("qstn")
        concept_idx = children.index("concept")
        fmt_idx = children.index("varFormat")
        catgry_indices = [i for i, t in enumerate(children) if t == "catgry"]
        assert qstn_idx < min(catgry_indices)
        assert max(catgry_indices) < concept_idx
        assert concept_idx < fmt_idx


class TestVarFormatSchema:
    """varFormat has schema='other'."""

    def test_schema_attribute(self, survey_rows, choices_by_list, settings, submissions):
        xml = build_ddi_xml("Test", survey_rows, choices_by_list, settings, submissions)
        root = _parse(xml)
        by_name = _vars_by_name(root)
        fmt = by_name["full_name"].find("ddi:varFormat", NS)
        assert fmt.get("schema") == "other"


class TestVarFormatTypes:
    def test_format_types(self, survey_rows, choices_by_list, settings, submissions):
        xml = build_ddi_xml("Test", survey_rows, choices_by_list, settings, submissions)
        root = _parse(xml)
        by_name = _vars_by_name(root)

        def fmt(var_el):
            return var_el.find("ddi:varFormat", NS).get("type")

        assert fmt(by_name["full_name"]) == "character"
        assert fmt(by_name["age"]) == "numeric"
        assert fmt(by_name["gender"]) == "numeric"
        assert fmt(by_name["score"]) == "numeric"
        assert fmt(by_name["rating"]) == "numeric"
        assert fmt(by_name["visit_date"]) == "character"


class TestIntrvl:
    def test_contin_vs_discrete(self, survey_rows, choices_by_list, settings, submissions):
        xml = build_ddi_xml("Test", survey_rows, choices_by_list, settings, submissions)
        root = _parse(xml)
        by_name = _vars_by_name(root)
        assert by_name["age"].get("intrvl") == "contin"
        assert by_name["score"].get("intrvl") == "contin"
        assert by_name["gender"].get("intrvl") == "discrete"
        assert by_name["full_name"].get("intrvl") == "discrete"


class TestNatureAttribute:
    """``nature`` is deliberately omitted — qwacback's converter never emits it."""

    def test_nature_absent(self, survey_rows, choices_by_list, settings, submissions):
        xml = build_ddi_xml("Test", survey_rows, choices_by_list, settings, submissions)
        root = _parse(xml)
        by_name = _vars_by_name(root)
        for var in by_name.values():
            assert var.get("nature") is None


class TestIdFormat:
    """IDs use V_<name> format."""

    def test_var_id_format(self, survey_rows, choices_by_list, settings, submissions):
        xml = build_ddi_xml("Test", survey_rows, choices_by_list, settings, submissions)
        root = _parse(xml)
        by_name = _vars_by_name(root)
        assert by_name["full_name"].get("ID") == "V_full_name"
        assert by_name["gender"].get("ID") == "V_gender"

    def test_vargrp_id_format(self, survey_rows, choices_by_list, settings, submissions):
        xml = build_ddi_xml("Test", survey_rows, choices_by_list, settings, submissions)
        root = _parse(xml)
        grps = root.findall(".//ddi:dataDscr/ddi:varGrp", NS)
        hobbies_grp = [g for g in grps if g.get("name") == "hobbies"]
        assert len(hobbies_grp) == 1
        assert hobbies_grp[0].get("ID") == "VG_hobbies"


class TestNoSectionGroups:
    """Section groups (demo, feedback) are dropped."""

    def test_no_section_type_groups(self, survey_rows, choices_by_list, settings, submissions):
        xml = build_ddi_xml("Test", survey_rows, choices_by_list, settings, submissions)
        root = _parse(xml)
        grps = root.findall(".//ddi:dataDscr/ddi:varGrp", NS)
        types = [g.get("type") for g in grps]
        assert "section" not in types

    def test_demo_group_not_present(self, survey_rows, choices_by_list, settings, submissions):
        xml = build_ddi_xml("Test", survey_rows, choices_by_list, settings, submissions)
        root = _parse(xml)
        grps = root.findall(".//ddi:dataDscr/ddi:varGrp", NS)
        names = [g.get("name") for g in grps]
        assert "demo" not in names
        assert "feedback" not in names


class TestSelectMultipleExpansion:
    """select_multiple → multipleResp group + binary vars."""

    def test_hobbies_becomes_multipleResp_group(self, survey_rows, choices_by_list, settings, submissions):
        xml = build_ddi_xml("Test", survey_rows, choices_by_list, settings, submissions)
        root = _parse(xml)
        grps = root.findall(".//ddi:dataDscr/ddi:varGrp", NS)
        hobbies_grp = [g for g in grps if g.get("name") == "hobbies"]
        assert len(hobbies_grp) == 1
        grp = hobbies_grp[0]
        assert grp.get("type") == "multipleResp"

    def test_multipleResp_has_concept(self, survey_rows, choices_by_list, settings, submissions):
        xml = build_ddi_xml("Test", survey_rows, choices_by_list, settings, submissions)
        root = _parse(xml)
        grps = root.findall(".//ddi:dataDscr/ddi:varGrp", NS)
        grp = [g for g in grps if g.get("name") == "hobbies"][0]
        concept = grp.find("ddi:concept", NS)
        assert concept is not None
        assert concept.text == "Hobbies"

    def test_multipleResp_has_txt(self, survey_rows, choices_by_list, settings, submissions):
        xml = build_ddi_xml("Test", survey_rows, choices_by_list, settings, submissions)
        root = _parse(xml)
        grps = root.findall(".//ddi:dataDscr/ddi:varGrp", NS)
        grp = [g for g in grps if g.get("name") == "hobbies"][0]
        txt = grp.find("ddi:txt", NS)
        assert txt is not None
        assert txt.text == "Hobbies"

    def test_binary_vars_created(self, survey_rows, choices_by_list, settings, submissions):
        xml = build_ddi_xml("Test", survey_rows, choices_by_list, settings, submissions)
        root = _parse(xml)
        by_name = _vars_by_name(root)
        assert "hobbies_sports" in by_name
        assert "hobbies_music" in by_name
        assert "hobbies_reading" in by_name

    def test_binary_var_structure(self, survey_rows, choices_by_list, settings, submissions):
        xml = build_ddi_xml("Test", survey_rows, choices_by_list, settings, submissions)
        root = _parse(xml)
        by_name = _vars_by_name(root)
        sports = by_name["hobbies_sports"]

        # responseDomainType = multiple
        assert sports.find("ddi:qstn", NS).get("responseDomainType") == "multiple"
        # preQTxt = original question label
        assert sports.find("ddi:qstn/ddi:preQTxt", NS).text == "Hobbies"
        # qstnLit = choice label
        assert sports.find("ddi:qstn/ddi:qstnLit", NS).text == "Sports"
        # Binary categories 0 and 1, no labl
        catgries = sports.findall("ddi:catgry", NS)
        assert len(catgries) == 2
        vals = [c.find("ddi:catValu", NS).text for c in catgries]
        assert vals == ["0", "1"]
        assert all(c.find("ddi:labl", NS) is None for c in catgries)
        # concept
        assert sports.find("ddi:concept", NS).text == "Hobbies: Sports"
        # intrvl and format
        assert sports.get("intrvl") == "discrete"
        assert sports.find("ddi:varFormat", NS).get("type") == "numeric"

    def test_group_references_binary_var_ids(self, survey_rows, choices_by_list, settings, submissions):
        xml = build_ddi_xml("Test", survey_rows, choices_by_list, settings, submissions)
        root = _parse(xml)
        grps = root.findall(".//ddi:dataDscr/ddi:varGrp", NS)
        grp = [g for g in grps if g.get("name") == "hobbies"][0]
        var_ids = grp.get("var").split()
        assert var_ids == ["V_hobbies_sports", "V_hobbies_music", "V_hobbies_reading"]

    def test_original_hobbies_var_not_present(self, survey_rows, choices_by_list, settings, submissions):
        """The original single 'hobbies' var should not exist — only binary vars."""
        xml = build_ddi_xml("Test", survey_rows, choices_by_list, settings, submissions)
        root = _parse(xml)
        by_name = _vars_by_name(root)
        assert "hobbies" not in by_name

    def test_total_variable_count(self, survey_rows, choices_by_list, settings, submissions):
        """9 standalone (inc. `thanks` note) + 3 binary (hobbies expanded) = 12 vars."""
        xml = build_ddi_xml("Test", survey_rows, choices_by_list, settings, submissions)
        root = _parse(xml)
        variables = root.findall(".//ddi:dataDscr/ddi:var", NS)
        assert len(variables) == 12


class TestGridGroup:
    """Grid groups from table-list appearance."""

    def test_grid_group_created(self, grid_survey_rows, grid_choices, settings, submissions):
        xml = build_ddi_xml("Test", grid_survey_rows, grid_choices, settings, [])
        root = _parse(xml)
        grps = root.findall(".//ddi:dataDscr/ddi:varGrp", NS)
        assert len(grps) == 1
        grp = grps[0]
        assert grp.get("type") == "grid"
        assert grp.get("name") == "trust"

    def test_grid_group_has_concept_and_txt(self, grid_survey_rows, grid_choices, settings, submissions):
        """Grid group emits both <concept> and <txt> with the group label."""
        xml = build_ddi_xml("Test", grid_survey_rows, grid_choices, settings, [])
        root = _parse(xml)
        grp = root.findall(".//ddi:dataDscr/ddi:varGrp", NS)[0]
        assert grp.find("ddi:concept", NS).text == "Trust in institutions"
        assert grp.find("ddi:txt", NS).text == "Trust in institutions"

    def test_grid_members_have_preQTxt(self, grid_survey_rows, grid_choices, settings, submissions):
        """Each grid member var carries <preQTxt> = group label."""
        xml = build_ddi_xml("Test", grid_survey_rows, grid_choices, settings, [])
        root = _parse(xml)
        by_name = _vars_by_name(root)
        for name in ("trust_parliament", "trust_police"):
            pre = by_name[name].find("ddi:qstn/ddi:preQTxt", NS)
            assert pre is not None
            assert pre.text == "Trust in institutions"

    def test_grid_members_have_categories(self, grid_survey_rows, grid_choices, settings, submissions):
        xml = build_ddi_xml("Test", grid_survey_rows, grid_choices, settings, [])
        root = _parse(xml)
        by_name = _vars_by_name(root)
        catgries = by_name["trust_parliament"].findall("ddi:catgry", NS)
        assert len(catgries) == 5

    def test_grid_var_ids_in_group(self, grid_survey_rows, grid_choices, settings, submissions):
        xml = build_ddi_xml("Test", grid_survey_rows, grid_choices, settings, [])
        root = _parse(xml)
        grp = root.findall(".//ddi:dataDscr/ddi:varGrp", NS)[0]
        var_ids = grp.get("var").split()
        assert var_ids == ["V_trust_parliament", "V_trust_police"]

    def test_vargrp_before_var_elements(self, grid_survey_rows, grid_choices, settings, submissions):
        xml = build_ddi_xml("Test", grid_survey_rows, grid_choices, settings, [])
        root = _parse(xml)
        data_dscr = root.find(".//ddi:dataDscr", NS)
        children = list(data_dscr)
        first_grp_idx = next(i for i, c in enumerate(children) if c.tag.endswith("varGrp"))
        first_var_idx = next(i for i, c in enumerate(children) if c.tag.endswith("}var") or c.tag == "var")
        assert first_grp_idx < first_var_idx


class TestXsdValidation:
    """Validate generated XML against the official DDI-Codebook 2.5 XSD."""

    @pytest.fixture
    def xml_file(self, tmp_path, survey_rows, choices_by_list, settings, submissions):
        xml_str = build_ddi_xml("Test Survey", survey_rows, choices_by_list, settings, submissions)
        path = tmp_path / "test.xml"
        path.write_text(xml_str, encoding="utf-8")
        return path

    @pytest.fixture
    def grid_xml_file(self, tmp_path, grid_survey_rows, grid_choices, settings):
        xml_str = build_ddi_xml("Grid Test", grid_survey_rows, grid_choices, settings, [])
        path = tmp_path / "grid_test.xml"
        path.write_text(xml_str, encoding="utf-8")
        return path

    @pytest.mark.skipif(
        subprocess.run(["which", "xmllint"], capture_output=True).returncode != 0,
        reason="xmllint not available",
    )
    def test_validates_against_ddi_codebook_25_xsd(self, xml_file):
        result = subprocess.run(
            ["xmllint", "--noout", "--schema", str(SCHEMA_PATH), str(xml_file)],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, (
            f"XSD validation failed:\n{result.stderr}"
        )

    @pytest.mark.skipif(
        subprocess.run(["which", "xmllint"], capture_output=True).returncode != 0,
        reason="xmllint not available",
    )
    def test_grid_validates_against_xsd(self, grid_xml_file):
        result = subprocess.run(
            ["xmllint", "--noout", "--schema", str(SCHEMA_PATH), str(grid_xml_file)],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, (
            f"XSD validation failed:\n{result.stderr}"
        )
