"""CLI for limesurvey2ddi."""

import argparse
import json
import sys
from pathlib import Path

from limesurvey2ddi.client import LimeSurveyClient
from limesurvey2ddi.transform import build_ddi_xml, build_workbook


def cmd_list(client: LimeSurveyClient, _args: argparse.Namespace) -> None:
    surveys = client.list_surveys()
    if not surveys:
        print("No surveys found.")
        return
    for s in surveys:
        active = "active" if s.get("active") == "Y" else "inactive"
        print(f"  {s['sid']}  {active:<10}  {s['surveyls_title']}")


def cmd_pull(client: LimeSurveyClient, args: argparse.Namespace) -> None:
    output_dir = Path(args.output) if args.output else None
    client.pull(int(args.survey_id), output_dir=output_dir)


def cmd_transform(client: LimeSurveyClient, args: argparse.Namespace) -> None:
    output_dir = Path(args.output) if args.output else Path("output")
    survey_id = int(args.survey_id)
    survey_dir = output_dir / str(survey_id)
    form_path = survey_dir / "form.xlsx"
    responses_path = survey_dir / "responses.json"

    if not form_path.exists():
        print(f"Error: {form_path} not found. Place your XLSForm export there.")
        sys.exit(1)
    if not responses_path.exists():
        print(f"Error: {responses_path} not found. Run 'pull' first.")
        sys.exit(1)

    responses = json.loads(responses_path.read_text())
    title = args.title or str(survey_id)

    wb = build_workbook(title, form_path, responses)
    xlsx_path = survey_dir / f"{survey_id}.xlsx"
    wb.save(xlsx_path)
    print(f"Wrote {xlsx_path}")

    xml_str = build_ddi_xml(title, form_path, responses)
    xml_path = survey_dir / f"{survey_id}.xml"
    xml_path.write_text(xml_str, encoding="utf-8")
    print(f"Wrote {xml_path}")


def cmd_validate(client: LimeSurveyClient, args: argparse.Namespace) -> None:
    output_dir = Path(args.output) if args.output else None
    ok = client.validate(int(args.survey_id), output_dir=output_dir)
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

    transform_p = sub.add_parser("transform", help="Transform into DDI xlsx + XML")
    transform_p.add_argument("survey_id", help="Numeric survey ID")
    transform_p.add_argument("--title", help="Survey title (default: survey ID)")
    transform_p.add_argument("-o", "--output", help="Output directory (default: ./output)")

    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        sys.exit(1)

    client = LimeSurveyClient(
        server_url=args.server_url,
        username=args.username,
        password=args.password,
    )

    commands = {"list": cmd_list, "pull": cmd_pull, "validate": cmd_validate, "transform": cmd_transform}
    commands[args.command](client, args)


if __name__ == "__main__":
    main()
