"""Tests for kobo2ddi.ddi_xml — DDI-Codebook 2.5 XML generation."""

from xml.etree.ElementTree import fromstring

from kobo2ddi.ddi_xml import build_ddi_xml

NS = {"ddi": "ddi:codebook:2_5"}


def _parse(xml_str: str):
    """Parse XML string and return root element."""
    return fromstring(xml_str)


class TestBuildDdiXml:
    def test_returns_valid_xml(self, survey_rows, choices_by_list, settings, submissions):
        xml = build_ddi_xml("Test", survey_rows, choices_by_list, settings, submissions)
        root = _parse(xml)
        # ElementTree expands xmlns into the tag: {namespace}localname
        assert root.tag == "{ddi:codebook:2_5}codeBook"

    def test_codebook_attributes(self, survey_rows, choices_by_list, settings, submissions):
        xml = build_ddi_xml("Test", survey_rows, choices_by_list, settings, submissions)
        root = _parse(xml)
        assert root.get("version") == "2.5"
        # xmlns is consumed by the parser into the tag namespace, not an attribute
        assert root.tag.startswith("{ddi:codebook:2_5}")

    def test_study_title(self, survey_rows, choices_by_list, settings, submissions):
        xml = build_ddi_xml("My Survey Title", survey_rows, choices_by_list, settings, submissions)
        root = _parse(xml)
        titl = root.find(".//ddi:stdyDscr/ddi:citation/ddi:titlStmt/ddi:titl", NS)
        assert titl is not None
        assert titl.text == "My Survey Title"

    def test_study_id(self, survey_rows, choices_by_list, settings, submissions):
        xml = build_ddi_xml("Test", survey_rows, choices_by_list, settings, submissions)
        root = _parse(xml)
        idno = root.find(".//ddi:stdyDscr/ddi:citation/ddi:titlStmt/ddi:IDno", NS)
        assert idno is not None
        assert idno.text == "test_survey_2025"

    def test_version(self, survey_rows, choices_by_list, settings, submissions):
        xml = build_ddi_xml("Test", survey_rows, choices_by_list, settings, submissions)
        root = _parse(xml)
        ver = root.find(".//ddi:stdyDscr/ddi:citation/ddi:verStmt/ddi:version", NS)
        assert ver is not None
        assert ver.text == "1.0"

    def test_variable_groups(self, survey_rows, choices_by_list, settings, submissions):
        xml = build_ddi_xml("Test", survey_rows, choices_by_list, settings, submissions)
        root = _parse(xml)
        var_grps = root.findall(".//ddi:dataDscr/ddi:varGrp", NS)
        grp_names = {g.get("name") for g in var_grps}
        assert "demo" in grp_names
        assert "feedback" in grp_names
        for g in var_grps:
            assert g.get("type") == "Section"
            assert g.get("var")  # has variable IDs

    def test_variable_count(self, survey_rows, choices_by_list, settings, submissions):
        xml = build_ddi_xml("Test", survey_rows, choices_by_list, settings, submissions)
        root = _parse(xml)
        variables = root.findall(".//ddi:dataDscr/ddi:var", NS)
        assert len(variables) == 9  # 9 data-carrying fields

    def test_variable_attributes(self, survey_rows, choices_by_list, settings, submissions):
        xml = build_ddi_xml("Test", survey_rows, choices_by_list, settings, submissions)
        root = _parse(xml)
        variables = root.findall(".//ddi:dataDscr/ddi:var", NS)
        first = variables[0]  # full_name (text → string → discrete/character)
        assert first.get("name") == "full_name"
        assert first.get("intrvl") == "discrete"
        assert first.get("ID") == "V1"

    def test_variable_label_and_question(self, survey_rows, choices_by_list, settings, submissions):
        xml = build_ddi_xml("Test", survey_rows, choices_by_list, settings, submissions)
        root = _parse(xml)
        var = root.findall(".//ddi:dataDscr/ddi:var", NS)[0]
        labl = var.find("ddi:labl", NS)
        qstn_lit = var.find("ddi:qstn/ddi:qstnLit", NS)
        assert labl.text == "Full name"
        assert qstn_lit.text == "Full name"

    def test_select_one_has_categories(self, survey_rows, choices_by_list, settings, submissions):
        xml = build_ddi_xml("Test", survey_rows, choices_by_list, settings, submissions)
        root = _parse(xml)
        # gender is V3 (full_name=V1, age=V2, gender=V3)
        var_gender = root.findall(".//ddi:dataDscr/ddi:var", NS)[2]
        assert var_gender.get("name") == "gender"
        catgries = var_gender.findall("ddi:catgry", NS)
        assert len(catgries) == 3
        vals = [(c.find("ddi:catValu", NS).text, c.find("ddi:labl", NS).text) for c in catgries]
        assert ("m", "Male") in vals
        assert ("f", "Female") in vals

    def test_select_multiple_has_categories(self, survey_rows, choices_by_list, settings, submissions):
        xml = build_ddi_xml("Test", survey_rows, choices_by_list, settings, submissions)
        root = _parse(xml)
        # hobbies = V4
        var_hobbies = root.findall(".//ddi:dataDscr/ddi:var", NS)[3]
        assert var_hobbies.get("name") == "hobbies"
        catgries = var_hobbies.findall("ddi:catgry", NS)
        assert len(catgries) == 3

    def test_text_has_no_categories(self, survey_rows, choices_by_list, settings, submissions):
        xml = build_ddi_xml("Test", survey_rows, choices_by_list, settings, submissions)
        root = _parse(xml)
        var_name = root.findall(".//ddi:dataDscr/ddi:var", NS)[0]
        assert var_name.get("name") == "full_name"
        assert var_name.findall("ddi:catgry", NS) == []

    def test_var_format_types(self, survey_rows, choices_by_list, settings, submissions):
        xml = build_ddi_xml("Test", survey_rows, choices_by_list, settings, submissions)
        root = _parse(xml)
        variables = root.findall(".//ddi:dataDscr/ddi:var", NS)
        by_name = {v.get("name"): v for v in variables}

        def fmt(var_el):
            return var_el.find("ddi:varFormat", NS).get("type")

        assert fmt(by_name["full_name"]) == "character"
        assert fmt(by_name["age"]) == "numeric"
        assert fmt(by_name["gender"]) == "numeric"
        assert fmt(by_name["hobbies"]) == "character"
        assert fmt(by_name["score"]) == "numeric"
        assert fmt(by_name["rating"]) == "numeric"
        assert fmt(by_name["visit_date"]) == "character"

    def test_continuous_vs_discrete(self, survey_rows, choices_by_list, settings, submissions):
        xml = build_ddi_xml("Test", survey_rows, choices_by_list, settings, submissions)
        root = _parse(xml)
        variables = root.findall(".//ddi:dataDscr/ddi:var", NS)
        by_name = {v.get("name"): v for v in variables}
        assert by_name["age"].get("intrvl") == "continuous"
        assert by_name["score"].get("intrvl") == "continuous"
        assert by_name["gender"].get("intrvl") == "discrete"
        assert by_name["full_name"].get("intrvl") == "discrete"

    def test_no_idno_when_missing(self, survey_rows, choices_by_list, submissions):
        xml = build_ddi_xml("Test", survey_rows, choices_by_list, {}, submissions)
        root = _parse(xml)
        idno = root.find(".//ddi:stdyDscr/ddi:citation/ddi:titlStmt/ddi:IDno", NS)
        assert idno is None

    def test_vargrp_before_var_elements(self, survey_rows, choices_by_list, settings, submissions):
        xml = build_ddi_xml("Test", survey_rows, choices_by_list, settings, submissions)
        root = _parse(xml)
        data_dscr = root.find(".//ddi:dataDscr", NS)
        children = list(data_dscr)
        # Find first varGrp and first var
        first_grp_idx = next(i for i, c in enumerate(children) if c.tag.endswith("varGrp"))
        first_var_idx = next(i for i, c in enumerate(children) if c.tag.endswith("}var") or c.tag == "var")
        assert first_grp_idx < first_var_idx
