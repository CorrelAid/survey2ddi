// TS half of the parity gate (#3). Called by scripts/parity_gate.py; not for CI.
//
//   node scripts/parity_gate.mjs <formtransform-dist-dir> <jobs.json>
//
// Reads the jobs the Python side wrote, runs formtransform's library (not its
// CLI: the CLI's XLSForm name check would rename fixture names like
// `full_name`), and prints {case: {xml, csv}} as JSON on stdout.

import { readFileSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { pathToFileURL } from 'node:url';

const [distDir, jobsPath] = process.argv.slice(2);
const ft = await import(pathToFileURL(join(resolve(distDir), 'index.js')).href);
const jobs = JSON.parse(readFileSync(jobsPath, 'utf8'));

const out = {};
for (const job of jobs) {
  const ddiOpts = {
    assetName: job.title,
    prodDate: job.prodDate,
    datasetFilename: job.datasetFilename,
    submissions: job.submissions,
  };
  try {
    if (job.kind === 'xlsform') {
      const variables = ft.extractVariables(
        job.surveyRows,
        ft.normalizeChoices(job.choices),
      );
      out[job.name] = {
        xml: ft.buildDdiXml(job.surveyRows, job.choices, {
          ...ddiOpts,
          settings: job.settings,
        }),
        csv: ft.buildDataCsv(variables, job.submissions),
      };
    } else {
      // A TSV outside the registry subset is rejected on purpose. Record the
      // rejection, then compare the rest with the check skipped.
      let rejected;
      try {
        ft.lstsvToDdiXml(job.tsv, ddiOpts);
      } catch (err) {
        rejected = err.message;
      }
      const skip = { skipValidation: rejected !== undefined };
      out[job.name] = {
        rejected,
        xml: ft.lstsvToDdiXml(job.tsv, { ...ddiOpts, ...skip }),
        csv: ft.lstsvToDataCsv(job.tsv, job.submissions, skip),
      };
    }
  } catch (err) {
    out[job.name] = { error: String(err?.stack ?? err) };
  }
}
process.stdout.write(JSON.stringify(out));
