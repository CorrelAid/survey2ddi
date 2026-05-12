"""CLI for limesurvey2ddi."""

import argparse
import csv
import json
import sys
from pathlib import Path

from limesurvey2ddi.client import LimeSurveyClient
from limesurvey2ddi.transform import (
    build_data_csv,
    build_data_csv_from_lstsv,
    build_ddi_xml,
    build_ddi_xml_from_lstsv,
)


def cmd_list(make_client, _args: argparse.Namespace) -> None:
    surveys = make_client().list_surveys()
    if not surveys:
        print("No surveys found.")
        return
    for s in surveys:
        active = "active" if s.get("active") == "Y" else "inactive"
        print(f"  {s['sid']}  {active:<10}  {s['surveyls_title']}")


def cmd_pull(make_client, args: argparse.Namespace) -> None:
    output_dir = Path(args.output) if args.output else None
    make_client().pull(int(args.survey_id), output_dir=output_dir)


def cmd_transform(_make_client, args: argparse.Namespace) -> None:
    output_dir = Path(args.output) if args.output else Path("output")
    survey_id = int(args.survey_id)
    survey_dir = output_dir / str(survey_id)

    # Load responses from CSV or JSON
    if args.data:
        csv_path = Path(args.data)
        if not csv_path.exists():
            print(f"Error: {csv_path} not found.")
            sys.exit(1)
        with open(csv_path, encoding="utf-8-sig") as f:
            responses = list(csv.DictReader(f, delimiter=";"))
            # Fallback to comma if semicolon didn't work (check for common headers)
            if not responses or not any("[" in k or k.lower() == "id" for k in responses[0].keys()):
                f.seek(0)
                responses = list(csv.DictReader(f, delimiter=","))
    else:
        responses_path = survey_dir / "responses.json"
        if not responses_path.exists():
            print(f"Error: {responses_path} not found. Run 'pull' first.")
            sys.exit(1)
        responses = json.loads(responses_path.read_text())

    # Determine schema source
    schema_path = None
    if args.schema:
        schema_path = Path(args.schema)
    else:
        # Default fallback chain
        xlsx_path = survey_dir / "form.xlsx"
        tsv_path = survey_dir / "survey.tsv"
        if xlsx_path.exists():
            schema_path = xlsx_path
        elif tsv_path.exists():
            schema_path = tsv_path

    if not schema_path or not schema_path.exists():
        print(
            f"Error: No schema found in {survey_dir}. "
            "Place form.xlsx or survey.tsv there, or use --schema."
        )
        sys.exit(1)

    title = args.title or str(survey_id)

    if schema_path.suffix.lower() == ".tsv":
        xml_str = build_ddi_xml_from_lstsv(
            title, schema_path, responses, dataset_filename=f"{survey_id}.csv"
        )
        csv_str = build_data_csv_from_lstsv(schema_path, responses)
    else:
        # Assume XLSX
        xml_str = build_ddi_xml(
            title, schema_path, responses, dataset_filename=f"{survey_id}.csv"
        )
        csv_str = build_data_csv(schema_path, responses)

    xml_path = survey_dir / f"{survey_id}.xml"
    xml_path.write_text(xml_str, encoding="utf-8")
    print(f"Wrote {xml_path}")

    csv_path = survey_dir / f"{survey_id}.csv"
    csv_path.write_text(csv_str, encoding="utf-8")
    print(f"Wrote {csv_path}")


def cmd_validate(make_client, args: argparse.Namespace) -> None:
    output_dir = Path(args.output) if args.output else None
    ok = make_client().validate(int(args.survey_id), output_dir=output_dir)
    if not ok:
        sys.exit(1)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="limesurvey2ddi", description="LimeSurvey → DDI"
    )
    parser.add_argument("--server-url", help="Server URL (overrides LIME_SERVER_URL)")
    parser.add_argument("--username", help="Username (overrides LIME_USERNAME)")
    parser.add_argument("--password", help="Password (overrides LIME_PASSWORD)")

    sub = parser.add_subparsers(dest="command")

    sub.add_parser("list", help="List available surveys")

    pull_p = sub.add_parser("pull", help="Download survey responses")
    pull_p.add_argument("survey_id", help="Numeric survey ID")
    pull_p.add_argument("-o", "--output", help="Output directory (default: ./output)")

    val_p = sub.add_parser("validate", help="Check form.xlsx matches responses.json")
    val_p.add_argument("survey_id", help="Numeric survey ID")
    val_p.add_argument("-o", "--output", help="Output directory (default: ./output)")

    transform_p = sub.add_parser("transform", help="Transform into DDI XML + CSV")
    transform_p.add_argument("survey_id", help="Numeric survey ID")
    transform_p.add_argument("--title", help="Survey title (default: survey ID)")
    transform_p.add_argument(
        "--schema", help="Path to schema file (form.xlsx or survey.tsv)"
    )
    transform_p.add_argument(
        "--data", help="Path to raw LimeSurvey CSV export (must use question codes)"
    )
    transform_p.add_argument("-o", "--output", help="Output directory (default: ./output)")

    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        sys.exit(1)

    cached_client: list[LimeSurveyClient] = []

    def make_client() -> LimeSurveyClient:
        if not cached_client:
            cached_client.append(
                LimeSurveyClient(
                    server_url=args.server_url,
                    username=args.username,
                    password=args.password,
                )
            )
        return cached_client[0]

    commands = {
        "list": cmd_list,
        "pull": cmd_pull,
        "validate": cmd_validate,
        "transform": cmd_transform,
    }
    commands[args.command](make_client, args)


if __name__ == "__main__":
    main()
