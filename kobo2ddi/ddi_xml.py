"""Generate DDI-Codebook 2.5 XML from parsed survey data."""

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
    "select_multiple":  ("discrete",  "character"),
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

    # Assign stable IDs and collect groups
    groups: dict[str, list[str]] = defaultdict(list)
    for i, v in enumerate(variables, 1):
        v["_id"] = f"V{i}"
        if v["group"]:
            groups[v["group"]].append(v["_id"])

    # Variable groups (must appear before <var> elements)
    for group_name, var_ids in groups.items():
        SubElement(
            data_dscr, "varGrp",
            name=group_name, type="section", var=" ".join(var_ids),
        )

    # Variables
    for v in variables:
        intrvl, fmt_type = DDI_TYPE_MAP.get(v["type"], ("discrete", "character"))
        var_el = SubElement(
            data_dscr, "var",
            ID=v["_id"], name=v["name"], intrvl=intrvl,
        )

        SubElement(var_el, "labl").text = v["label"]

        if v["label"]:
            qstn = SubElement(var_el, "qstn")
            SubElement(qstn, "qstnLit").text = v["label"]

        for choice in v["choices"]:
            catgry = SubElement(var_el, "catgry")
            SubElement(catgry, "catValu").text = choice["name"]
            SubElement(catgry, "labl").text = choice["label"]

        SubElement(var_el, "varFormat", type=fmt_type)

    # Pretty-print
    raw = tostring(root, encoding="unicode", xml_declaration=False)
    dom = parseString(f'<?xml version="1.0" encoding="UTF-8"?>{raw}')
    return dom.toprettyxml(indent="  ", encoding=None)
