import pytest
import pandas as pd
from pathlib import Path
from kobo2ddi.ddi import read_variable_labels, read_value_maps, apply_value_labels

SAMPLE_DDI = """<?xml version="1.0" encoding="UTF-8"?>
<codeBook xmlns="ddi:codebook:2_5" version="2.5">
  <stdyDscr>
    <citation>
      <titlStmt>
        <titl>Test Survey</titl>
      </titlStmt>
    </citation>
  </stdyDscr>
  <dataDscr>
    <var name="q1">
      <labl>What is your name?</labl>
    </var>
    <var name="q2">
      <labl>How old are you?</labl>
    </var>
    <var name="q3">
      <labl>Select a choice</labl>
      <catgry>
        <catValu>A1</catValu>
        <labl>Choice 1</labl>
      </catgry>
      <catgry>
        <catValu>A2</catValu>
        <labl>Choice 2</labl>
      </catgry>
    </var>
  </dataDscr>
</codeBook>
"""

def test_read_variable_labels():
    labels = read_variable_labels(SAMPLE_DDI.encode("utf-8"))
    assert labels == {
        "q1": "What is your name?",
        "q2": "How old are you?",
        "q3": "Select a choice",
    }

def test_read_value_maps():
    v_maps = read_value_maps(SAMPLE_DDI.encode("utf-8"))
    assert "q3" in v_maps
    assert v_maps["q3"] == {"A1": "Choice 1", "A2": "Choice 2"}
    assert "q1" not in v_maps  # No categories for q1

def test_apply_value_labels():
    df = pd.DataFrame({
        "q1": ["Alice", "Bob"],
        "q3": ["A1", "A2"]
    })
    
    apply_value_labels(df, SAMPLE_DDI.encode("utf-8"))
    
    assert df["q1"].tolist() == ["Alice", "Bob"]
    assert df["q3"].tolist() == ["Choice 1", "Choice 2"]

def test_apply_value_labels_with_missing_columns():
    df = pd.DataFrame({
        "q1": ["Alice"]
    })
    # Should not raise error if q3 is missing
    apply_value_labels(df, SAMPLE_DDI.encode("utf-8"))
    assert "q1" in df.columns

def test_apply_value_labels_fills_na():
    df = pd.DataFrame({
        "q3": ["A1", "Unknown"]
    })
    apply_value_labels(df, SAMPLE_DDI.encode("utf-8"))
    # Unknown code remains as is
    assert df["q3"].tolist() == ["Choice 1", "Unknown"]

def test_read_from_path(tmp_path):
    p = tmp_path / "test.xml"
    p.write_text(SAMPLE_DDI, encoding="utf-8")
    labels = read_variable_labels(p)
    assert "q1" in labels
