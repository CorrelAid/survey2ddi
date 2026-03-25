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
    "select_one":       ("discrete",  "numeric"),
    "select_multiple":  ("discrete",  "numeric"),
    "rank":             ("discrete",  "numeric"),
    "integer":          ("contin",    "numeric"),
    "decimal":          ("contin",    "numeric"),
    "range":            ("contin",    "numeric"),
    "calculate":        ("contin",    "numeric"),
    "string":           ("discrete",  "character"),
    "date":             ("discrete",  "character"),
    "time":             ("discrete",  "character"),
    "datetime":         ("discrete",  "character"),
    "acknowledge":      ("discrete",  "numeric"),
    "hidden":           ("discrete",  "character"),
}

# Type → responseDomainType for <qstn>
RESPONSE_DOMAIN_MAP = {
    "select_one":       "category",
    "select_multiple":  "multiple",
    "rank":             "category",
    "integer":          "numeric",
    "decimal":          "numeric",
    "range":            "numeric",
    "calculate":        "numeric",
    "string":           "text",
    "date":             "text",
    "time":             "text",
    "datetime":         "text",
    "acknowledge":      "text",
    "hidden":           "text",
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
    measure: str,
    choices: list[dict],
    pre_q_txt: str = "",
) -> Element:
    """Add a single <var> element with qwacback-compliant structure.

    Element order: qstn → catgry* → concept → varFormat
    """
    intrvl, fmt_type = DDI_TYPE_MAP.get(var_type, ("discrete", "character"))
    resp_domain = RESPONSE_DOMAIN_MAP.get(var_type, "text")

    var_attrs = {"ID": var_id, "name": name, "intrvl": intrvl}
    if measure:
        var_attrs["nature"] = measure
    var_el = SubElement(parent, "var", **var_attrs)

    # qstn (with responseDomainType)
    if label:
        qstn = SubElement(var_el, "qstn", responseDomainType=resp_domain)
        if pre_q_txt:
            SubElement(qstn, "preQTxt").text = pre_q_txt
        SubElement(qstn, "qstnLit").text = label

    # catgry elements
    for choice in choices:
        catgry = SubElement(var_el, "catgry")
        SubElement(catgry, "catValu").text = choice["name"]
        SubElement(catgry, "labl").text = choice["label"]

    # concept (replaces labl on var)
    SubElement(var_el, "concept").text = label

    # varFormat
    SubElement(var_el, "varFormat", type=fmt_type, schema="other")

    return var_el


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

    # Classify groups and collect member variables
    grid_groups: dict[str, list[dict]] = defaultdict(list)
    multi_resp_groups: dict[str, dict] = {}  # name → variable dict
    standalone_vars: list[dict] = []

    for v in variables:
        group = v["group"]
        if v["type"] == "select_multiple":
            # select_multiple becomes its own multipleResp group
            multi_resp_groups[v["name"]] = v
        elif group and _is_grid_group(variables, group):
            grid_groups[group].append(v)
        else:
            standalone_vars.append(v)

    # --- Emit varGrp elements first (XSD requires before var) ---

    # Grid groups
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

    # MultipleResp groups (from select_multiple)
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
                measure=v["measure"],
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

    # Standalone variables (non-grid, non-select_multiple)
    for v in standalone_vars:
        _add_var_element(
            data_dscr,
            var_id=_make_var_id(v["name"]),
            name=v["name"],
            label=v["label"],
            var_type=v["type"],
            measure=v["measure"],
            choices=v["choices"],
        )

    # Pretty-print
    raw = tostring(root, encoding="unicode", xml_declaration=False)
    dom = parseString(f'<?xml version="1.0" encoding="UTF-8"?>{raw}')
    return dom.toprettyxml(indent="  ", encoding=None)
