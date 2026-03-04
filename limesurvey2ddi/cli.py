"""CLI for limesurvey2ddi."""

import argparse
import sys
from pathlib import Path

from limesurvey2ddi.client import LimeSurveyClient


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

    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        sys.exit(1)

    client = LimeSurveyClient(
        server_url=args.server_url,
        username=args.username,
        password=args.password,
    )

    commands = {"list": cmd_list, "pull": cmd_pull, "validate": cmd_validate}
    commands[args.command](client, args)


if __name__ == "__main__":
    main()
