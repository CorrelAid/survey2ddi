"""Python↔TS parity gate for retiring survey2ddi (#3). Temporary; not in CI.

Runs this package's emitters and formtransform's over the same fixture corpus
and byte-compares XML and CSV. Each case lands in one bucket:

- equal:    byte-identical
- expected: CSV differs only in column order, and the TS order is the XML's
            <var> order (Python's get_canonical_columns uses input order)
- finding:  anything else; file it on CorrelAid/formtransform

Usage (needs a built formtransform checkout, `npm ci && npm run build`):

    uv run python scripts/parity_gate.py /path/to/formtransform/dist
"""

import csv
import datetime
import difflib
import io
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from xml.etree.ElementTree import fromstring

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))

import conftest  # noqa: E402
import test_limesurvey_transform as lime_fx  # noqa: E402
from limesurvey2ddi import transform as lime_tx  # noqa: E402
from survey2ddi_core import ddi_xml  # noqa: E402
from survey2ddi_core.data import build_data_csv  # noqa: E402
from survey2ddi_core.xlsform import extract_variables  # noqa: E402

PROD_DATE = "2026-01-01"
DATASET = "data.csv"
LSTSV = ROOT / "tests" / "fixtures" / "lstsv"


class _PinnedDate(datetime.date):
    @classmethod
    def today(cls):
        return cls.fromisoformat(PROD_DATE)


ddi_xml.date = _PinnedDate


def _row(type_, name, label=None, appearance=None):
    return {"type": type_, "name": name, "label": label, "required": "false", "appearance": appearance}


# Not in the pytest suite as one survey: every emit bucket at once (grid,
# select_multiple, select_one/select_multiple + _other, inline note).
COMBO_ROWS = [
    _row("note", "intro", "Please answer honestly."),
    _row("text", "comment", "Comment"),
    _row("begin_group", "trust", "Trust in institutions", "table-list"),
    _row("select_one skala", "trust_parl", "Parliament"),
    _row("select_one skala", "trust_police", "Police"),
    _row("end_group", None),
    _row("select_multiple fruit", "fruit", "Fruit you like"),
    _row("text", "fruit_other", "Other fruit"),
    _row("select_one colour", "colour", "Favourite colour"),
    _row("text", "colour_other", "Other colour"),
    _row("integer", "age", "Age"),
]
COMBO_CHOICES = {
    "skala": [{"name": "1", "label": "Low"}, {"name": "2", "label": "High"}],
    "fruit": [
        {"name": "apple", "label": "Apple"},
        {"name": "pear", "label": "Pear"},
        {"name": "other", "label": "Other"},
    ],
    "colour": [{"name": "red", "label": "Red"}, {"name": "other", "label": "Other"}],
}
COMBO_SUBMISSIONS = [
    {"comment": 'says "hi", twice', "trust/trust_parl": "1", "trust/trust_police": "2",
     "fruit": "apple other", "fruit_other": "kiwi", "colour": "other", "colour_other": "teal", "age": "40"},
    {"comment": "multi\nline", "trust/trust_parl": "2", "trust/trust_police": None,
     "fruit": "pear", "fruit_other": "", "colour": "red", "colour_other": "", "age": ""},
]

XLSFORM_CASES = {
    "conftest.SURVEY_ROWS": (conftest.SURVEY_ROWS, conftest.CHOICES_BY_LIST, conftest.SETTINGS, conftest.SUBMISSIONS),
    "conftest.GRID_SURVEY_ROWS": (conftest.GRID_SURVEY_ROWS, conftest.GRID_CHOICES, conftest.SETTINGS,
                                  [{"trust/trust_parliament": "1", "trust/trust_police": "5"}]),
    "test_limesurvey_transform.LIME_SURVEY_ROWS": (
        lime_fx.LIME_SURVEY_ROWS, lime_fx.LIME_CHOICES, lime_fx.LIME_SETTINGS,
        [{"haeufigkeit": "1", "bereiche": "holz textil", "beruf_post": "5",
          "am_meisten_gebracht": "It was great", "nps_score": "9"}]),
    "synthetic.combo": (COMBO_ROWS, COMBO_CHOICES, {"id_string": "combo"}, COMBO_SUBMISSIONS),
}

# LimeSurvey exports with question-code headings and answer codes.
LSTSV_CASES = {
    "examples/basic (basic_survey.tsv + responses.json)": (
        LSTSV / "basic_survey.tsv",
        json.loads((ROOT / "examples" / "basic" / "responses.json").read_text()),
    ),
    "lstsv/complex_survey.tsv": (
        LSTSV / "complex_survey.tsv",
        [{"id": "1", "submitdate": "2025-01-01", "fullname": "Ada", "age": "36", "gender": "feml",
          "favoritecolors[red]": "Y", "favoritecolors[blue]": "", "favoritecolors[green]": "Y",
          "favoritecolors[yello]": "", "satisfactionlevel": "happ", "othercomments": "",
          "surveydate": "2025-01-01"}],
    ),
    "lstsv/all_types_survey.tsv": (
        LSTSV / "all_types_survey.tsv",
        [{"id": "1", "orphanbefore": "P-7", "qtext": "Ada L.", "qinteger": "3", "qselectone": "yes",
          "qselectmulti[red]": "Y", "qselectmulti[green]": "Y", "qlikert": "mid",
          "matrixheader[skillpython]": "adv", "matrixheader[skilljs]": "basic",
          "qsel1other": "-oth-", "qsel1other[other]": "Design"}],
    ),
}


def _python_side():
    out = {}
    for name, (rows, choices, settings, subs) in XLSFORM_CASES.items():
        out[name] = {
            "xml": ddi_xml.build_ddi_xml(name, rows, choices, settings, subs, dataset_filename=DATASET),
            "csv": build_data_csv(extract_variables(rows, choices), subs),
        }
    for name, (path, responses) in LSTSV_CASES.items():
        out[name] = {
            "xml": lime_tx.build_ddi_xml(name, path, responses, dataset_filename=DATASET),
            "csv": lime_tx.build_data_csv(path, responses),
        }
    return out


def _ts_side(dist: Path):
    jobs = [
        {"kind": "xlsform", "name": n, "title": n, "surveyRows": r, "choices": c, "settings": s,
         "submissions": subs, "prodDate": PROD_DATE, "datasetFilename": DATASET}
        for n, (r, c, s, subs) in XLSFORM_CASES.items()
    ] + [
        {"kind": "lstsv", "name": n, "title": n, "tsv": p.read_text(encoding="utf-8"),
         "submissions": resp, "prodDate": PROD_DATE, "datasetFilename": DATASET}
        for n, (p, resp) in LSTSV_CASES.items()
    ]
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(jobs, f)
    res = subprocess.run(
        ["node", str(ROOT / "scripts" / "parity_gate.mjs"), str(dist), f.name],
        capture_output=True, text=True, check=True,
    )
    return json.loads(res.stdout)


def _xml_var_order(xml: str) -> list[str]:
    ns = {"d": "ddi:codebook:2_5"}
    return [v.get("name") for v in fromstring(xml).findall(".//d:dataDscr/d:var", ns)]


def _csv_records(text: str):
    rows = list(csv.reader(io.StringIO(text, newline="")))
    header, body = rows[0], rows[1:]
    return header, [dict(zip(header, r)) for r in body]


def _diff(a: str, b: str, label: str) -> str:
    return "".join(difflib.unified_diff(
        a.splitlines(True), b.splitlines(True), f"python/{label}", f"ts/{label}", n=1))


# lstsv.py invents study metadata the TSV doesn't hold: IDNo = title,
# version = "1.0". formtransform omits both.
_INVENTED_META = re.compile(
    r"\s*<IDNo>[^<]*</IDNo>|\s*<verStmt>\s*<version>1\.0</version>\s*</verStmt>")


def classify(py, ts, lstsv):
    """Return (xml_bucket, csv_bucket, notes)."""
    if "error" in ts:
        return "finding", "finding", ["TS raised:\n" + ts["error"]]
    notes = []
    if ts.get("rejected"):
        notes.append("TS rejects this TSV by default (registry subset); "
                     "compared with skipValidation:\n" + ts["rejected"])

    if py["xml"] == ts["xml"]:
        xml_bucket = "equal"
    elif lstsv and _INVENTED_META.sub("", py["xml"]) == ts["xml"]:
        xml_bucket = "expected"
        notes.append("XML: Python invents <IDNo> (= title) and <version>1.0</version> "
                     "for TSV input; TS omits them.")
    else:
        xml_bucket = "finding"
        notes.append(_diff(py["xml"], ts["xml"], "xml"))

    if py["csv"] == ts["csv"]:
        return xml_bucket, "equal", notes
    py_head, py_rows = _csv_records(py["csv"])
    ts_head, ts_rows = _csv_records(ts["csv"])
    ts_matches_xml = ts_head == _xml_var_order(ts["xml"])
    if set(py_head) == set(ts_head) and py_rows == ts_rows and ts_matches_xml:
        dupes = sorted({h for h in py_head if py_head.count(h) > 1})
        if dupes:
            notes.append(f"CSV: Python header repeats {dupes} (select_multiple 'other' "
                         "binary collides with the <base>_other text column); TS emits it once, "
                         "matching the XML.")
        notes.append(f"CSV column order only.\n  python: {py_head}\n  ts:     {ts_head}")
        return xml_bucket, "expected", notes
    notes.append(f"TS CSV header matches its XML <var> order: {ts_matches_xml}")
    notes.append(_diff(py["csv"], ts["csv"], "csv"))
    return xml_bucket, "finding", notes


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    py, ts = _python_side(), _ts_side(Path(sys.argv[1]))
    print("| case | XML | CSV |\n| --- | --- | --- |")
    details = []
    findings = 0
    for name in py:
        xb, cb, notes = classify(py[name], ts[name], name in LSTSV_CASES)
        findings += (xb == "finding") + (cb == "finding")
        print(f"| `{name}` | {xb} | {cb} |")
        if notes:
            details.append(f"\n### {name}\n\n```diff\n" + "\n".join(notes).rstrip() + "\n```")
    print("\n".join(details))
    print(f"\n{findings} finding(s)")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
