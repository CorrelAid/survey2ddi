"""Retirement notices. survey2ddi is replaced by CorrelAid/formtransform.

Every entry point still works and calls :func:`warn_retired` with its exact
replacement: library functions as a ``DeprecationWarning``, CLI commands on
stderr, where a plain run shows it.
"""

import sys
import warnings

GUIDE = "https://github.com/CorrelAid/formtransform/blob/main/RESPONSE_DATA.md"
FORMTRANSFORM = "npx github:CorrelAid/formtransform"

KOBO_EXPORT = (
    "export from KoboToolbox yourself: the form via Form → Download XLS, the data via "
    "Data → Downloads (CSV or JSON, 'XML values and headers'). "
    "There is no API pull replacement"
)
KOBO_CONVERT = f"{FORMTRANSFORM} xlsform2ddi form.xlsx -o codebook.xml [--data export.csv]"
LIME_EXPORT = (
    "export from LimeSurvey yourself: Responses → Export, CSV, "
    "'Headings: Question code' and 'Responses: Answer codes' (not full answers). "
    "There is no API pull replacement"
)
LIME_CONVERT = f"{FORMTRANSFORM} lstsv2ddi survey.tsv -o codebook.xml [--data export.csv]"
READER = (
    "copy formtransform's stdlib reader examples/python/ddi_reader.py "
    "(variable_labels, value_labels, apply_value_labels)"
)


def retired_message(what: str, replacement: str) -> str:
    return f"survey2ddi is retired. Instead of {what}: {replacement}. Guide: {GUIDE}"


def warn_retired(what: str, replacement: str, *, cli: bool = False) -> None:
    """Emit a ``DeprecationWarning`` naming *replacement*; on the CLI, print it instead."""
    message = retired_message(what, replacement)
    if cli:
        print(f"WARNING: {message}\n", file=sys.stderr)
    else:
        warnings.warn(message, DeprecationWarning, stacklevel=3)
