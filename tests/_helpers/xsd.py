"""XSD validation helpers — wraps ``xmllint`` subprocess invocation."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from _helpers import CODEBOOK_XSD

XMLLINT_AVAILABLE = shutil.which("xmllint") is not None

requires_xmllint = pytest.mark.skipif(
    not XMLLINT_AVAILABLE,
    reason="xmllint not available",
)


def validate_with_xsd(xml_path: Path, xsd_path: Path = CODEBOOK_XSD) -> None:
    """Run xmllint against *xml_path* and assert it validates against *xsd_path*."""
    result = subprocess.run(
        ["xmllint", "--noout", "--schema", str(xsd_path), str(xml_path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"XSD validation failed:\n{result.stderr}"
