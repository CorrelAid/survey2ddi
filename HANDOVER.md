# Handover: retiring survey2ddi

Audience: whoever (person or agent) picks up the survey2ddi retirement next,
in this repo or in formtransform. This is the plan; each linked issue is written
to stand on its own.

## Status (2026-09-25)

| Step | State |
| --- | --- |
| [#3](https://github.com/CorrelAid/survey2ddi/issues/3) parity gate | **Done: go.** No missing behaviour; one cosmetic finding, [formtransform#75](https://github.com/CorrelAid/formtransform/issues/75) |
| [#4](https://github.com/CorrelAid/survey2ddi/issues/4) release 0.6.0 | Deprecation notices, README notice, CI fix, version bump in [#10](https://github.com/CorrelAid/survey2ddi/pull/10) |
| [#5](https://github.com/CorrelAid/survey2ddi/issues/5) archive | After 0.6.0 is on PyPI |
| formtransform#10, #11, #14, #15 | All closed |

**Decision (2026-09-24): survey2ddi is retired, not shrunk.** Everything it
does moves to [`@correlaid/formtransform`](https://github.com/CorrelAid/formtransform).
The package gets one last release that points every entry point at the
replacement, and then the repo is archived. Nothing is deleted from the code
first. An archived repo doesn't need a tidy tree, and the Python emitter
stays readable as a reference.

## Why

- **The implementations have already drifted.**
  `survey2ddi_core/{data,ddi_xml,xlsform,notes,types}.py` + `_generated/`
  (~850 lines) duplicate formtransform's `buildDdiXml`, `buildDataCsv` and
  `lstsvToDdiXml`. `data.get_canonical_columns` returns input order, but
  `ddi_xml.build_ddi_xml` emits bucketed order (grid → `select_multiple`
  binaries → `_other` → standalone). So any survey with one of those gets a CSV
  header that doesn't match its own XML. formtransform gets it right.
- **The registry can't be resynced.** `scripts/check-registry-drift.sh` (the
  first CI job) clones `CorrelAid/survey-type-registry`, which no longer
  exists. Every fresh CI run fails with `could not read Username for
  'https://github.com'`, and `_generated/` is stuck at `.registry-version`
  v1.0.0.
- **Keeping the reader alone isn't worth a package.** `survey2ddi_core/ddi.py`
  (`read_variable_labels`, `read_value_maps`, `apply_value_labels`) is ~30
  lines of stdlib `xml.etree`. It's replaced by a documented snippet in
  formtransform (formtransform#15), not by a package.

**No API pulls (decided 2026-09-24).** formtransform does conversions only,
and every conversion must also work in the browser, so it ships no Kobo or
LimeSurvey API client. The replacement for `kobo2ddi pull` /
`limesurvey2ddi pull` is the platform's own export step. That's the trade:
state it plainly in the deprecation notice.

## What replaces what

| survey2ddi today | Replacement | formtransform |
| --- | --- | --- |
| `kobo2ddi transform` / `metadata` | `formtransform xlsform2ddi [--data]` | done ([#10](https://github.com/CorrelAid/formtransform/issues/10)) |
| `limesurvey2ddi transform` / `metadata` | `formtransform lstsv2ddi [--data]` | done ([#11](https://github.com/CorrelAid/formtransform/issues/11)) |
| `kobo2ddi list` / `pull` | Kobo's own export: form as XLSForm, data as CSV/JSON with XML values and headers | none needed |
| `limesurvey2ddi list` / `pull` | LimeSurvey's response export with question-code headings and **answer codes** | none needed |
| `test_conversion_equivalence.py` | same comparison against `buildDdiXml` | [#14](https://github.com/CorrelAid/formtransform/issues/14) |
| `survey2ddi_core.ddi` reader | documented Python snippet | [#15](https://github.com/CorrelAid/formtransform/issues/15) |

In the browser the same path is `parseResponses` → `buildDataCsv` /
`lstsvToDataCsv`, all exported from formtransform's `src/index.ts`.

**LimeSurvey: answer codes, not texts.** `limesurvey2ddi/client.py` exports
with `responseType "long"`, which returns answer *labels* (`Ja`, `Yes`,
`Fortgeschritten`; checked against LimeSurvey 6.16). The DDI categories hold
answer *codes*, so survey2ddi's pulled LimeSurvey CSVs never matched their own
codebook. The deprecation notice and formtransform#15 both have to name the
export setting.

formtransform is **not on the npm registry**. Install it with
`npm install github:CorrelAid/formtransform`, run it with
`npx github:CorrelAid/formtransform`, or use a local checkout's `dist/`.

## Work here, in order

### 1. [#3](https://github.com/CorrelAid/survey2ddi/issues/3): parity gate (can start now)

The goal: prove formtransform isn't missing a behaviour before users are sent
to it. The script is temporary, lives in this repo, and is archived with it.
Suggested: `scripts/parity_gate.py`. Keep it out of `ci.yml`.

- **Inputs.** The XLSForm rows in `tests/conftest.py` (`survey_rows`,
  `choices_by_list`, `settings`, `submissions`). There are no `.xlsx`
  fixtures. Also `examples/basic/` (`responses.json`, `101.csv`, `101.xml`)
  and `tests/fixtures/lstsv/*.tsv`.
- **Python side:** `survey2ddi_core.ddi_xml.build_ddi_xml`,
  `survey2ddi_core.data.build_data_csv`, and for TSV
  `limesurvey2ddi.transform.build_ddi_xml(title, schema_path, responses)`.
- **TS side: call the library, not the CLI.** Dump the same rows to JSON and
  run a small node script importing `buildDdiXml`, `buildDataCsv`,
  `extractVariables`, `choicesByListFromRows` and `lstsvToDdiXml` from
  formtransform's `dist/index.js`. The reason: the CLI's XLSForm loader
  enforces a strict name subset (alnum ≤20, no underscores). Fixture names
  like `full_name` fail that check, and `--skip-validation` renames them,
  which would show up as false diffs.
- **Pin the non-deterministic parts** on both sides: prod date, dataset
  filename, title.
- **Compare byte-for-byte**, XML and CSV. Sort each difference into one of
  three buckets:
  - **equal**
  - **expected**: CSV column order only. The TS order is the correct one.
  - **finding**: anything else. File it on `CorrelAid/formtransform` with a
    minimal repro and link it from #3. A Python behaviour missing in TS is a
    formtransform bug.
- **LimeSurvey CSV:** feed both sides the same export rows. Expect TS-only
  improvements, not findings: arrays (`array[sq]`, which Python leaves empty),
  `-oth-` → `other`, and the `<base>_other` companion. Python's
  `normalize_responses` misses all three (see formtransform PR #20).
- **Done =** results table in #3 plus a go/no-go for step 2.

### 2. [#4](https://github.com/CorrelAid/survey2ddi/issues/4): final release 0.6.0 (gated on #3 and formtransform#15)

- Every entry point still works and emits a `DeprecationWarning` naming the
  exact replacement. For CLI runs, print it on stderr too:
  `kobo2ddi`, `limesurvey2ddi`, and `survey2ddi_core.ddi`'s three functions
  (the last pointing at the formtransform#15 snippet).
- Add a "Retired" notice at the top of the README with the replacement table
  above: the export steps for `pull`, and `npx github:CorrelAid/formtransform`
  for the conversion commands.
- Mark `pyproject.toml` `Development Status :: 7 - Inactive`.
- To release, CI must be green. Delete the dead `Registry Drift Check` job
  in `.github/workflows/ci.yml`; it can't pass (see Why).
- Don't yank the earlier PyPI releases: pinned users must keep installing.

### 3. [#5](https://github.com/CorrelAid/survey2ddi/issues/5): archive (after 0.6.0 and formtransform#14)

- Check once more that nothing in the org still depends on survey2ddi:
  `gh search code survey2ddi --owner CorrelAid`. Expect only the docs covered by
  [cdl-wp-eins#26](https://github.com/CorrelAid/cdl-wp-eins/issues/26).
- Close the remaining issues. Put a one-line description on the repo pointing to
  formtransform, then archive it (`gh repo archive CorrelAid/survey2ddi`).

[#6](https://github.com/CorrelAid/survey2ddi/issues/6) (rewrite as a DDI
reader) is closed as not planned. The reader is now covered by formtransform#15.

## Rules

- **No capability disappears without a pointer.** Every entry point's
  deprecation message names its replacement, and that replacement must be on
  formtransform `main` before 0.6.0 ships.
- **No 0.6.0 without #3.** Sending users to formtransform needs the parity run
  behind it.
- **Fix gaps in formtransform, not here.**
