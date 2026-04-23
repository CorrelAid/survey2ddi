"""XLSForm → DDI equivalence between survey2ddi and qwacback.

For every answer type qwacback supports (see qwacback/internal/examples/examples.go),
we post the same XLSForm through both converters and compare the DDI shape.
All supported types are expected to match byte-equivalent shapes.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest

from kobo2ddi.ddi_xml import build_ddi_xml

pytestmark = pytest.mark.integration


# --- XML shape helpers -----------------------------------------------------


def _tag(el: ET.Element) -> str:
    return el.tag.split("}", 1)[-1] if "}" in el.tag else el.tag


def _find_data_dscr(xml_str: str) -> ET.Element:
    """Return a <dataDscr>-equivalent element.

    survey2ddi always wraps in <codeBook>/<dataDscr>. qwacback returns a bare
    <var> or <varGrp> when there's only one, or <dataDscr> otherwise. We
    synthesize a container in the bare case so callers can iterate uniformly.
    """
    root = ET.fromstring(xml_str)
    if _tag(root) == "dataDscr":
        return root
    if _tag(root) in ("var", "varGrp"):
        container = ET.Element("dataDscr")
        container.append(root)
        return container
    for e in root.iter():
        if _tag(e) == "dataDscr":
            return e
    raise AssertionError(f"no <dataDscr>/<var>/<varGrp> root; got <{_tag(root)}>")


def _child(el: ET.Element, name: str) -> ET.Element | None:
    for c in el:
        if _tag(c) == name:
            return c
    return None


def _children(el: ET.Element, name: str) -> list[ET.Element]:
    return [c for c in el if _tag(c) == name]


def _text(el: ET.Element | None) -> str | None:
    if el is None or el.text is None:
        return None
    return el.text.strip() or None


def _var_shape(v: ET.Element) -> dict:
    qstn = _child(v, "qstn")
    vfmt = _child(v, "varFormat")
    concept = _child(v, "concept")
    cats = tuple(
        (_text(_child(c, "catValu")), _text(_child(c, "labl")))
        for c in _children(v, "catgry")
    )
    return {
        "name": v.get("name"),
        "ID": v.get("ID"),
        "intrvl": v.get("intrvl"),
        "nature": v.get("nature"),
        "responseDomainType": qstn.get("responseDomainType") if qstn is not None else None,
        "preQTxt": _text(_child(qstn, "preQTxt")) if qstn is not None else None,
        "qstnLit": _text(_child(qstn, "qstnLit")) if qstn is not None else None,
        "varFormat_type": vfmt.get("type") if vfmt is not None else None,
        "varFormat_schema": vfmt.get("schema") if vfmt is not None else None,
        "concept": _text(concept),
        "concept_vocab": concept.get("vocab") if concept is not None else None,
        "catgry": cats,
    }


def _grp_shape(g: ET.Element) -> dict:
    return {
        "name": g.get("name"),
        "ID": g.get("ID"),
        "type": g.get("type"),
        "var": tuple((g.get("var") or "").split()),
        "varGrp_ref": tuple((g.get("varGrp") or "").split()),
        "concept": _text(_child(g, "concept")),
        "txt": _text(_child(g, "txt")),
    }


def _shape(xml_str: str) -> tuple[dict, dict]:
    dd = _find_data_dscr(xml_str)
    vars_ = {v.get("name"): _var_shape(v) for v in _children(dd, "var")}
    grps = {g.get("name"): _grp_shape(g) for g in _children(dd, "varGrp")}
    return vars_, grps


def _both(qwacback_convert_xlsform, survey, choices):
    ours = build_ddi_xml("T", survey, choices, {}, [])
    theirs = qwacback_convert_xlsform(survey, choices, {})
    return _shape(ours), _shape(theirs)


# --- Equivalent types -------------------------------------------------------


EQUIVALENT_TYPES = [
    pytest.param(
        "single_choice",
        [{"type": "select_one bildung", "name": "bildung", "label": "Bildungsgrad", "required": "false", "appearance": None}],
        {"bildung": [
            {"name": "1", "label": "Kein Abschluss"},
            {"name": "2", "label": "Abitur"},
            {"name": "3", "label": "Hochschulabschluss"},
        ]},
        id="single_choice",
    ),
    pytest.param(
        "multiple_choice",
        [{"type": "select_multiple tage", "name": "wochenende", "label": "Wochenendtage", "required": "false", "appearance": None}],
        {"tage": [
            {"name": "sa", "label": "Samstag"},
            {"name": "so", "label": "Sonntag"},
        ]},
        id="multiple_choice",
    ),
    pytest.param(
        "single_choice_other",
        [
            {"type": "select_one quelle", "name": "src", "label": "Source", "required": "false", "appearance": None},
            {"type": "text", "name": "src_other", "label": "Other", "required": "false", "appearance": None},
        ],
        {"quelle": [
            {"name": "a", "label": "A"},
            {"name": "other", "label": "Other"},
        ]},
        id="single_choice_other",
    ),
    pytest.param(
        "multiple_choice_other",
        [
            {"type": "select_multiple dev", "name": "own", "label": "Own", "required": "false", "appearance": None},
            {"type": "text", "name": "own_other", "label": "Other", "required": "false", "appearance": None},
        ],
        {"dev": [
            {"name": "a", "label": "A"},
            {"name": "other", "label": "Other"},
        ]},
        id="multiple_choice_other",
    ),
    pytest.param(
        "grid",
        [
            {"type": "begin_group", "name": "trust", "label": "Trust", "required": "false", "appearance": "table-list"},
            {"type": "select_one s5", "name": "trust_a", "label": "A", "required": "false", "appearance": None},
            {"type": "end_group", "name": None, "label": None, "required": None, "appearance": None},
        ],
        {"s5": [
            {"name": "1", "label": "One"},
            {"name": "2", "label": "Two"},
        ]},
        id="grid",
    ),
    pytest.param(
        "integer",
        [{"type": "integer", "name": "alter", "label": "Alter", "required": "false", "appearance": None}],
        {},
        id="integer",
    ),
    pytest.param(
        "decimal",
        [{"type": "decimal", "name": "rating", "label": "Rating", "required": "false", "appearance": None}],
        {},
        id="decimal",
    ),
    pytest.param(
        "range",
        [{"type": "range", "name": "score", "label": "Score", "required": "false", "appearance": None}],
        {},
        id="range",
    ),
    pytest.param(
        "date",
        [{"type": "date", "name": "besuch", "label": "Besuchsdatum", "required": "false", "appearance": None}],
        {},
        id="date",
    ),
    pytest.param(
        "text",
        [{"type": "text", "name": "anmerkung", "label": "Anmerkungen", "required": "false", "appearance": None}],
        {},
        id="text",
    ),
    pytest.param(
        "note",
        [{"type": "note", "name": "thanks", "label": "Thank you", "required": "false", "appearance": None}],
        {},
        id="note",
    ),
    pytest.param(
        "calculate",
        [{"type": "calculate", "name": "calc", "label": "Calc", "required": "false", "appearance": None}],
        {},
        id="calculate",
    ),
    pytest.param(
        "single_choice_long_list",
        [{"type": "select_one_from_file iso_3166_1.csv", "name": "country", "label": "Country", "required": "false", "appearance": None}],
        {},
        id="single_choice_long_list",
    ),
    pytest.param(
        "multiple_choice_long_list",
        [{"type": "select_multiple_from_file iso_3166_1.csv", "name": "visited", "label": "Visited", "required": "false", "appearance": None}],
        {},
        id="multiple_choice_long_list",
    ),
    pytest.param(
        "section",
        # Plain begin_group (no table-list appearance) — both converters drop
        # the wrapper and emit only the member vars at the top level.
        [
            {"type": "begin_group", "name": "section1", "label": "Section 1", "required": "false", "appearance": None},
            {"type": "text", "name": "q1", "label": "Q1", "required": "false", "appearance": None},
            {"type": "end_group", "name": None, "label": None, "required": None, "appearance": None},
        ],
        {},
        id="section",
    ),
]


class TestXlsformToDdiEquivalence:
    """survey2ddi and qwacback produce the same DDI for every supported type."""

    @pytest.mark.parametrize("label,survey,choices", EQUIVALENT_TYPES)
    def test_type_equivalence(self, qwacback_convert_xlsform, label, survey, choices):
        (our_vars, our_grps), (their_vars, their_grps) = _both(
            qwacback_convert_xlsform, survey, choices,
        )
        assert our_vars == their_vars, f"{label}: var shape differs"
        assert our_grps == their_grps, f"{label}: varGrp shape differs"
