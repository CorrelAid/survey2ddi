"""Transform LimeSurvey data into the DDI-adjacent xlsx and XML formats."""

from pathlib import Path

from openpyxl import Workbook

from kobo2ddi.ddi_xml import build_ddi_xml as _build_ddi_xml
from kobo2ddi.transform import (
    build_workbook as _build_workbook,
    extract_variables,
    parse_xlsform,
)


def _norm(name: str) -> str:
    """Remove underscores and lowercase — mirrors LimeSurvey's export behaviour."""
    return name.replace("_", "").lower()


def normalize_responses(
    variables: list[dict],
    responses: list[dict],
) -> list[dict]:
    """Re-key LimeSurvey response dicts to use XLSForm variable names.

    Handles two LimeSurvey export quirks:
    - Underscore stripping: ``beruf_post`` becomes ``berufpost`` in exports.
    - select_multiple sub-columns: ``bereiche[holz]="Yes"`` — collected into a
      space-separated string of selected choice codes (``"holz"``).
      LimeSurvey truncates option codes to 5 characters in bracket keys
      (``metall`` → ``metal``), so prefix matching is used to recover the
      original code from the XLSForm choices list.

    Returns a list of dicts keyed by ``v["_data_key"]``, ready for
    ``kobo2ddi.transform.build_workbook``.
    """
    def _match_choice(subkey: str, choices: list[dict]) -> str:
        """Return the full choice code whose name prefix-matches *subkey*."""
        for c in choices:
            code = c["name"]
            # LimeSurvey truncates to 5 chars; one is a prefix of the other
            if code == subkey or code.startswith(subkey) or subkey.startswith(code):
                return code
        return subkey  # fall back to the raw subkey

    result = []
    for row in responses:
        # Separate simple columns from select_multiple sub-columns
        multi_cols: dict[str, dict[str, str]] = {}   # norm_base → {subkey: value}
        simple_cols: dict[str, str] = {}

        for key, value in row.items():
            if "[" in key:
                base, rest = key.split("[", 1)
                subkey = rest.rstrip("]")
                multi_cols.setdefault(_norm(base), {})[subkey] = str(value or "")
            else:
                simple_cols[_norm(key)] = str(value or "")

        normalized: dict[str, str] = {}
        for v in variables:
            data_key = v["_data_key"]   # "group/name" or just "name"
            norm_name = _norm(v["name"])

            if v["type"] == "select_multiple":
                subs = multi_cols.get(norm_name, {})
                selected = [
                    _match_choice(subkey, v["choices"])
                    for subkey, val in subs.items()
                    if val.lower() in ("yes", "y", "1", "true")
                ]
                normalized[data_key] = " ".join(selected)
            else:
                normalized[data_key] = simple_cols.get(norm_name, "")

        result.append(normalized)

    return result


def build_workbook(
    survey_title: str,
    form_path: Path,
    responses: list[dict],
) -> Workbook:
    """Build the DDI-adjacent xlsx workbook for a LimeSurvey survey."""
    survey_rows, choices_by_list, settings = parse_xlsform(form_path)
    variables = extract_variables(survey_rows, choices_by_list)
    normalized = normalize_responses(variables, responses)
    return _build_workbook(
        asset_name=survey_title,
        survey_rows=survey_rows,
        choices_by_list=choices_by_list,
        settings=settings,
        submissions=normalized,
        source="limesurvey",
    )


def build_ddi_xml(
    survey_title: str,
    form_path: Path,
    responses: list[dict],
) -> str:
    """Build a DDI-Codebook 2.5 XML string for a LimeSurvey survey."""
    survey_rows, choices_by_list, settings = parse_xlsform(form_path)
    variables = extract_variables(survey_rows, choices_by_list)
    normalized = normalize_responses(variables, responses)
    return _build_ddi_xml(
        asset_name=survey_title,
        survey_rows=survey_rows,
        choices_by_list=choices_by_list,
        settings=settings,
        submissions=normalized,
    )
