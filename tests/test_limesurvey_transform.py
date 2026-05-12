"""Tests for limesurvey2ddi.transform — response normalisation."""

import pytest

from kobo2ddi.transform import extract_variables
from limesurvey2ddi.transform import normalize_responses

# ---------------------------------------------------------------------------
# Fixtures — a minimal LimeSurvey-style survey
# ---------------------------------------------------------------------------

LIME_SURVEY_ROWS = [
    {"type": "select_one haeufigkeit", "name": "haeufigkeit", "label": "How often?", "required": "true", "appearance": None},
    {"type": "select_multiple bereiche", "name": "bereiche", "label": "Which areas?", "required": "false", "appearance": None},
    {"type": "select_one likert5", "name": "beruf_post", "label": "Career clarity", "required": "true", "appearance": None},
    {"type": "text", "name": "am_meisten_gebracht", "label": "What helped most?", "required": "false", "appearance": None},
    {"type": "select_one nps", "name": "nps_score", "label": "NPS", "required": "true", "appearance": None},
]

LIME_CHOICES = {
    "haeufigkeit": [
        {"name": "1", "label": "Once"},
        {"name": "2", "label": "Sometimes"},
    ],
    "bereiche": [
        {"name": "holz", "label": "Wood workshop"},
        {"name": "metall", "label": "Metal workshop"},
        {"name": "textil", "label": "Textile workshop"},
        {"name": "digital", "label": "Digital workshop"},
    ],
    "likert5": [
        {"name": "1", "label": "Strongly disagree"},
        {"name": "5", "label": "Strongly agree"},
    ],
    "nps": [{"name": str(i), "label": str(i)} for i in range(11)],
}

LIME_SETTINGS = {"id_string": "lime_test", "version": "1.0", "default_language": "Deutsch"}

# A single LimeSurvey response row — note the export quirks:
#   - underscores stripped: beruf_post → berufpost, am_meisten_gebracht → ammeistengebracht, nps_score → npsscore
#   - select_multiple as sub-columns with truncated option codes (5 chars max)
#   - metadata fields mixed in
LIME_RESPONSE_ROW = {
    "id": "1",
    "submitdate": "2025-01-01",
    "startdate": "2025-01-01",
    "datestamp": "2025-01-01",
    "lastpage": "5",
    "startlanguage": "de",
    "seed": "42",
    "haeufigkeit": "Once",
    "bereiche[holz]": "Yes",
    "bereiche[metal]": "No",     # metall truncated to metal
    "bereiche[texti]": "Yes",    # textil truncated to texti
    "bereiche[digit]": "No",     # digital truncated to digit
    "berufpost": "Strongly agree",
    "ammeistengebracht": "It was great",
    "npsscore": "9",
}


@pytest.fixture
def lime_variables():
    return extract_variables(LIME_SURVEY_ROWS, LIME_CHOICES)


@pytest.fixture
def lime_responses():
    return [LIME_RESPONSE_ROW]


# ---------------------------------------------------------------------------
# normalize_responses
# ---------------------------------------------------------------------------


class TestNormalizeResponses:
    def test_simple_field_lookup(self, lime_variables, lime_responses):
        result = normalize_responses(lime_variables, lime_responses)
        assert result[0]["haeufigkeit"] == "Once"

    def test_underscore_stripping(self, lime_variables, lime_responses):
        """beruf_post in form → berufpost in LimeSurvey export."""
        result = normalize_responses(lime_variables, lime_responses)
        assert result[0]["beruf_post"] == "Strongly agree"

    def test_underscore_stripping_multiple(self, lime_variables, lime_responses):
        """am_meisten_gebracht → ammeistengebracht, nps_score → npsscore."""
        result = normalize_responses(lime_variables, lime_responses)
        assert result[0]["am_meisten_gebracht"] == "It was great"
        assert result[0]["nps_score"] == "9"

    def test_select_multiple_yes_becomes_code(self, lime_variables, lime_responses):
        """bereiche[holz]="Yes" → "holz" is included in the result."""
        result = normalize_responses(lime_variables, lime_responses)
        selected = result[0]["bereiche"].split()
        assert "holz" in selected

    def test_select_multiple_no_excluded(self, lime_variables, lime_responses):
        """bereiche[metal]="No" → "metall" should not appear in the result."""
        result = normalize_responses(lime_variables, lime_responses)
        selected = result[0]["bereiche"].split()
        assert "metall" not in selected
        assert "metal" not in selected

    def test_select_multiple_truncated_code_recovered(self, lime_variables, lime_responses):
        """bereiche[texti]="Yes" → recovers full code "textil" via prefix match."""
        result = normalize_responses(lime_variables, lime_responses)
        selected = result[0]["bereiche"].split()
        assert "textil" in selected

    def test_select_multiple_all_no(self, lime_variables):
        """All sub-columns "No" → empty string."""
        row = {
            "bereiche[holz]": "No", "bereiche[metal]": "No",
            "bereiche[texti]": "No", "bereiche[digit]": "No",
        }
        result = normalize_responses(lime_variables, [row])
        assert result[0]["bereiche"] == ""

    def test_select_multiple_ambiguous_prefix_raises(self):
        """Two choice codes sharing the same 5-char prefix → ValueError, not silent wrong data."""
        from kobo2ddi.transform import extract_variables
        rows = [{"type": "select_multiple tags", "name": "tags", "label": "Tags", "required": "false"}]
        # "optie_a" and "optie_b" both truncate to "optie" in LimeSurvey bracket keys
        choices = {"tags": [{"name": "optie_a", "label": "A"}, {"name": "optie_b", "label": "B"}]}
        variables = extract_variables(rows, choices)
        response = [{"tags[optie]": "Yes"}]
        with pytest.raises(ValueError, match="Ambiguous"):
            normalize_responses(variables, response)

    def test_select_multiple_unknown_bracket_key_warns(self):
        """Bracket key with no matching choice code → warning, raw key used."""
        from kobo2ddi.transform import extract_variables
        rows = [{"type": "select_multiple opts", "name": "opts", "label": "Opts", "required": "false"}]
        choices = {"opts": [{"name": "alpha", "label": "Alpha"}]}
        variables = extract_variables(rows, choices)
        response = [{"opts[zzzzz]": "Yes"}]  # "zzzzz" matches nothing
        with pytest.warns(UserWarning, match="did not match any choice code"):
            result = normalize_responses(variables, response)
        assert result[0]["opts"] == "zzzzz"  # raw key preserved

    def test_select_multiple_multiple_selected(self, lime_variables):
        """Multiple "Yes" sub-columns → space-separated codes."""
        row = {
            "bereiche[holz]": "Yes", "bereiche[metal]": "Yes",
            "bereiche[texti]": "No", "bereiche[digit]": "No",
        }
        result = normalize_responses(lime_variables, [row])
        selected = result[0]["bereiche"].split()
        assert "holz" in selected
        assert "metall" in selected
        assert len(selected) == 2

    def test_metadata_fields_not_in_output(self, lime_variables, lime_responses):
        """LimeSurvey metadata fields (id, submitdate, etc.) are not present."""
        result = normalize_responses(lime_variables, lime_responses)
        for meta in ("id", "submitdate", "startdate", "datestamp", "seed"):
            assert meta not in result[0]

    def test_keyed_by_data_key(self, lime_variables, lime_responses):
        """Output is keyed by _data_key, which equals name when no group."""
        result = normalize_responses(lime_variables, lime_responses)
        by_name = {v["name"]: v["_data_key"] for v in lime_variables}
        for var_name, data_key in by_name.items():
            assert data_key in result[0]

    def test_missing_variable_in_response_gives_empty_string(self, lime_variables):
        """Variable not present in the response row → empty string, not KeyError."""
        result = normalize_responses(lime_variables, [{}])
        assert result[0]["haeufigkeit"] == ""
        assert result[0]["bereiche"] == ""

    def test_multiple_rows(self, lime_variables):
        rows = [
            {"haeufigkeit": "Once", "bereiche[holz]": "Yes", "bereiche[metal]": "No",
             "bereiche[texti]": "No", "bereiche[digit]": "No", "berufpost": "1",
             "ammeistengebracht": "great", "npsscore": "8"},
            {"haeufigkeit": "Sometimes", "bereiche[holz]": "No", "bereiche[metal]": "Yes",
             "bereiche[texti]": "No", "bereiche[digit]": "No", "berufpost": "5",
             "ammeistengebracht": "also great", "npsscore": "10"},
        ]
        result = normalize_responses(lime_variables, rows)
        assert len(result) == 2
        assert result[0]["haeufigkeit"] == "Once"
        assert result[1]["haeufigkeit"] == "Sometimes"
        assert "holz" in result[0]["bereiche"].split()
        assert "metall" in result[1]["bereiche"].split()

    def test_empty_responses(self, lime_variables):
        assert normalize_responses(lime_variables, []) == []


