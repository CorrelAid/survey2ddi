# survey2ddi

Convert survey data from KoboToolbox or LimeSurvey into DDI-compliant formats.

Given a survey, survey2ddi outputs two files:

- **`<id>.xlsx`** — a human-readable workbook with three sheets:
  - **variables** — codebook with variable name, group, question text, type, value labels, and measurement level
  - **data** — one row per submission, one column per variable
  - **survey_info** — study-level metadata (title, ID, version, language, source, submission count, export date)

- **`<id>.xml`** — a valid [DDI-Codebook 2.5](https://ddialliance.org/Specification/DDI-Codebook/2.5/) XML document

## Setup

Requires Python 3.13+. Install with [uv](https://docs.astral.sh/uv/):

```
uv sync
```

Copy `.env.example` to `.env` and fill in your credentials (see the relevant section below).

## KoboToolbox

### Credentials

```
KOBO_API_TOKEN=your_token_here
KOBO_SERVER_URL=https://eu.kobotoolbox.org
```

Get your API token from KoboToolbox account settings under **Account Settings → Security**.

### Usage

```
# List available surveys
uv run python -m kobo2ddi list

# Download submissions + XLSForm
uv run python -m kobo2ddi pull <asset_uid>

# Transform into DDI formats (pulls if not cached)
uv run python -m kobo2ddi transform <asset_uid>
```

The asset UID is an 11-character alphanumeric string (e.g. `aXkQm3nBpL9`) visible in the KoboToolbox URL and in the output of `list`.

`pull` saves `submissions.json` and `form.xlsx` to `output/<asset_uid>/`.
`transform` generates `<asset_uid>.xlsx` and `<asset_uid>.xml` in the same directory. Use `--refresh` to re-download from the API.

## LimeSurvey

### Credentials

```
LIME_SERVER_URL=https://your-limesurvey-instance.org
LIME_USERNAME=your_username
LIME_PASSWORD=your_password
```

### Usage

```
# List available surveys
uv run python -m limesurvey2ddi list

# Download responses
uv run python -m limesurvey2ddi pull <survey_id>

# Place the XLSForm export as output/<survey_id>/form.xlsx, then transform
uv run python -m limesurvey2ddi transform <survey_id> --title "My Survey"
```

The survey ID is a numeric integer (e.g. `322836`) shown in the LimeSurvey admin URL and in the output of `list`.

`pull` saves `responses.json` to `output/<survey_id>/`. Unlike KoboToolbox, the XLSForm cannot be downloaded automatically — export it manually from LimeSurvey and place it as `output/<survey_id>/form.xlsx`.

`transform` generates `<survey_id>.xlsx` and `<survey_id>.xml`. `--title` sets the study title in the output (defaults to the survey ID if omitted).

You can also validate that `form.xlsx` and `responses.json` match before transforming:

```
uv run python -m limesurvey2ddi validate <survey_id>
```

## Running tests

```
uv run python -m pytest tests/ -v
```

Tests include XSD validation of generated XML against the official DDI-Codebook 2.5 schema (requires `xmllint`, auto-skipped if not available).

## Validating XML manually

```
xmllint --noout --schema tests/schemas/codebook.xsd output/<id>/<id>.xml
```

The schema files in `tests/schemas/` are the official DDI-Codebook 2.5 XSD from the [DDI Alliance](https://ddialliance.org/Specification/DDI-Codebook/2.5/).

## Known limitations

**Multi-language forms:** Only the first `label::*` column in the XLSForm is used. For bilingual forms, place the preferred language column first.

**Repeat groups:** Variables inside `begin_repeat`/`end_repeat` blocks are silently skipped. KoboToolbox stores repeat data as nested arrays which require a different data model; this is not currently supported.

**LimeSurvey `select_multiple` bracket keys:** LimeSurvey truncates option codes to 5 characters in its export (e.g. `metall` → `metal`). The transform recovers the original code via prefix matching. This fails if two choice codes share the same first 5 characters — a `ValueError` is raised in that case. It also fails silently (with a warning) if LimeSurvey uses internal answer codes that have no relation to the XLSForm choice names; this can happen for surveys not originally created from an XLSForm.

## Design

The transform and DDI XML modules (`kobo2ddi/transform.py`, `kobo2ddi/ddi_xml.py`) are source-agnostic — they work with parsed XLSForm data rather than platform-specific objects. The LimeSurvey adapter (`limesurvey2ddi/transform.py`) normalises LimeSurvey's export quirks (underscore stripping, `select_multiple` sub-columns) before passing data to the same core functions.

### As a Python library

```python
# KoboToolbox
from kobo2ddi import KoboClient
from kobo2ddi.transform import parse_xlsform, build_workbook
from kobo2ddi.ddi_xml import build_ddi_xml

client = KoboClient()
asset = client.get_asset("your_asset_uid")
submissions = client.get_submissions("your_asset_uid")
client.download_xlsform("your_asset_uid", Path("form.xlsx"))
survey_rows, choices, settings = parse_xlsform(Path("form.xlsx"))
workbook = build_workbook(asset["name"], survey_rows, choices, settings, submissions)
xml_string = build_ddi_xml(asset["name"], survey_rows, choices, settings, submissions)

# LimeSurvey
from limesurvey2ddi import LimeSurveyClient
from limesurvey2ddi.transform import build_workbook, build_ddi_xml

client = LimeSurveyClient()
responses = client.get_responses(322836)
workbook = build_workbook("My Survey", Path("form.xlsx"), responses)
xml_string = build_ddi_xml("My Survey", Path("form.xlsx"), responses)
```
