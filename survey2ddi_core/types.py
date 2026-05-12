"""Shared schema types for survey2ddi.

``Variable`` is the canonical, source-agnostic representation of a question
in a survey. Adapters (kobo2ddi, limesurvey2ddi) produce ``list[Variable]``
via ``xlsform.extract_variables``; ``ddi_xml.build_ddi_xml`` and
``data.build_data_csv`` consume them.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class Choice:
    name: str
    label: str = ""


@dataclass(frozen=True, slots=True)
class Variable:
    name: str
    type: str
    label: str = ""
    group: str = ""
    group_label: str = ""
    group_appearance: str = ""
    measure: str = ""
    list_name: str = ""
    vocab: str = ""
    choices: tuple[Choice, ...] = ()
    values: str = ""
    required: str = "false"
    source_type: str = ""
    data_key: str = field(default="")
