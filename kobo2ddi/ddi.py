"""Utilities for reading and using generated DDI XML files."""

import xml.etree.ElementTree as ET
from pathlib import Path

NS = {"ddi": "ddi:codebook:2_5"}


def _get_root(xml_source: str | Path | bytes) -> ET.Element:
    """Load XML from path, string, or bytes and return the root element."""
    if isinstance(xml_source, Path):
        return ET.parse(xml_source).getroot()
    if isinstance(xml_source, bytes):
        return ET.fromstring(xml_source)
    # Check if it looks like a file path
    if isinstance(xml_source, str) and not xml_source.strip().startswith("<"):
        return ET.parse(xml_source).getroot()
    return ET.fromstring(xml_source)


def read_variable_labels(xml_source: str | Path | bytes) -> dict[str, str]:
    """Extract human-readable labels for all variables.

    Returns a dict mapping variable names to their labels.
    """
    root = _get_root(xml_source)
    labels = {}
    for var in root.findall(".//ddi:var", NS):
        name = var.get("name")
        if not name:
            continue
        # qwacback convention: var labels live in <concept>, not <labl>.
        # Fall back to <qstn>/<qstnLit> for older/alt outputs.
        for path in ("ddi:concept", "ddi:qstn/ddi:qstnLit", "ddi:labl"):
            node = var.find(path, NS)
            if node is not None and node.text:
                labels[name] = node.text
                break
    return labels


def read_value_maps(xml_source: str | Path | bytes) -> dict[str, dict[str, str]]:
    """Extract value-to-label mappings for all categorical variables.

    Returns a dict mapping variable names to a mapping dict (code -> label).
    """
    root = _get_root(xml_source)
    maps = {}
    for var in root.findall(".//ddi:var", NS):
        name = var.get("name")
        catgries = var.findall("ddi:catgry", NS)
        if name and catgries:
            m = {}
            for cat in catgries:
                val_node = cat.find("ddi:catValu", NS)
                labl_node = cat.find("ddi:labl", NS)
                if val_node is not None and labl_node is not None:
                    m[val_node.text or ""] = labl_node.text or ""
            maps[name] = m
    return maps


def apply_value_labels(df, xml_source: str | Path | bytes):
    """Apply DDI value labels to a pandas DataFrame in-place.

    *df* should be a pandas DataFrame whose columns match DDI variable names.
    Columns with categorical mappings in the XML will be converted to
    strings and remapped.
    """
    value_maps = read_value_maps(xml_source)
    for col, mapping in value_maps.items():
        if col in df.columns:
            # We cast to string because DDI values are strings and CSVs
            # might be read with mixed types.
            df[col] = df[col].astype(str).map(mapping).fillna(df[col])
    return df
