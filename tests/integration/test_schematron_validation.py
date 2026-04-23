"""End-to-end validation via qwacback's /api/validate endpoint (XSD + Schematron)."""

import pytest

from kobo2ddi.ddi_xml import build_ddi_xml

pytestmark = pytest.mark.integration


class TestQwacbackValidation:
    def test_primary_xml_validates(
        self, validate_ddi,
        survey_rows, choices_by_list, settings, submissions,
    ):
        xml = build_ddi_xml("Test Survey", survey_rows, choices_by_list, settings, submissions)
        validate_ddi(xml, "primary.xml")

    def test_grid_xml_validates(
        self, validate_ddi,
        grid_survey_rows, grid_choices, settings,
    ):
        xml = build_ddi_xml("Grid Test", grid_survey_rows, grid_choices, settings, [])
        validate_ddi(xml, "grid.xml")
