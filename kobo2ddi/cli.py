"""CLI for kobo2ddi."""

import argparse
import json
import sys
from pathlib import Path

from kobo2ddi.client import KoboClient
from kobo2ddi.ddi_xml import build_ddi_xml
from kobo2ddi.transform import build_workbook, parse_xlsform


def cmd_list(client: KoboClient, _args: argparse.Namespace) -> None:
    assets = client.list_assets()
    if not assets:
        print("No assets found.")
        return
    for a in assets:
        deployed = "deployed" if a.get("has_deployment") else "draft"
        print(f"  {a['uid']}  {deployed:<10}  {a['name']}")


def cmd_pull(client: KoboClient, args: argparse.Namespace) -> None:
    output_dir = Path(args.output) if args.output else None
    client.pull(args.uid, output_dir=output_dir)


def cmd_transform(client: KoboClient, args: argparse.Namespace) -> None:
    output_dir = Path(args.output) if args.output else Path("output")
    uid = args.uid
    asset_dir = output_dir / uid
    form_path = asset_dir / "form.xlsx"
    submissions_path = asset_dir / "submissions.json"

    # Pull data if not already present (or if --refresh)
    if args.refresh or not form_path.exists() or not submissions_path.exists():
        client.pull(uid, output_dir=output_dir)

    # Load data
    asset = client.get_asset(uid)
    submissions = json.loads(submissions_path.read_text())
    survey_rows, choices_by_list, settings = parse_xlsform(form_path)

    # Build and save xlsx
    wb = build_workbook(asset["name"], survey_rows, choices_by_list, settings, submissions)
    xlsx_path = asset_dir / f"{uid}.xlsx"
    wb.save(xlsx_path)
    print(f"Wrote {xlsx_path}")

    # Build and save DDI-Codebook 2.5 XML
    xml_str = build_ddi_xml(asset["name"], survey_rows, choices_by_list, settings, submissions)
    xml_path = asset_dir / f"{uid}.xml"
    xml_path.write_text(xml_str, encoding="utf-8")
    print(f"Wrote {xml_path}")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="kobo2ddi", description="KoboToolbox → DDI")
    parser.add_argument("--token", help="API token (overrides KOBO_API_TOKEN env var)")
    parser.add_argument(
        "--server-url", help="Server URL (overrides KOBO_SERVER_URL env var)"
    )

    sub = parser.add_subparsers(dest="command")

    sub.add_parser("list", help="List available surveys")

    pull_p = sub.add_parser("pull", help="Download submissions + XLSForm")
    pull_p.add_argument("uid", help="Asset UID")
    pull_p.add_argument("-o", "--output", help="Output directory (default: ./output)")

    transform_p = sub.add_parser("transform", help="Pull + transform into DDI xlsx")
    transform_p.add_argument("uid", help="Asset UID")
    transform_p.add_argument("-o", "--output", help="Output directory (default: ./output)")
    transform_p.add_argument(
        "--refresh", action="store_true", help="Re-download data even if cached"
    )

    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        sys.exit(1)

    client = KoboClient(token=args.token, server_url=args.server_url)

    commands = {"list": cmd_list, "pull": cmd_pull, "transform": cmd_transform}
    commands[args.command](client, args)


if __name__ == "__main__":
    main()
