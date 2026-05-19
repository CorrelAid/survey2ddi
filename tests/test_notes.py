"""Tests for survey2ddi_core.notes — note classification."""

from survey2ddi_core.notes import classify_notes
from survey2ddi_core.types import Variable


def _v(name: str, type: str = "text", group: str = "", label: str | None = None) -> Variable:
    if label is None:
        label = name
    return Variable(name=name, type=type, group=group, label=label)


def test_inline_note_attaches_to_next_var():
    variables = [_v("intro", "note", label="Welcome."), _v("age", "integer")]
    c = classify_notes(variables)
    assert [v.name for v in c.data_vars] == ["age"]
    assert c.inline_preqtxt == {"age": "Welcome."}
    assert c.orphan_notes == []


def test_consecutive_inline_notes_joined():
    variables = [
        _v("n1", "note", label="Para 1."),
        _v("n2", "note", label="Para 2."),
        _v("q", "text"),
    ]
    c = classify_notes(variables)
    assert c.inline_preqtxt == {"q": "Para 1.\n\nPara 2."}
    assert c.orphan_notes == []


def test_trailing_note_is_orphan():
    variables = [_v("q", "integer"), _v("outro", "note", label="Thanks.")]
    c = classify_notes(variables)
    assert c.data_vars == [variables[0]]
    assert c.inline_preqtxt == {}
    assert c.orphan_notes == [variables[1]]


def test_note_at_group_boundary_is_orphan():
    """A note in group A followed only by a var in group B has no in-scope successor."""
    variables = [
        _v("a1", "integer", group="A"),
        _v("trailing_a", "note", group="A", label="End of A."),
        _v("b1", "integer", group="B"),
    ]
    c = classify_notes(variables)
    assert [v.name for v in c.data_vars] == ["a1", "b1"]
    assert c.inline_preqtxt == {}
    assert [n.name for n in c.orphan_notes] == ["trailing_a"]


def test_intro_only_note_is_orphan_when_no_data_vars():
    variables = [_v("only_note", "note", label="Hello.")]
    c = classify_notes(variables)
    assert c.data_vars == []
    assert c.inline_preqtxt == {}
    assert [n.name for n in c.orphan_notes] == ["only_note"]


def test_empty_label_note_dropped_from_inline_but_still_classified():
    """A note with no body produces no preQTxt text."""
    variables = [_v("blank", "note", label=""), _v("q", "text")]
    c = classify_notes(variables)
    assert c.inline_preqtxt == {}  # nothing to attach
    assert c.orphan_notes == []
    assert [v.name for v in c.data_vars] == ["q"]
