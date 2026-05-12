"""Source-agnostic DDI-Codebook 2.5 engine shared by kobo2ddi and limesurvey2ddi."""

from survey2ddi_core.ddi import apply_value_labels, read_value_maps, read_variable_labels

__all__ = ["read_variable_labels", "read_value_maps", "apply_value_labels"]
