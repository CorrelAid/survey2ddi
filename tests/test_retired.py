"""Retirement notices: every entry point names its formtransform replacement."""

import pytest

from kobo2ddi import cli as kobo_cli
from limesurvey2ddi import cli as lime_cli
from limesurvey2ddi import transform as lime_tx
from survey2ddi_core import ddi
from survey2ddi_core.data import build_data_csv
from survey2ddi_core.ddi_xml import build_ddi_xml
from survey2ddi_core.retired import GUIDE
from survey2ddi_core.xlsform import extract_variables

from _helpers import TESTS_DIR

LSTSV = TESTS_DIR / "fixtures" / "lstsv" / "basic_survey.tsv"


ARGS = {"list": [], "pull": ["x"], "transform": ["x"], "metadata": ["x"]}


@pytest.mark.parametrize(
    ("cli", "command", "expected"),
    [
        (kobo_cli, "list", "Download XLS"),
        (kobo_cli, "pull", "XML values and headers"),
        (kobo_cli, "transform", "formtransform xlsform2ddi"),
        (kobo_cli, "metadata", "formtransform xlsform2ddi"),
        (lime_cli, "list", "Answer codes"),
        (lime_cli, "pull", "Answer codes"),
        (lime_cli, "transform", "formtransform lstsv2ddi"),
        (lime_cli, "metadata", "formtransform lstsv2ddi"),
    ],
)
def test_cli_prints_replacement_on_stderr(cli, command, expected, capsys, monkeypatch):
    # Stop right after the notice: no network, no files.
    monkeypatch.setattr(cli, f"cmd_{command}", lambda *_: None)
    cli.main([command, *ARGS[command]])
    err = capsys.readouterr().err
    assert "survey2ddi is retired" in err
    assert expected in err
    assert GUIDE in err


def test_cli_without_command_still_warns(capsys):
    with pytest.raises(SystemExit):
        kobo_cli.main([])
    assert "formtransform xlsform2ddi" in capsys.readouterr().err


def test_library_builders_warn(survey_rows, choices_by_list, settings, submissions):
    with pytest.warns(DeprecationWarning, match="buildDdiXml"):
        build_ddi_xml("T", survey_rows, choices_by_list, settings, submissions)
    with pytest.warns(DeprecationWarning, match="buildDataCsv"):
        build_data_csv(extract_variables(survey_rows, choices_by_list), submissions)


def test_limesurvey_builders_warn_once_with_lime_replacement(recwarn):
    lime_tx.build_ddi_xml("T", LSTSV, [])
    lime_tx.build_data_csv(LSTSV, [])
    messages = [str(w.message) for w in recwarn if w.category is DeprecationWarning]
    assert len(messages) == 2
    assert all("lstsv2ddi" in m for m in messages)


@pytest.mark.parametrize("fn", ["read_variable_labels", "read_value_maps"])
def test_reader_warns(fn):
    with pytest.warns(DeprecationWarning, match="ddi_reader.py"):
        getattr(ddi, fn)("<codeBook xmlns='ddi:codebook:2_5'/>")


def test_apply_value_labels_warns_once(recwarn):
    pd = pytest.importorskip("pandas")
    ddi.apply_value_labels(pd.DataFrame({"a": ["1"]}), "<codeBook xmlns='ddi:codebook:2_5'/>")
    assert len([w for w in recwarn if w.category is DeprecationWarning]) == 1
