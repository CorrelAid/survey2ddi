# Handover: shrinking survey2ddi to a DDI reader

Audience: whoever (person or agent) picks up the survey2ddi retirement next,
in this repo or in formtransform. This is the plan; each linked issue is written
to stand on its own.

## Why

`survey2ddi_core/{data,ddi_xml,xlsform,notes,types}.py` + `_generated/` (~850
lines) duplicate `@correlaid/formtransform` (`buildDdiXml`, `buildDataCsv`,
`lstsvToDdiXml`). Two reasons this has to be fixed, not left alone:

- **The two implementations have already drifted.** `data.get_canonical_columns` returns
  input order, but `ddi_xml.build_ddi_xml` emits bucketed order (grid →
  `select_multiple` binaries → `_other` → standalone). Any survey with one of
  those gets a CSV header that doesn't match its own XML. formtransform gets it
  right.
- **The registry can't be resynced.** `scripts/sync-registry.sh` clones
  `CorrelAid/survey-type-registry`, which no longer exists, so `_generated/`
  is stuck at `.registry-version` v1.0.0 and `check-registry-drift.sh`
  (first CI step) can't pass on a fresh run.

End state: survey2ddi = `survey2ddi_core/ddi.py` only (`read_variable_labels`,
`read_value_maps`, `apply_value_labels`, already the entire `__all__`). All
conversion and API pulls live in formtransform.

The trade, stated rather than hidden: the ops path (pull + convert) becomes
node-only. **Rejected alternative:** keep the Python CLIs and have them shell
out to the `formtransform` binary. That makes a pip package depend on a node
runtime it can't declare. If ops-in-Python turns out to be a hard requirement,
fall back to it: keep `kobo2ddi` / `limesurvey2ddi` permanently and delete only
the emit core.

## Status of the formtransform side

| Needed for | formtransform issue | State (2026-09-24) |
| --- | --- | --- |
| `kobo2ddi transform` replacement | [#10](https://github.com/CorrelAid/formtransform/issues/10) `xlsform2ddi --data` | PR [#17](https://github.com/CorrelAid/formtransform/pull/17) open |
| `limesurvey2ddi transform` replacement | [#11](https://github.com/CorrelAid/formtransform/issues/11) port `normalize_responses` | not started |
| `kobo2ddi pull/list` replacement | [#12](https://github.com/CorrelAid/formtransform/issues/12) Kobo client | not started |
| `limesurvey2ddi pull/list` replacement | [#13](https://github.com/CorrelAid/formtransform/issues/13) LimeSurvey client | not started |
| keeping qwacback coverage | [#14](https://github.com/CorrelAid/formtransform/issues/14) port `test_conversion_equivalence.py` | not started |

formtransform is **not on the npm registry**. Install it with
`npm install github:CorrelAid/formtransform`, run it with
`npx github:CorrelAid/formtransform`, or use a local checkout's `dist/`.

## Work here, in order

### 1. [#3](https://github.com/CorrelAid/survey2ddi/issues/3): parity gate (can start now)

The script lives in this repo, because it runs the Python emitter and is
deleted along with it. Suggested: `scripts/parity_gate.py`. Keep it out of
`ci.yml`.

- **Inputs.** The XLSForm rows in `tests/conftest.py` (`survey_rows`,
  `choices_by_list`, `settings`, `submissions`). There are no `.xlsx`
  fixtures. Also `examples/basic/` (`responses.json`, `101.csv`, `101.xml`)
  and `tests/fixtures/lstsv/*.tsv` (`all_types`, `basic`, `complex`).
- **Python side:** `survey2ddi_core.ddi_xml.build_ddi_xml`,
  `survey2ddi_core.data.build_data_csv`, and for TSV
  `limesurvey2ddi.transform.build_ddi_xml(title, schema_path, responses)`.
- **TS side: call the library, not the CLI.** Dump the same rows to JSON and
  run a small node script that imports `buildDdiXml`, `buildDataCsv`,
  `extractVariables` and `choicesByListFromRows` from formtransform's
  `dist/index.js`, plus `lstsvToDdiXml` for the TSVs. The reason: the CLI's
  XLSForm loader enforces a strict name subset (alnum ≤20, no underscores).
  Fixture names like `full_name` fail that check, and `--skip-validation`
  renames them, which would show up as false diffs.
- **Pin the non-deterministic parts** on both sides: prod date, dataset
  filename, title.
- **Compare byte-for-byte**, XML and CSV. Sort each difference into
  one of three buckets:
  - **equal**
  - **expected**: CSV column order only (Python uses input order, TS uses
    bucketed order). The TS order is the correct one. Report it, don't fail on it.
  - **finding**: anything else. A behaviour Python has and TS lacks is a
    formtransform bug. File it on `CorrelAid/formtransform` with a minimal
    repro and link it from #3. Don't keep the Python around as a workaround.
- **LimeSurvey CSV can't be compared yet.** It depends on `normalize_responses`
  (formtransform#11). Compare XML only for the TSVs and mark the CSV
  "pending #11".
- Already checked by hand: on a flat survey the two CSVs are byte-equal
  (quoting, CRLF, `None` → empty cell, multi expansion).
- **Done =** results table pasted into #3 plus an explicit go/no-go for step 2.

### 2. [#4](https://github.com/CorrelAid/survey2ddi/issues/4): delete the emit core (gated on #3 = go)

- Delete `survey2ddi_core/{data,ddi_xml,xlsform,notes,types}.py`,
  `_generated/`, `scripts/{sync-registry,check-registry-drift}.sh`,
  `.registry-version`, the registry-drift step in `.github/workflows/ci.yml`,
  and the `openpyxl` / `xlrd` dependencies.
- Delete the tests that only cover the deleted code (`test_ddi_xml.py`,
  `test_data.py`, most of `conftest.py`). Keep `test_ddi_utils.py`.
- `tests/integration/test_conversion_equivalence.py` goes only after
  formtransform#14 has taken over its coverage.
- Keep `survey2ddi_core/ddi.py` and its `__init__` exports.
- **Catch:** `kobo2ddi/cli.py` and `limesurvey2ddi/transform.py` import the
  emit core. Either do this step after step 3's 1.0.0 removal, or have the
  0.6.x CLIs shell out / fail with a pointer to formtransform. Don't ship a
  release with broken imports.

### 3. [#5](https://github.com/CorrelAid/survey2ddi/issues/5): deprecate, then remove, the CLIs (gated on formtransform #10–#13)

- **0.6.0:** `kobo2ddi` and `limesurvey2ddi` still work but emit a
  `DeprecationWarning` naming the replacement (`formtransform xlsform2ddi
  --data`, `formtransform kobo pull`, `formtransform limesurvey pull`).
  `cmd_transform` / `cmd_metadata` repeat it on stderr.
- **1.0.0:** drop both packages, `httpx` and `python-dotenv`,
  `[project.scripts]` and `.env.example`. Update the wheel `packages` to
  `["survey2ddi_core"]`.
- Say plainly in the notice that the pull-and-convert path now needs
  node (`npx github:CorrelAid/formtransform …`, or a subprocess call from Python).
- Env var names (`KOBO_API_TOKEN`, `LIME_SERVER_URL`, `LIME_USERNAME`,
  `LIME_PASSWORD`) don't change in the TS clients, so existing `.env` files
  keep working via `node --env-file`.
- Don't deprecate a command whose replacement isn't on formtransform `main`
  yet.

### 4. [#6](https://github.com/CorrelAid/survey2ddi/issues/6): rewrite the package's story (after #4)

- Rewrite `README.md`, `AI_DISCLOSURE.md`, and the `pyproject.toml`
  description and keywords for a DDI-reader package.
- Check that `examples/basic/analysis_example.ipynb` still runs against the
  checked-in `101.xml` with the emitter gone.
- After that: [cdl-wp-eins#26](https://github.com/CorrelAid/cdl-wp-eins/issues/26)
  retargets the public docs.

## Rules

- **No capability disappears to reach a green build.** If something has no TS
  equivalent yet, stop and say so. Don't delete it.
- **No step 2 without step 1.** Deleting the reference implementation without
  the parity run means trusting it blindly.
- **Fix gaps in formtransform, not here.**
