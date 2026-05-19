"""Canonical response layer + DDI-aligned CSV emitter (Track B).

The DDI XML produced by ``survey2ddi_core.ddi_xml.build_ddi_xml`` expands every
``select_multiple`` question into N binary ``<var>`` elements, one per choice
(named ``<question>_<choice>``). To keep the data file in lock-step with the
schema we mirror that expansion in the CSV: each ``select_multiple`` becomes
N columns of ``"0"`` / ``"1"``. Every CSV header therefore matches a
``<var name="">`` in the XML exactly — programmatic schema↔data alignment is
trivial.

The matcher is platform-neutral. Source adapters (``kobo2ddi`` is essentially
identity, ``limesurvey2ddi.transform.normalize_responses`` handles LimeSurvey
quirks) feed it rows keyed by ``v.data_key`` with ``select_multiple``
values stored as space-joined choice codes.
"""

from __future__ import annotations

import csv
import io

from survey2ddi_core.types import Variable


def _data_carrying(variables: list[Variable]) -> list[Variable]:
    """Drop variables that carry no respondent data (currently: ``note``)."""
    return [v for v in variables if v.type != "note"]


def get_canonical_columns(variables: list[Variable]) -> list[str]:
    """DDI variable names in the same order ``build_ddi_xml`` emits them.

    ``select_multiple`` is expanded to ``<name>_<choice>`` columns. All other
    variables contribute a single column equal to ``v.name``. ``note``
    variables are skipped — they have no data column.
    """
    cols: list[str] = []
    for v in _data_carrying(variables):
        if v.type == "select_multiple":
            for c in v.choices:
                cols.append(f"{v.name}_{c.name}")
        else:
            cols.append(v.name)
    return cols


def to_canonical_rows(
    variables: list[Variable],
    neutral_rows: list[dict],
) -> list[dict]:
    """Re-key adapter rows to DDI variable names.

    *neutral_rows* are keyed by ``v.data_key`` (``"group/name"`` or
    ``"name"``).  ``select_multiple`` values are space-joined choice codes;
    they are expanded into per-choice ``"0"``/``"1"`` columns. Every other
    variable becomes a single string column.

    Output rows have one entry per column returned by
    ``get_canonical_columns(variables)``.
    """
    out: list[dict] = []
    data_vars = _data_carrying(variables)
    for row in neutral_rows:
        canonical: dict[str, str] = {}
        for v in data_vars:
            raw = row.get(v.data_key, "")
            if v.type == "select_multiple":
                selected = set(str(raw).split()) if raw else set()
                for c in v.choices:
                    col = f"{v.name}_{c.name}"
                    canonical[col] = "1" if c.name in selected else "0"
            else:
                canonical[v.name] = "" if raw is None else str(raw)
        out.append(canonical)
    return out


def build_data_csv(
    variables: list[Variable],
    neutral_rows: list[dict],
) -> str:
    """RFC 4180 CSV — headers = DDI ``<var name="">`` in XML order.

    Uses CRLF line endings and minimal quoting (only when a field contains
    a delimiter, quote, or line break).
    """
    cols = get_canonical_columns(variables)
    canonical_rows = to_canonical_rows(variables, neutral_rows)

    buf = io.StringIO(newline="")
    writer = csv.DictWriter(
        buf,
        fieldnames=cols,
        lineterminator="\r\n",
        quoting=csv.QUOTE_MINIMAL,
    )
    writer.writeheader()
    for row in canonical_rows:
        writer.writerow(row)
    return buf.getvalue()
