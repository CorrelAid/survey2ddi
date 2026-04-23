"""Generate DDI-Codebook 2.5 XML from parsed survey data.

Produces XML compliant with qwacback's XSD + Schematron validation:
- ``concept`` instead of ``labl`` on ``<var>`` and ``<varGrp>``
- ``responseDomainType`` on every ``<qstn>``
- ``select_multiple`` expanded into ``<varGrp type="multipleResp">`` + binary vars
- Grid groups (``appearance="table-list"``) as ``<varGrp type="grid">``
- No ``type="section"`` groups
"""

from collections import defaultdict
from datetime import date
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom.minidom import parseString

from kobo2ddi.transform import extract_variables

NS = "ddi:codebook:2_5"
XSI = "http://www.w3.org/2001/XMLSchema-instance"
SCHEMA_LOC = "ddi:codebook:2_5 https://ddialliance.org/Specification/DDI-Codebook/2.5/XMLSchema/codebook.xsd"

# Type → (intrvl attribute, varFormat/@type)
DDI_TYPE_MAP = {
    "select_one":            ("discrete",  "numeric"),
    "select_multiple":       ("discrete",  "numeric"),
    "select_one_from_file":  ("discrete",  "numeric"),
    "select_multiple_from_file": ("discrete", "numeric"),
    "rank":                  ("discrete",  "numeric"),
    "integer":               ("contin",    "numeric"),
    "decimal":               ("contin",    "numeric"),
    "range":                 ("contin",    "numeric"),
    "calculate":             ("discrete",  "character"),
    "string":                ("discrete",  "character"),
    "note":                  ("discrete",  "character"),
    "date":                  ("discrete",  "character"),
    "time":                  ("discrete",  "character"),
    "datetime":              ("discrete",  "character"),
    "acknowledge":           ("discrete",  "numeric"),
    "hidden":                ("discrete",  "character"),
}

# Type → responseDomainType for <qstn>
RESPONSE_DOMAIN_MAP = {
    "select_one":            "category",
    "select_multiple":       "multiple",
    "select_one_from_file":  "category",
    "select_multiple_from_file": "multiple",
    "rank":                  "category",
    "integer":               "numeric",
    "decimal":               "numeric",
    "range":                 "numeric",
    "calculate":             "text",
    "string":                "text",
    "note":                  "text",
    "date":                  "text",
    "time":                  "text",
    "datetime":              "text",
    "acknowledge":           "text",
    "hidden":                "text",
}


def _make_var_id(name: str) -> str:
    return f"V_{name}"


def _make_grp_id(name: str) -> str:
    return f"VG_{name}"


def _is_grid_group(variables: list[dict], group_name: str) -> bool:
    """A group is a grid if its appearance is table-list."""
    for v in variables:
        if v["group"] == group_name and v.get("group_appearance"):
            return "table-list" in v["group_appearance"]
    return False


def _get_group_label(variables: list[dict], group_name: str) -> str:
    """Get the label of the group from its member variables."""
    for v in variables:
        if v["group"] == group_name and v.get("group_label"):
            return v["group_label"]
    return group_name


def _add_var_element(
    parent: Element,
    var_id: str,
    name: str,
    label: str,
    var_type: str,
    choices: list[dict],
    vocab: str = "",
    pre_q_txt: str = "",
) -> Element:
    """Add a single <var> element with qwacback-compliant structure.

    Element order: qstn → catgry* → concept → varFormat.
    For ``*_from_file`` types, pass ``vocab`` (filename without extension) —
    no ``<catgry>`` is emitted and ``<concept>`` carries ``@vocab``.
    Pass ``pre_q_txt`` for grid members so the shared question stem is
    emitted as ``<preQTxt>`` (qwacback's canonical convention).
    """
    intrvl, fmt_type = DDI_TYPE_MAP.get(var_type, ("discrete", "character"))
    resp_domain = RESPONSE_DOMAIN_MAP.get(var_type, "text")

    var_el = SubElement(parent, "var", ID=var_id, name=name, intrvl=intrvl)

    if label:
        qstn = SubElement(var_el, "qstn", responseDomainType=resp_domain)
        if pre_q_txt:
            SubElement(qstn, "preQTxt").text = pre_q_txt
        SubElement(qstn, "qstnLit").text = label

    # No inline <catgry> for external-vocab types — the vocab reference replaces them.
    if not vocab:
        for choice in choices:
            catgry = SubElement(var_el, "catgry")
            SubElement(catgry, "catValu").text = choice["name"]
            SubElement(catgry, "labl").text = choice["label"]

    concept_attrs = {"vocab": vocab} if vocab else {}
    SubElement(var_el, "concept", **concept_attrs).text = label

    SubElement(var_el, "varFormat", type=fmt_type, schema="other")

    return var_el


def _detect_other_patterns(variables: list[dict]) -> dict[str, dict]:
    """Detect the semi-open (`_other`) pattern.

    A ``_other`` pattern exists when a ``text`` variable named ``<base>_other``
    follows a ``select_one``/``select_multiple`` variable ``<base>`` that has a
    choice with ``name == "other"``. qwacback emits such pairs as a parent
    ``<varGrp type="other">``; we mirror that shape.

    Returns ``{base_name: {"base": <var>, "other_var": <var>, "is_multi": bool}}``.
    """
    by_name = {v["name"]: v for v in variables}
    patterns: dict[str, dict] = {}
    for v in variables:
        if v["type"] != "string" or not v["name"].endswith("_other"):
            continue
        base_name = v["name"][: -len("_other")]
        base = by_name.get(base_name)
        if not base or base["type"] not in ("select_one", "select_multiple"):
            continue
        if not any(c.get("name") == "other" for c in base.get("choices", [])):
            continue
        patterns[base_name] = {
            "base": base,
            "other_var": v,
            "is_multi": base["type"] == "select_multiple",
        }
    return patterns


def _emit_other_pattern(data_dscr: Element, p: dict) -> None:
    """Emit the parent <varGrp type="other"> (+ child multipleResp for multi)."""
    base = p["base"]
    other_var = p["other_var"]
    label = base["label"]
    base_name = base["name"]

    if p["is_multi"]:
        # Child group holds the non-"other" binary vars.
        non_other = [c for c in base["choices"] if c.get("name") != "other"]
        child_name = f"{base_name}_choices"
        child_id = _make_grp_id(child_name)
        child_members = " ".join(
            _make_var_id(f"{base_name}_{c['name']}") for c in non_other
        )

        parent_el = SubElement(
            data_dscr, "varGrp",
            ID=_make_grp_id(base_name),
            name=base_name,
            type="other",
            var=_make_var_id(other_var["name"]),
            varGrp=child_id,
        )
        SubElement(parent_el, "txt").text = label
        SubElement(parent_el, "concept").text = label

        child_el = SubElement(
            data_dscr, "varGrp",
            ID=child_id,
            name=child_name,
            type="multipleResp",
            var=child_members,
        )
        SubElement(child_el, "txt").text = label
        SubElement(child_el, "concept").text = label
    else:
        # Single-choice: parent references the base var AND the other var.
        parent_el = SubElement(
            data_dscr, "varGrp",
            ID=_make_grp_id(base_name),
            name=base_name,
            type="other",
            var=" ".join([
                _make_var_id(base_name),
                _make_var_id(other_var["name"]),
            ]),
        )
        SubElement(parent_el, "txt").text = label
        SubElement(parent_el, "concept").text = label


def _emit_other_pattern_vars(data_dscr: Element, p: dict) -> None:
    """Emit the <var> elements associated with an _other pattern."""
    base = p["base"]
    other_var = p["other_var"]
    base_name = base["name"]

    if p["is_multi"]:
        # Binary vars for non-"other" choices only.
        for choice in base["choices"]:
            if choice.get("name") == "other":
                continue
            _add_binary_var(
                data_dscr,
                var_id=_make_var_id(f"{base_name}_{choice['name']}"),
                name=f"{base_name}_{choice['name']}",
                question_label=base["label"],
                choice_label=choice["label"],
            )
    else:
        # Base select_one retains all categories (including "other").
        _add_var_element(
            data_dscr,
            var_id=_make_var_id(base_name),
            name=base_name,
            label=base["label"],
            var_type=base["type"],
            choices=base["choices"],
        )

    # The _other text follow-up is always a standalone text var.
    _add_var_element(
        data_dscr,
        var_id=_make_var_id(other_var["name"]),
        name=other_var["name"],
        label=other_var["label"],
        var_type=other_var["type"],
        choices=[],
    )


def _add_binary_var(
    parent: Element,
    var_id: str,
    name: str,
    question_label: str,
    choice_label: str,
) -> Element:
    """Add a binary 0/1 <var> for a select_multiple option."""
    var_el = SubElement(parent, "var", ID=var_id, name=name, intrvl="discrete")

    qstn = SubElement(var_el, "qstn", responseDomainType="multiple")
    SubElement(qstn, "preQTxt").text = question_label
    SubElement(qstn, "qstnLit").text = choice_label

    # Binary categories (no labl — qwacback convention)
    for val in ("0", "1"):
        catgry = SubElement(var_el, "catgry")
        SubElement(catgry, "catValu").text = val

    SubElement(var_el, "concept").text = f"{question_label}: {choice_label}"
    SubElement(var_el, "varFormat", type="numeric", schema="other")

    return var_el


def build_ddi_xml(
    asset_name: str,
    survey_rows: list[dict],
    choices_by_list: dict[str, list[dict]],
    settings: dict,
    submissions: list[dict],
) -> str:
    """Build a DDI-Codebook 2.5 XML string from parsed survey data.

    Same source-agnostic signature as ``build_workbook``.
    """
    variables = extract_variables(survey_rows, choices_by_list)

    root = Element("codeBook")
    root.set("xmlns", NS)
    root.set("xmlns:xsi", XSI)
    root.set("xsi:schemaLocation", SCHEMA_LOC)
    root.set("version", "2.5")

    # --- stdyDscr ---
    stdy = SubElement(root, "stdyDscr")
    citation = SubElement(stdy, "citation")

    titl_stmt = SubElement(citation, "titlStmt")
    SubElement(titl_stmt, "titl").text = asset_name
    study_id = settings.get("id_string", "")
    if study_id:
        SubElement(titl_stmt, "IDNo").text = str(study_id)

    prod_stmt = SubElement(citation, "prodStmt")
    SubElement(prod_stmt, "prodDate", date=date.today().isoformat()).text = (
        date.today().isoformat()
    )

    ver = settings.get("version", "")
    if ver:
        ver_stmt = SubElement(citation, "verStmt")
        SubElement(ver_stmt, "version").text = str(ver)

    # --- dataDscr ---
    data_dscr = SubElement(root, "dataDscr")

    # Detect _other (semi-open) patterns: a text var named <base>_other paired
    # with a base select_one/select_multiple that has an "other" category.
    other_patterns = _detect_other_patterns(variables)
    base_names_in_other = {p["base"]["name"] for p in other_patterns.values()}
    other_var_names = {p["other_var"]["name"] for p in other_patterns.values()}

    # Classify remaining variables
    grid_groups: dict[str, list[dict]] = defaultdict(list)
    multi_resp_groups: dict[str, dict] = {}  # name → variable dict
    standalone_vars: list[dict] = []

    for v in variables:
        # Skip vars consumed by an _other pattern; they're emitted separately.
        if v["name"] in base_names_in_other or v["name"] in other_var_names:
            continue
        group = v["group"]
        if v["type"] == "select_multiple":
            multi_resp_groups[v["name"]] = v
        elif group and _is_grid_group(variables, group):
            grid_groups[group].append(v)
        else:
            standalone_vars.append(v)

    # --- Emit varGrp elements first (XSD requires before var) ---

    # Grid groups — <txt> on the group and <preQTxt> on each member carry the
    # shared question stem (qwacback's canonical grid convention).
    for group_name, members in grid_groups.items():
        group_label = _get_group_label(variables, group_name)
        member_ids = [_make_var_id(m["name"]) for m in members]
        grp_el = SubElement(
            data_dscr, "varGrp",
            ID=_make_grp_id(group_name),
            name=group_name,
            type="grid",
            var=" ".join(member_ids),
        )
        SubElement(grp_el, "txt").text = group_label
        SubElement(grp_el, "concept").text = group_label

    # MultipleResp groups (from standalone select_multiple)
    for sm_name, sm_var in multi_resp_groups.items():
        binary_ids = [_make_var_id(f"{sm_name}_{c['name']}") for c in sm_var["choices"]]
        grp_el = SubElement(
            data_dscr, "varGrp",
            ID=_make_grp_id(sm_name),
            name=sm_name,
            type="multipleResp",
            var=" ".join(binary_ids),
        )
        SubElement(grp_el, "txt").text = sm_var["label"]
        SubElement(grp_el, "concept").text = sm_var["label"]

    # _other (semi-open) pattern groups
    for base_name, p in other_patterns.items():
        _emit_other_pattern(data_dscr, p)

    # --- Emit var elements ---

    # Grid member variables
    for group_name, members in grid_groups.items():
        group_label = _get_group_label(variables, group_name)
        for v in members:
            _add_var_element(
                data_dscr,
                var_id=_make_var_id(v["name"]),
                name=v["name"],
                label=v["label"],
                var_type=v["type"],
                choices=v["choices"],
                pre_q_txt=group_label,
            )

    # Binary vars for select_multiple
    for sm_name, sm_var in multi_resp_groups.items():
        for choice in sm_var["choices"]:
            _add_binary_var(
                data_dscr,
                var_id=_make_var_id(f"{sm_name}_{choice['name']}"),
                name=f"{sm_name}_{choice['name']}",
                question_label=sm_var["label"],
                choice_label=choice["label"],
            )

    # Vars emitted by the _other pattern handler
    for base_name, p in other_patterns.items():
        _emit_other_pattern_vars(data_dscr, p)

    # Standalone variables (non-grid, non-select_multiple, non-other-pattern)
    for v in standalone_vars:
        _add_var_element(
            data_dscr,
            var_id=_make_var_id(v["name"]),
            name=v["name"],
            label=v["label"],
            var_type=v["type"],
            choices=v["choices"],
            vocab=v.get("vocab", ""),
        )

    # Pretty-print
    raw = tostring(root, encoding="unicode", xml_declaration=False)
    dom = parseString(f'<?xml version="1.0" encoding="UTF-8"?>{raw}')
    return dom.toprettyxml(indent="  ", encoding=None)
