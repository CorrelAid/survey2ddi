"""Classify ``note`` variables for spec-correct DDI emission.

XLSForm/LimeSurvey allow informational rows (``type == "note"`` /
``type/scale == "X"``) that carry no respondent data. Emitting them as
plain ``<var>`` elements (the qwacback convention) breaks DDI's contract
that ``dataDscr/var`` describes a data column.

This module splits them into two buckets:

- **Inline notes** — followed by a data-carrying variable in the same group.
  Attached as ``<preQTxt>`` on that next variable's ``<qstn>``.
- **Orphan notes** — no data-carrying successor in scope (intro pages,
  closing pages, group-trailing notes). Emitted as ``<notes
  type="instruction" subject="<name>">`` on ``<stdyDscr>``.

Consecutive inline notes targeting the same variable are joined with a
blank line so the ``<preQTxt>`` reads as one block.
"""

from __future__ import annotations

from dataclasses import dataclass

from survey2ddi_core.types import Variable


@dataclass(frozen=True, slots=True)
class ClassifiedNotes:
    data_vars: list[Variable]
    """Data-carrying variables, in original order. Notes excluded."""

    inline_preqtxt: dict[str, str]
    """``data_var.name`` → combined preceding-note text (joined with ``\\n\\n``)."""

    orphan_notes: list[Variable]
    """Notes with no data-carrying successor in the same group."""


def classify_notes(variables: list[Variable]) -> ClassifiedNotes:
    """Walk *variables* and assign each ``note`` to inline or orphan."""
    data_vars: list[Variable] = []
    inline_preqtxt: dict[str, list[str]] = {}
    orphan: list[Variable] = []
    pending: list[Variable] = []

    for v in variables:
        if v.type == "note":
            pending.append(v)
            continue

        # Found a data-carrying var. Pending notes from the same group attach
        # to it as preQTxt; notes from other groups have no successor in
        # their own scope and become orphans.
        same_group = [n.label for n in pending if n.group == v.group and n.label]
        diff_group = [n for n in pending if n.group != v.group]
        if same_group:
            inline_preqtxt.setdefault(v.name, []).extend(same_group)
        orphan.extend(diff_group)
        pending = []
        data_vars.append(v)

    # Anything left over has no successor at all → study outro.
    orphan.extend(pending)

    return ClassifiedNotes(
        data_vars=data_vars,
        inline_preqtxt={k: "\n\n".join(v) for k, v in inline_preqtxt.items()},
        orphan_notes=orphan,
    )
