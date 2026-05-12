"""Parse a LimeSurvey survey-structure TSV export into the same shape as ``parse_xlsform``.

LimeSurvey's TSV uses 14 columns and row classes ``S``/``SL``/``G``/``Q``/``SQ``/``A``.
This module flattens it to ``(survey_rows, choices_by_list, settings)`` so the
existing ``extract_variables`` / ``build_workbook`` / ``build_ddi_xml`` pipelines
keep working unchanged.
"""

from __future__ import annotations

import csv
from pathlib import Path

LS_COLUMNS = [
    "class", "type/scale", "name", "relevance", "text", "help", "language",
    "validation", "em_validation_q", "mandatory", "other", "default",
    "same_default", "hidden",
]

# LS question type code → standardized XLSForm-style base type.
# Codes that need a list name are filled with ``f"{base} {list_name}"`` later.
TYPE_MAP = {
    "S": "text",
    "T": "text",
    "N": "decimal",
    "D": "date",
    "L": "select_one",
    "!": "select_one",
    "M": "select_multiple",
    "R": "rank",
    "X": "note",
    "*": "calculate",
    "Y": "select_one",
    "G": "select_one",
    "F": "begin_group",  # matrix; opens a table-list group
}

YES_NO_CHOICES = [{"name": "Y", "label": "Yes"}, {"name": "N", "label": "No"}]
GENDER_CHOICES = [{"name": "M", "label": "Male"}, {"name": "F", "label": "Female"}]


def parse_lstsv(path: Path) -> tuple[list[dict], dict[str, list[dict]], dict]:
    """Parse a LimeSurvey TSV file. See module docstring for return shape."""
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        rows = list(reader)

    primary_lang = _detect_primary_language(rows)
    settings = _build_settings(rows, primary_lang)

    survey_rows: list[dict] = []
    choices_by_list: dict[str, list[dict]] = {}

    # Parser state
    current_question: str | None = None  # last opened Q (for choice/SQ attachment)
    current_list: str | None = None      # list name choices currently flow into
    current_q_type: str | None = None    # LS code of currently open Q
    in_outer_group = False               # whether a G group is open
    in_matrix = False                    # whether F's table-list group is open

    for row in rows:
        cls = (row.get("class") or "").strip()
        lang = (row.get("language") or "").strip()

        # Drop secondary-language rows (only A/SQ/SL/Q/G have language).
        if lang and primary_lang and lang != primary_lang:
            continue

        if cls == "S" or cls == "SL":
            continue  # already absorbed into settings

        if cls == "G":
            if in_matrix:
                survey_rows.append(_end_group_row())
                in_matrix = False
            if in_outer_group:
                survey_rows.append(_end_group_row())
            survey_rows.append({
                "type": "begin_group",
                "name": (row.get("name") or "").strip(),
                "label": (row.get("text") or "").strip(),
                "required": "false",
                "appearance": None,
            })
            in_outer_group = True
            current_question = None
            current_list = None
            current_q_type = None
            continue

        if cls == "Q":
            # Close any open matrix group before starting next Q (unless this Q
            # is the matrix header itself, which never happens — F is always
            # the matrix Q so closure is at next Q after F).
            if in_matrix:
                survey_rows.append(_end_group_row())
                in_matrix = False

            ls_type = (row.get("type/scale") or "").strip()
            qname = (row.get("name") or "").strip()
            label = (row.get("text") or "").strip()
            required = "true" if (row.get("mandatory") or "").strip().upper() == "Y" else "false"

            current_question = qname
            current_q_type = ls_type
            current_list = None

            if ls_type == "F":
                # Matrix: open a table-list group; subquestions emit as
                # select_one rows inside; answers feed the shared scale list.
                list_name = f"{qname}_list"
                current_list = list_name
                choices_by_list.setdefault(list_name, [])
                survey_rows.append({
                    "type": "begin_group",
                    "name": qname,
                    "label": label,
                    "required": required,
                    "appearance": "table-list",
                })
                in_matrix = True
                continue

            base = TYPE_MAP.get(ls_type)
            if base is None:
                # Unknown LS type — treat as text so pipeline keeps going.
                base = "text"

            if base in ("select_one", "select_multiple", "rank"):
                list_name = f"{qname}_list"
                current_list = list_name
                if ls_type == "Y":
                    choices_by_list[list_name] = list(YES_NO_CHOICES)
                elif ls_type == "G":
                    choices_by_list[list_name] = list(GENDER_CHOICES)
                else:
                    choices_by_list.setdefault(list_name, [])
                survey_rows.append({
                    "type": f"{base} {list_name}",
                    "name": qname,
                    "label": label,
                    "required": required,
                    "appearance": None,
                })
            else:
                survey_rows.append({
                    "type": base,
                    "name": qname,
                    "label": label,
                    "required": required,
                    "appearance": None,
                })
            continue

        if cls == "SQ":
            sqname = (row.get("name") or "").strip()
            sqlabel = (row.get("text") or "").strip()
            if in_matrix and current_list:
                # Subquestion in a matrix → its own select_one row sharing the
                # matrix's scale list.
                survey_rows.append({
                    "type": f"select_one {current_list}",
                    "name": sqname,
                    "label": sqlabel,
                    "required": "false",
                    "appearance": None,
                })
            elif current_q_type == "M" and current_list:
                # Multi-select subquestions become entries in the choice list.
                choices_by_list.setdefault(current_list, []).append({
                    "name": sqname,
                    "label": sqlabel,
                })
            # else: orphan SQ — drop silently.
            continue

        if cls == "A":
            aname = (row.get("name") or "").strip()
            alabel = (row.get("text") or "").strip()
            if current_list:
                choices_by_list.setdefault(current_list, []).append({
                    "name": aname,
                    "label": alabel,
                })
            continue

        # Unknown class — ignore.

    # Close any still-open groups at EOF.
    if in_matrix:
        survey_rows.append(_end_group_row())
    if in_outer_group:
        survey_rows.append(_end_group_row())

    return survey_rows, choices_by_list, settings


def _detect_primary_language(rows: list[dict]) -> str:
    """Primary language is given by the ``S language`` row's ``text`` column."""
    for row in rows:
        if (row.get("class") or "").strip() == "S" and (row.get("name") or "").strip() == "language":
            return (row.get("text") or "").strip()
    return ""


def _build_settings(rows: list[dict], primary_lang: str) -> dict:
    title = ""
    for row in rows:
        if (row.get("class") or "").strip() == "SL" and (row.get("name") or "").strip() == "surveyls_title":
            lang = (row.get("language") or "").strip()
            if not primary_lang or lang == primary_lang:
                title = (row.get("text") or "").strip()
                break
    return {
        "id_string": title or "limesurvey",
        "version": "1.0",
        "default_language": primary_lang,
    }


def _end_group_row() -> dict:
    return {
        "type": "end_group",
        "name": None,
        "label": None,
        "required": None,
        "appearance": None,
    }
