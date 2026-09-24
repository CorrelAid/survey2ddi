# Handover: retiring survey2ddi

Audience: whoever (person or agent) picks up the survey2ddi retirement next,
in this repo or in formtransform. This is the plan; each linked issue is written
to stand on its own.

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

The trade, stated rather than hidden: the pull-and-convert path becomes
node-only. Anyone scripting a Kobo pull from Python will need
`npx github:CorrelAid/formtransform …` or a `subprocess` call. Say so plainly
in the deprecation notice.

## What replaces what

| survey2ddi today | Replacement | formtransform issue |
| --- | --- | --- |
| `kobo2ddi transform` / `metadata` | `formtransform xlsform2ddi [--data]` | [#10](https://github.com/CorrelAid/formtransform/issues/10) |
| `limesurvey2ddi transform` / `metadata` | `formtransform lstsv2ddi [--data]` | [#11](https://github.com/CorrelAid/formtransform/issues/11) |
| `kobo2ddi list` / `pull` | `formtransform kobo list` / `pull` | [#12](https://github.com/CorrelAid/formtransform/issues/12) |
| `limesurvey2ddi list` / `pull` | `formtransform limesurvey list` / `pull` | [#13](https://github.com/CorrelAid/formtransform/issues/13) |
| `test_conversion_equivalence.py` | same comparison against `buildDdiXml` | [#14](https://github.com/CorrelAid/formtransform/issues/14) |
| `survey2ddi_core.ddi` reader | documented Python snippet | [#15](https://github.com/CorrelAid/formtransform/issues/15) |

Check each issue's state before relying on it. As of 2026-09-24 only #10 was
done.

formtransform is **not on the npm registry**. Install it with
`npm install github:CorrelAid/formtransform`, run it with
`npx github:CorrelAid/formtransform`, or use a local checkout's `dist/`.

Env var names (`KOBO_API_TOKEN`, `LIME_SERVER_URL`, `LIME_USERNAME`,
`LIME_PASSWORD`) don't change in the TS clients, so existing `.env` files
keep working via `node --env-file`.

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
- **LimeSurvey CSV can't be compared yet.** It depends on formtransform#11.
  Compare XML only for the TSVs until then.
- **Done =** results table in #3 plus a go/no-go for step 2.

### 2. [#4](https://github.com/CorrelAid/survey2ddi/issues/4): final release 0.6.0 (gated on #3 and formtransform #10–#13)

- Every entry point still works and emits a `DeprecationWarning` naming the
  exact replacement. For CLI runs, print it on stderr too:
  `kobo2ddi`, `limesurvey2ddi`, and `survey2ddi_core.ddi`'s three functions
  (the last pointing at the formtransform#15 snippet).
- Add a "Retired" notice at the top of the README with the replacement table
  above and the node requirement.
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
