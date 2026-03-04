"""Transform LimeSurvey data into the DDI-adjacent xlsx and XML formats."""

import warnings
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
        """Return the XLSForm choice code that matches the LimeSurvey bracket *subkey*.

        LimeSurvey truncates option codes to 5 characters in bracket keys, so
        prefix matching is used to recover the original code.  Exact match is
        preferred; a single unambiguous prefix match is accepted.

        Raises ValueError if multiple choices share the same truncated prefix
        (ambiguous — would silently produce wrong data).

        Falls back to the raw *subkey* with a warning when no choice matches,
        which can happen if LimeSurvey uses internal codes not derived from the
        XLSForm choice names.
        """
        # Exact match first (no truncation occurred, or code is ≤5 chars)
        exact = [c["name"] for c in choices if c["name"] == subkey]
        if exact:
            return exact[0]

        # Prefix match: LimeSurvey truncated the code
        prefix_matches = [
            c["name"] for c in choices
            if c["name"].startswith(subkey) or subkey.startswith(c["name"])
        ]
        if len(prefix_matches) == 1:
            return prefix_matches[0]
        if len(prefix_matches) > 1:
            raise ValueError(
                f"Ambiguous select_multiple bracket key {subkey!r} matches multiple "
                f"choice codes: {prefix_matches}. Choice codes must be unique in "
                "their first 5 characters for LimeSurvey export to be unambiguous."
            )

        # No match — LimeSurvey may be using internal codes unrelated to XLSForm names.
        # Return the raw key so data is preserved, but warn the user.
        warnings.warn(
            f"select_multiple bracket key {subkey!r} did not match any XLSForm "
            "choice code. Using raw key. LimeSurvey may be using internal answer "
            "codes not derived from the XLSForm choice names — check your form.xlsx.",
            stacklevel=4,
        )
        return subkey

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
