"""CLI for kobo2ddi."""

import argparse
import csv
import json
import sys
from pathlib import Path

from kobo2ddi.client import KoboClient
from kobo2ddi.data import build_data_csv
from kobo2ddi.ddi_xml import build_ddi_xml
from kobo2ddi.transform import extract_variables, parse_xlsform


def cmd_list(make_client, _args: argparse.Namespace) -> None:
    client = make_client()
    assets = client.list_assets()
    if not assets:
        print("No assets found.")
        return
    for a in assets:
        deployed = "deployed" if a.get("has_deployment") else "draft"
        print(f"  {a['uid']}  {deployed:<10}  {a['name']}")


def cmd_pull(make_client, args: argparse.Namespace) -> None:
    output_dir = Path(args.output) if args.output else None
    make_client().pull(args.uid, output_dir=output_dir)


def cmd_transform(make_client, args: argparse.Namespace) -> None:
    output_dir = Path(args.output) if args.output else Path("output")
    uid = args.uid
    asset_dir = output_dir / uid
    form_path = asset_dir / "form.xlsx"
    submissions_path = asset_dir / "submissions.json"

    # Load submissions from CSV or JSON
    if args.data:
        csv_path = Path(args.data)
        if not csv_path.exists():
            print(f"Error: {csv_path} not found.")
            sys.exit(1)
        with open(csv_path, encoding="utf-8-sig") as f:
            submissions = list(csv.DictReader(f, delimiter=";"))
            # Fallback to comma if semicolon didn't work (headers should have /)
            if not submissions or not any("/" in k for k in submissions[0].keys()):
                f.seek(0)
                submissions = list(csv.DictReader(f, delimiter=","))
    else:
        needs_pull = args.refresh or not form_path.exists() or not submissions_path.exists()
        if needs_pull:
            make_client().pull(uid, output_dir=output_dir)
        submissions = json.loads(submissions_path.read_text())

    survey_rows, choices_by_list, settings = parse_xlsform(form_path)

    if args.title:
        title = args.title
    else:
        title = make_client().get_asset(uid)["name"]

    # Build and save DDI-Codebook 2.5 XML
    xml_str = build_ddi_xml(
        title,
        survey_rows,
        choices_by_list,
        settings,
        submissions,
        dataset_filename=f"{uid}.csv",
    )
    xml_path = asset_dir / f"{uid}.xml"
    xml_path.write_text(xml_str, encoding="utf-8")
    print(f"Wrote {xml_path}")

    # Build and save DDI-aligned response CSV
    variables = extract_variables(survey_rows, choices_by_list)
    csv_str = build_data_csv(variables, submissions)
    csv_path = asset_dir / f"{uid}.csv"
    csv_path.write_text(csv_str, encoding="utf-8")
    print(f"Wrote {csv_path}")


def cmd_metadata(_make_client, args: argparse.Namespace) -> None:
    form_path = Path(args.form)
    if not form_path.exists():
        print(f"Error: {form_path} not found.")
        sys.exit(1)

    survey_rows, choices_by_list, settings = parse_xlsform(form_path)
    title = args.title or form_path.stem

    xml_str = build_ddi_xml(
        title,
        survey_rows,
        choices_by_list,
        settings,
        [],
    )

    out_path = Path(args.output) if args.output else form_path.with_suffix(".xml")
    out_path.write_text(xml_str, encoding="utf-8")
    print(f"Wrote {out_path}")


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

    transform_p = sub.add_parser("transform", help="Pull + emit DDI XML and CSV")
    transform_p.add_argument("uid", help="Asset UID")
    transform_p.add_argument("-o", "--output", help="Output directory (default: ./output)")
    transform_p.add_argument(
        "--refresh", action="store_true", help="Re-download data even if cached"
    )
    transform_p.add_argument(
        "--title",
        help="Survey title (skips API call when form.xlsx + submissions.json are cached)",
    )
    transform_p.add_argument(
        "--data",
        help="Path to raw Kobo CSV export (must use XML values and headers)",
    )

    meta_p = sub.add_parser(
        "metadata",
        help="Emit DDI XML from an XLSForm only (no responses, no API call)",
    )
    meta_p.add_argument("form", help="Path to form.xlsx")
    meta_p.add_argument("--title", help="Survey title (default: form filename stem)")
    meta_p.add_argument("-o", "--output", help="Output XML path (default: <form>.xml)")

    args = parser.parse_args(argv)
    if not args.command:
        parser.print_help()
        sys.exit(1)

    cached_client: list[KoboClient] = []

    def make_client() -> KoboClient:
        if not cached_client:
            cached_client.append(
                KoboClient(token=args.token, server_url=args.server_url)
            )
        return cached_client[0]

    commands = {
        "list": cmd_list,
        "pull": cmd_pull,
        "transform": cmd_transform,
        "metadata": cmd_metadata,
    }
    commands[args.command](make_client, args)


if __name__ == "__main__":
    main()
