[![PyPI](https://img.shields.io/pypi/v/survey2ddi.svg)](https://pypi.org/project/survey2ddi/)
[![Python](https://img.shields.io/pypi/pyversions/survey2ddi.svg)](https://pypi.org/project/survey2ddi/)
[![AI-Assisted](https://img.shields.io/badge/AI--assisted-Claude%20Code-blueviolet?logo=anthropic&logoColor=white)](./AI_DISCLOSURE.md)


This repository is part of the Civic Data Lab's [Survey Toolbox](https://umfragen.civic-data.de/). In the Toolbox you'll find information and guidance on everything related to surveys — from design to analysis.

# survey2ddi

**Bridge the gap between raw survey exports and archival-grade metadata.**

Survey platforms like KoboToolbox and LimeSurvey are excellent for data collection, but their raw exports are often difficult to use for long-term archiving or secondary analysis. They frequently lack clear labels, structured metadata, and standardized formats.

`survey2ddi` transforms these raw exports into a standardized pair of files:
1.  **DDI-Codebook 2.5 XML**: A machine-readable schema containing all question texts, choice labels, and group structures. Compatible with the [qwac](https://qwac.correlaid.org/) question bank.
2.  **DDI-Aligned CSV**: Clean response data where column headers match the XML variable names exactly, and multi-select questions are expanded into binary indicators.

## Why use this?

*   **Long-term Archiving**: Move away from cryptic CSVs to self-documenting DDI metadata.
*   **Interoperability**: Import your survey structure directly into tools like [qwac](https://qwac.correlaid.org/).
*   **Data Analysis**: Use the generated XML to automatically apply labels to your data in R, Python, or Stata (see our [example notebook](./examples/basic/analysis_example.ipynb)).
*   **Reproducibility**: Maintain a strict link between your data collection instrument (XLSForm/TSV) and the resulting dataset.

## Setup

Requires Python 3.13+. Install with [uv](https://docs.astral.sh/uv/):

```bash
uv sync
```

Copy `.env.example` to `.env` and fill in your credentials.

## Usage

### 1. Pull data from your platform
First, download the raw responses and structure from your survey platform.

**KoboToolbox:**
```bash
uv run kobo2ddi pull <asset_uid>
```

**LimeSurvey:**
```bash
uv run limesurvey2ddi pull <survey_id>
# Then export the "Survey structure" (TSV) from LimeSurvey's admin UI
# and place it in the output folder as survey.tsv
```

LimeSurvey schema source is the survey-structure TSV (Surveys → Export → Survey structure). XLSForm input is no longer supported on the LimeSurvey side — use the [xlsform2lstsv](https://github.com/CorrelAid/xlsform2lstsv) bridge if you author surveys in XLSForm.

### 2. Transform to DDI + CSV
Once the data is cached locally, generate the standardized outputs.

```bash
# KoboToolbox
uv run kobo2ddi transform <asset_uid>

# OR use a raw CSV export from the GUI instead of the API JSON
# (Must be exported with "XML values and headers" and use , or ; as delimiter)
uv run kobo2ddi transform <asset_uid> --data path/to/export.csv --title "My Study"

# LimeSurvey (uses cached responses.json + survey.tsv)
uv run limesurvey2ddi transform <survey_id> --title "My Research Study"

# OR use a raw CSV export from the GUI instead of the API JSON
# (Must be exported with "Question codes" as headers)
uv run limesurvey2ddi transform <survey_id> --data path/to/export.csv --title "My Study"
```

The output will be saved in `output/<id>/` as `<id>.xml` and `<id>.csv`.

Title resolution order: `--title` flag → `form_title` from XLSForm `settings` sheet (Kobo) / `surveyls_title` from TSV (LimeSurvey) → KoboToolbox API asset name (Kobo, only when `--data` not used) / survey ID (LimeSurvey) → `"Untitled"`. Omit `--title` when the schema already carries one; for Kobo this also skips the API call.

### Metadata only (no responses)

If you only need the DDI codebook — e.g. before the survey is fielded, or to import the structure into [qwac](https://qwac.correlaid.org/) — skip the response data entirely. No API call, no CSV output.

```bash
# KoboToolbox: from a local form.xlsx
uv run kobo2ddi metadata path/to/form.xlsx --title "My Survey"

# LimeSurvey: survey-structure TSV
uv run limesurvey2ddi metadata path/to/survey.tsv --title "My Survey"
```

Output XML lands next to the schema file (override with `-o`).

## Examples

We provide a basic example of the generated output and a Jupyter notebook showing how to use them for analysis in the `examples/` directory.

To run the example notebook:
```bash
uv sync --group notebook
cd examples/basic
uv run jupyter notebook analysis_example.ipynb
```

## Running tests

```
uv run pytest
```

Tests include XSD validation of generated XML against the official DDI-Codebook 2.5 schema (requires `xmllint`, auto-skipped if not available).

### Integration tests (Schematron)

Schematron rules go beyond the XSD (uniqueness of IDs, consistency between variable groups and their members, `_other` conventions, etc.). They live in [qwacback](https://github.com/CorrelAid/qwacback) and are checked by a Java worker exposed behind `POST /api/validate`. The integration suite boots that stack via docker compose and posts generated XML to it.

```
uv run pytest -m integration
```

Requires Docker. The session fixture pulls `ghcr.io/correlaid/qwacback{,-schematron-worker}:latest`, waits for readiness, then tears the stack down. Cold start is ~20-30s; subsequent tests in the same session are ~1s.

To iterate faster, keep the stack up and point tests at it:

```
docker compose -f tests/integration/docker-compose.validate.yml up -d --wait
S2D_VALIDATE_URL=http://127.0.0.1:8090 uv run pytest -m integration
```

Pin to a specific qwacback build with `QWACBACK_TAG=sha-abc1234` (or a semver like `0.1.0`). Change `PB_PORT` if 8090 is taken.

## Validating XML manually

```
xmllint --noout --schema tests/schemas/codebook.xsd output/<id>/<id>.xml
```

The schema files in `tests/schemas/` are the official DDI-Codebook 2.5 XSD from the [DDI Alliance](https://ddialliance.org/Specification/DDI-Codebook/2.5/).

## Releasing to PyPI

Releases are published by [`/.github/workflows/publish.yml`](.github/workflows/publish.yml), which runs on any tag matching `v*`. Authentication is via [PyPI Trusted Publishers](https://docs.pypi.org/trusted-publishers/) (OIDC) — no API token is stored in the repo.

To cut a new release:

```bash
# 1. Bump version in pyproject.toml
# 2. Commit and tag
git add pyproject.toml
git commit -m "chore: release vX.Y.Z"
git tag vX.Y.Z
git push origin main --tags
```

The workflow builds with `uv build`, runs the test suite, and publishes the resulting sdist + wheel to https://pypi.org/project/survey2ddi/. Versions are hand-bumped — no automated semantic-release.

One-time setup (already done for this repo):
- PyPI → account → *Publishing* → add Trusted Publisher pointing at `CorrelAid/survey2ddi` workflow `publish.yml` in environment `pypi`.
- GitHub → repo settings → *Environments* → create environment `pypi`.

## Known limitations

**Multi-language forms:** Only the first `label::*` column in the XLSForm is used. For bilingual forms, place the preferred language column first.

**Repeat groups:** Variables inside `begin_repeat`/`end_repeat` blocks are silently skipped. KoboToolbox stores repeat data as nested arrays which require a different data model; this is not currently supported.

**Plain groups in DDI XML:** `begin_group`/`end_group` blocks without `appearance="table-list"` are not emitted as `<varGrp>` in the XML — their variables appear as standalone `<var>` elements. Groups with `appearance="table-list"` become `<varGrp type="grid">`.

**LimeSurvey `select_multiple` bracket keys:** LimeSurvey truncates option codes to 5 characters in its export (e.g. `metall` → `metal`). The transform recovers the original code via prefix matching. This fails if two choice codes share the same first 5 characters — a `ValueError` is raised in that case. It also fails silently (with a warning) if LimeSurvey uses internal answer codes that have no relation to the schema's choice names.

## Design

The package is split into three:

- `survey2ddi_core/` — source-agnostic engine: XLSForm parser (`xlsform.py`), DDI-Codebook 2.5 emitter (`ddi_xml.py`), DDI reader (`ddi.py`), CSV builder (`data.py`), and shared schema types (`types.py` — `Variable`, `Choice` dataclasses).
- `kobo2ddi/` — KoboToolbox connector (API client + CLI).
- `limesurvey2ddi/` — LimeSurvey connector (API client, TSV schema parser `lstsv.py`, response-normalisation glue `transform.py`, CLI).

Both connectors emit `list[Variable]` through `survey2ddi_core.xlsform.extract_variables`, then feed the same `build_ddi_xml` / `build_data_csv` pipelines. Adding a third source = new `client.py` + a thin `transform.py` mapping to `Variable`.

### As a Python library

```python
from pathlib import Path

# KoboToolbox
from kobo2ddi.client import KoboClient
from survey2ddi_core.data import build_data_csv
from survey2ddi_core.ddi_xml import build_ddi_xml
from survey2ddi_core.xlsform import parse_xlsform, extract_variables

client = KoboClient()
asset = client.get_asset("your_asset_uid")
submissions = client.get_submissions("your_asset_uid")
survey_rows, choices, settings = parse_xlsform(Path("form.xlsx"))
xml_string = build_ddi_xml(asset["name"], survey_rows, choices, settings, submissions)

variables = extract_variables(survey_rows, choices)
csv_string = build_data_csv(variables, submissions)

# LimeSurvey
from limesurvey2ddi.transform import build_data_csv, build_ddi_xml

responses = [...] # from LimeSurvey API
xml_string = build_ddi_xml("My Survey", Path("survey.tsv"), responses)
csv_string = build_data_csv(Path("survey.tsv"), responses)
```


