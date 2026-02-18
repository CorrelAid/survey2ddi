# kobo2ddi

Convert KoboToolbox survey data into DDI-compliant formats.

kobo2ddi pulls survey submissions and the corresponding XLSForm definition from the KoboToolbox API, transforms them into a structured xlsx codebook with separate sheets for variables, data, and study metadata, and generates a DDI-Codebook 2.5 XML file for standards-compliant documentation.

## What it produces

Given a KoboToolbox survey, kobo2ddi outputs two files:

- **`<uid>.xlsx`** -- a human-readable workbook with three sheets:
  - **variables** -- codebook with variable name, group, question text, type, coded value labels, and required flag
  - **data** -- one row per submission, one column per variable, with only survey responses (no Kobo metadata)
  - **survey_info** -- study-level metadata (title, ID, version, language, source, submission count, export date)

- **`<uid>.xml`** -- a valid [DDI-Codebook 2.5](https://ddialliance.org/Specification/DDI-Codebook/2.5/) XML document containing:
  - Study description (`stdyDscr`) with title, ID, version, and production date
  - Variable groups (`varGrp`) matching the XLSForm sections
  - Variable definitions (`var`) with labels, question text, category codes, and format types

The XML validates against the official DDI-Codebook 2.5 XSD schema.

## Setup

Requires Python 3.13+. Install with [uv](https://docs.astral.sh/uv/):

```
uv sync
```

Create a `.env` file (see `.env.example`):

```
KOBO_API_TOKEN=your_token_here
KOBO_SERVER_URL=https://eu.kobotoolbox.org
```

Get your API token from your KoboToolbox account under Account Settings > Security.

## Usage

### List available surveys

```
uv run python -m kobo2ddi list
```

### Pull raw data (submissions + XLSForm)

```
uv run python -m kobo2ddi pull <uid>
```

Saves `submissions.json` and `form.xlsx` to `output/<uid>/`.

### Transform into DDI formats

```
uv run python -m kobo2ddi transform <uid>
```

Pulls data if not already cached, then generates `<uid>.xlsx` and `<uid>.xml` in `output/<uid>/`. Use `--refresh` to re-download from the API.

### As a Python library

```python
from kobo2ddi import KoboClient
from kobo2ddi.transform import parse_xlsform, build_workbook
from kobo2ddi.ddi_xml import build_ddi_xml

client = KoboClient()
asset = client.get_asset("your_uid")
submissions = client.get_submissions("your_uid")
client.download_xlsform("your_uid", Path("form.xlsx"))

survey_rows, choices, settings = parse_xlsform(Path("form.xlsx"))
workbook = build_workbook(asset["name"], survey_rows, choices, settings, submissions)
xml_string = build_ddi_xml(asset["name"], survey_rows, choices, settings, submissions)
```

## Running tests

```
uv run python -m pytest tests/ -v
```

Tests include XSD validation of generated XML against the official DDI-Codebook 2.5 schema (requires `xmllint`, auto-skipped if not available).

## Design

The transform and DDI XML modules are source-agnostic -- they work with parsed survey data (rows, choices, settings) rather than Kobo-specific objects. This means the same output format can be reused for other survey platforms (e.g. Limesurvey) by writing a different adapter that produces the same inputs.
