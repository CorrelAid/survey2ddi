"""Tests for kobo2ddi.data — canonical row matcher + DDI-aligned CSV."""

import csv
import io

from kobo2ddi.data import (
    build_data_csv,
    get_canonical_columns,
    to_canonical_rows,
)
from kobo2ddi.transform import extract_variables


# ---------------------------------------------------------------------------
# get_canonical_columns
# ---------------------------------------------------------------------------


class TestGetCanonicalColumns:
    def test_simple_vars_become_one_col_each(self, survey_rows, choices_by_list):
        variables = extract_variables(survey_rows, choices_by_list)
        cols = get_canonical_columns(variables)
        assert "full_name" in cols
        assert "age" in cols
        assert "gender" in cols
        assert "satisfaction" in cols

    def test_select_multiple_expanded(self, survey_rows, choices_by_list):
        """``hobbies`` (select_multiple, 3 choices) → 3 binary cols, no ``hobbies`` col."""
        variables = extract_variables(survey_rows, choices_by_list)
        cols = get_canonical_columns(variables)
        assert "hobbies" not in cols
        assert "hobbies_sports" in cols
        assert "hobbies_music" in cols
        assert "hobbies_reading" in cols

    def test_choice_order_preserved(self, survey_rows, choices_by_list):
        variables = extract_variables(survey_rows, choices_by_list)
        cols = get_canonical_columns(variables)
        # Choices were defined sports → music → reading
        i_sports = cols.index("hobbies_sports")
        i_music = cols.index("hobbies_music")
        i_reading = cols.index("hobbies_reading")
        assert i_sports < i_music < i_reading

    def test_empty_variables(self):
        assert get_canonical_columns([]) == []


# ---------------------------------------------------------------------------
# to_canonical_rows
# ---------------------------------------------------------------------------


class TestToCanonicalRows:
    def test_simple_field_passthrough(self, survey_rows, choices_by_list, submissions):
        variables = extract_variables(survey_rows, choices_by_list)
        rows = to_canonical_rows(variables, submissions)
        # Alice, age 30
        assert rows[0]["full_name"] == "Alice"
        assert rows[0]["age"] == "30"

    def test_select_multiple_binary_expansion(self, survey_rows, choices_by_list, submissions):
        """Alice ticked 'sports music' → those cols get '1', 'reading' gets '0'."""
        variables = extract_variables(survey_rows, choices_by_list)
        rows = to_canonical_rows(variables, submissions)
        assert rows[0]["hobbies_sports"] == "1"
        assert rows[0]["hobbies_music"] == "1"
        assert rows[0]["hobbies_reading"] == "0"
        # Bob ticked 'reading' only
        assert rows[1]["hobbies_sports"] == "0"
        assert rows[1]["hobbies_music"] == "0"
        assert rows[1]["hobbies_reading"] == "1"

    def test_missing_value_becomes_empty_string(self, survey_rows, choices_by_list):
        variables = extract_variables(survey_rows, choices_by_list)
        rows = to_canonical_rows(variables, [{}])
        # Every column present, simple cols default to ""
        assert rows[0]["full_name"] == ""
        # Multi-select with no value → all 0s
        assert rows[0]["hobbies_sports"] == "0"

    def test_missing_select_multiple_all_zero(self, survey_rows, choices_by_list):
        variables = extract_variables(survey_rows, choices_by_list)
        rows = to_canonical_rows(variables, [{"demo/full_name": "x"}])
        for c in ("hobbies_sports", "hobbies_music", "hobbies_reading"):
            assert rows[0][c] == "0"

    def test_empty_neutral_rows(self, survey_rows, choices_by_list):
        variables = extract_variables(survey_rows, choices_by_list)
        assert to_canonical_rows(variables, []) == []


# ---------------------------------------------------------------------------
# build_data_csv
# ---------------------------------------------------------------------------


class TestBuildDataCsv:
    def test_header_first_line(self, survey_rows, choices_by_list, submissions):
        variables = extract_variables(survey_rows, choices_by_list)
        csv_str = build_data_csv(variables, submissions)
        first_line = csv_str.splitlines()[0]
        cols = first_line.split(",")
        # Canonical cols == header
        assert cols == get_canonical_columns(variables)

    def test_row_count_matches_input(self, survey_rows, choices_by_list, submissions):
        variables = extract_variables(survey_rows, choices_by_list)
        csv_str = build_data_csv(variables, submissions)
        rows = list(csv.DictReader(io.StringIO(csv_str)))
        assert len(rows) == len(submissions)

    def test_crlf_line_endings(self, survey_rows, choices_by_list, submissions):
        """RFC 4180 mandates CRLF."""
        variables = extract_variables(survey_rows, choices_by_list)
        csv_str = build_data_csv(variables, submissions)
        assert "\r\n" in csv_str
        # And no bare \n that isn't preceded by \r
        assert csv_str.replace("\r\n", "").count("\n") == 0

    def test_quoting_for_commas_and_quotes(self):
        """Free-text values containing , or " must be RFC 4180 quoted."""
        variables = [{
            "name": "comment", "type": "text", "_data_key": "comment", "choices": [],
        }]
        rows = [{"comment": 'a, "b" and c'}]
        csv_str = build_data_csv(variables, rows)
        # csv.DictReader must round-trip the value untouched.
        out = list(csv.DictReader(io.StringIO(csv_str)))
        assert out[0]["comment"] == 'a, "b" and c'

    def test_empty_submissions_emits_header_only(self, survey_rows, choices_by_list):
        variables = extract_variables(survey_rows, choices_by_list)
        csv_str = build_data_csv(variables, [])
        # Exactly one terminator after header, no rows
        assert csv_str.endswith("\r\n")
        assert csv_str.count("\r\n") == 1
