"""Shared test helpers — DDI namespaces, XSD validation, fixture paths."""

from pathlib import Path

DDI_NS = {"ddi": "ddi:codebook:2_5"}

TESTS_DIR = Path(__file__).resolve().parent.parent
SCHEMAS_DIR = TESTS_DIR / "schemas"
CODEBOOK_XSD = SCHEMAS_DIR / "codebook.xsd"

__all__ = ["DDI_NS", "TESTS_DIR", "SCHEMAS_DIR", "CODEBOOK_XSD"]
