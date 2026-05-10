"""Command-line entry point for the ICE detention pipeline.

Examples (run from the project root, with the virtualenv activated):

  # 1) extract every workbook in the input directory to slim per-FY CSVs
  python -m ice_pipeline.cli extract --input-dir "C:\\Users\\xief\\Downloads"

  # 2) build the facility crosswalk (auto state + flags, blank counties)
  python -m ice_pipeline.cli crosswalk

  # 3) aggregate detention counts to the county-year and county-month panels
  python -m ice_pipeline.cli aggregate

  # ...or run all three in sequence
  python -m ice_pipeline.cli all --input-dir "C:\\Users\\xief\\Downloads"
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from . import aggregate as agg_mod
from . import config
from . import crosswalk as cw_mod
from . import encounters as enc_mod
from . import extract as ex_mod


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def _cmd_extract(args: argparse.Namespace) -> int:
    input_dir = Path(args.input_dir)
    out_dir = Path(args.out_dir or config.INTERIM_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)

    files = ex_mod.discover_inputs(input_dir)
    if not files:
        print(
            f"No files matching *Detentions_FY*.xlsx found under {input_dir}",
            file=sys.stderr,
        )
        return 2

    print(f"Found {len(files)} workbook(s) to extract:")
    for f in files:
        print(f"  - {f.name}")

    only = set(int(y) for y in args.only) if args.only else None
    skipped = 0
    for f in files:
        fy = ex_mod.fiscal_year_from_filename(f)
        if only and fy not in only:
            continue
        out_path = out_dir / f"fy{fy}_detentions.csv.gz"
        if out_path.exists() and not args.force:
            print(f"  [skip] {out_path.name} already exists (use --force to overwrite)")
            skipped += 1
            continue
        stats = ex_mod.extract_workbook(f, out_path, gzip_output=True)
        print(
            f"  [done] FY{stats['fiscal_year']}: "
            f"{stats['rows_written']:,} rows -> {out_path.name}"
        )
    print(f"Extraction complete. Skipped {skipped} existing file(s).")
    return 0


def _cmd_crosswalk(args: argparse.Namespace) -> int:
    stats = cw_mod.build_crosswalk(
        interim_dir=Path(args.interim_dir or config.INTERIM_DIR),
        fips_csv=Path(args.fips_csv) if args.fips_csv else None,
        overrides_csv=Path(args.overrides_csv) if args.overrides_csv else None,
        out_dir=Path(args.out_dir or config.PROCESSED_DIR),
        refs_dir=Path(args.refs_dir or config.REFERENCES_DIR),
    )
    print("Crosswalk build complete.")
    print(f"  facilities total       : {stats['n_facilities']:,}")
    print(f"  with resolved county   : {stats['n_with_county']:,}")
    print(f"  flagged unusual        : {stats['n_unusual']:,}")
    print(f"  needs review (no county or unusual): {stats['n_needs_review']:,}")
    print(f"  -> {stats['crosswalk_path']}")
    print(f"  -> {stats['review_path']}")
    print(f"  -> {stats['template_path']}  (edit this and rerun crosswalk)")
    return 0


def _cmd_aggregate(args: argparse.Namespace) -> int:
    stats = agg_mod.aggregate(
        interim_dir=Path(args.interim_dir or config.INTERIM_DIR),
        crosswalk_csv=Path(args.crosswalk_csv) if args.crosswalk_csv else None,
        out_dir=Path(args.out_dir or config.PROCESSED_DIR),
    )
    print("Aggregation complete.")
    print(f"  county-year rows : {stats['year_panel_rows']:,}")
    print(f"  county-month rows: {stats['month_panel_rows']:,}")
    print(f"  unmapped facility rows: {stats['unmapped_rows']:,}")
    print(f"  -> {stats['year_panel_path']}")
    print(f"  -> {stats['month_panel_path']}")
    print(f"  -> {stats['unmapped_path']}")
    return 0


def _cmd_all(args: argparse.Namespace) -> int:
    # Each step has a different default output location (interim vs.
    # processed), so we deliberately do not let the user pin them together
    # via a single --out-dir on the `all` command. Run the steps individually
    # if you need bespoke paths.
    args.out_dir = None
    rc = _cmd_extract(args)
    if rc != 0:
        return rc
    rc = _cmd_crosswalk(args)
    if rc != 0:
        return rc
    return _cmd_aggregate(args)


# --- Encounters commands ----------------------------------------------------

def _cmd_extract_encounters(args: argparse.Namespace) -> int:
    input_dir = Path(args.input_dir)
    out_dir = Path(args.out_dir or config.INTERIM_DIR)
    out_dir.mkdir(parents=True, exist_ok=True)

    files = ex_mod.discover_encounters(input_dir)
    if not files:
        print(
            f"No files matching '{config.ENCOUNTERS_FILENAME_GLOB}' under {input_dir}",
            file=sys.stderr,
        )
        return 2

    print(f"Found {len(files)} encounters workbook(s):")
    for f in files:
        print(f"  - {f.name}")

    for f in files:
        out_path = out_dir / f"encounters_{f.stem.replace(' ', '_')}.csv.gz"
        if out_path.exists() and not args.force:
            print(f"  [skip] {out_path.name} already exists (use --force to overwrite)")
            continue
        stats = ex_mod.extract_encounters_workbook(f, out_path, gzip_output=True)
        per_sheet = ", ".join(f"{k}={v:,}" for k, v in stats["per_sheet"].items())
        print(
            f"  [done] {f.name}: {stats['rows_written']:,} rows total "
            f"({per_sheet}) -> {out_path.name}"
        )
    return 0


def _cmd_crosswalk_encounters(args: argparse.Namespace) -> int:
    stats = enc_mod.build_site_crosswalk(
        interim_dir=Path(args.interim_dir or config.INTERIM_DIR),
        fips_csv=Path(args.fips_csv) if args.fips_csv else None,
        overrides_csv=Path(args.overrides_csv) if args.overrides_csv else None,
        out_dir=Path(args.out_dir or config.PROCESSED_DIR),
        refs_dir=Path(args.refs_dir or config.REFERENCES_DIR),
    )
    print("Encounters site crosswalk build complete.")
    print(f"  sites total            : {stats['n_sites']:,}")
    print(f"  with resolved county   : {stats['n_with_county']:,}")
    print(f"  flagged unusual        : {stats['n_unusual']:,}")
    print(f"  needs review           : {stats['n_needs_review']:,}")
    print(f"  -> {stats['crosswalk_path']}")
    print(f"  -> {stats['review_path']}")
    print(f"  -> {stats['template_path']}  (edit -> rerun crosswalk-encounters)")
    return 0


def _cmd_aggregate_encounters(args: argparse.Namespace) -> int:
    stats = enc_mod.aggregate(
        interim_dir=Path(args.interim_dir or config.INTERIM_DIR),
        crosswalk_csv=Path(args.crosswalk_csv) if args.crosswalk_csv else None,
        out_dir=Path(args.out_dir or config.PROCESSED_DIR),
    )
    print("Encounters aggregation complete.")
    print(f"  county-year rows  : {stats['year_panel_rows']:,}")
    print(f"  county-month rows : {stats['month_panel_rows']:,}")
    print(f"  unmapped sites    : {stats['unmapped_rows']:,}")
    print(f"  -> {stats['year_panel_path']}")
    print(f"  -> {stats['month_panel_path']}")
    print(f"  -> {stats['unmapped_path']}")
    return 0


def _cmd_all_encounters(args: argparse.Namespace) -> int:
    args.out_dir = None
    rc = _cmd_extract_encounters(args)
    if rc != 0:
        return rc
    rc = _cmd_crosswalk_encounters(args)
    if rc != 0:
        return rc
    return _cmd_aggregate_encounters(args)


def _cmd_everything(args: argparse.Namespace) -> int:
    """Run the detention pipeline AND the encounters pipeline."""
    rc = _cmd_all(args)
    if rc != 0:
        return rc
    return _cmd_all_encounters(args)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ice-pipeline",
        description=(
            "ICE FOIA detention pipeline: extract -> crosswalk -> aggregate."
        ),
    )
    p.add_argument("-v", "--verbose", action="store_true",
                   help="DEBUG-level logging")
    sub = p.add_subparsers(dest="command", required=True)

    # extract
    e = sub.add_parser("extract", help="stream xlsx workbooks to per-FY CSVs")
    e.add_argument("--input-dir", required=True,
                   help="directory containing *Detentions_FY*.xlsx files")
    e.add_argument("--out-dir", default=None,
                   help=f"per-FY output dir (default: {config.INTERIM_DIR})")
    e.add_argument("--only", nargs="*", default=None,
                   help="restrict to specific 4-digit fiscal years (e.g. 2015 2016)")
    e.add_argument("--force", action="store_true",
                   help="overwrite existing per-FY CSVs")
    e.set_defaults(func=_cmd_extract)

    # crosswalk
    c = sub.add_parser("crosswalk", help="build facility -> state/county crosswalk")
    c.add_argument("--interim-dir", default=None)
    c.add_argument("--fips-csv", default=None,
                   help="FIPS state-county CSV (default: references/fips*.csv)")
    c.add_argument("--overrides-csv", default=None,
                   help="curated overrides CSV (default: references/facility_overrides.csv)")
    c.add_argument("--out-dir", default=None)
    c.add_argument("--refs-dir", default=None)
    c.set_defaults(func=_cmd_crosswalk)

    # aggregate
    a = sub.add_parser("aggregate", help="join crosswalk and roll up to county")
    a.add_argument("--interim-dir", default=None)
    a.add_argument("--crosswalk-csv", default=None)
    a.add_argument("--out-dir", default=None)
    a.set_defaults(func=_cmd_aggregate)

    # all (detention pipeline)
    all_p = sub.add_parser("all", help="extract + crosswalk + aggregate, in order (detention files)")
    all_p.add_argument("--input-dir", required=True)
    all_p.add_argument("--interim-dir", default=None)
    all_p.add_argument("--fips-csv", default=None)
    all_p.add_argument("--overrides-csv", default=None)
    all_p.add_argument("--crosswalk-csv", default=None)
    all_p.add_argument("--refs-dir", default=None)
    all_p.add_argument("--only", nargs="*", default=None)
    all_p.add_argument("--force", action="store_true")
    all_p.set_defaults(func=_cmd_all)

    # extract-encounters
    ee = sub.add_parser(
        "extract-encounters",
        help="stream the ERO Encounters workbook(s) to a per-period CSV",
    )
    ee.add_argument("--input-dir", required=True)
    ee.add_argument("--out-dir", default=None)
    ee.add_argument("--force", action="store_true")
    ee.set_defaults(func=_cmd_extract_encounters)

    # crosswalk-encounters
    ce = sub.add_parser(
        "crosswalk-encounters",
        help="build the encounter-site crosswalk",
    )
    ce.add_argument("--interim-dir", default=None)
    ce.add_argument("--fips-csv", default=None)
    ce.add_argument(
        "--overrides-csv",
        default=None,
        help="curated overrides (default: references/site_overrides.csv)",
    )
    ce.add_argument("--out-dir", default=None)
    ce.add_argument("--refs-dir", default=None)
    ce.set_defaults(func=_cmd_crosswalk_encounters)

    # aggregate-encounters
    ae = sub.add_parser(
        "aggregate-encounters",
        help="join encounter-site crosswalk and roll up to county",
    )
    ae.add_argument("--interim-dir", default=None)
    ae.add_argument("--crosswalk-csv", default=None)
    ae.add_argument("--out-dir", default=None)
    ae.set_defaults(func=_cmd_aggregate_encounters)

    # all-encounters
    ae_all = sub.add_parser(
        "all-encounters",
        help="extract-encounters + crosswalk-encounters + aggregate-encounters",
    )
    ae_all.add_argument("--input-dir", required=True)
    ae_all.add_argument("--interim-dir", default=None)
    ae_all.add_argument("--fips-csv", default=None)
    ae_all.add_argument("--overrides-csv", default=None)
    ae_all.add_argument("--crosswalk-csv", default=None)
    ae_all.add_argument("--refs-dir", default=None)
    ae_all.add_argument("--force", action="store_true")
    ae_all.set_defaults(func=_cmd_all_encounters)

    # everything (both pipelines back to back)
    every = sub.add_parser(
        "everything",
        help="run the full detention pipeline AND the encounters pipeline",
    )
    every.add_argument("--input-dir", required=True)
    every.add_argument("--interim-dir", default=None)
    every.add_argument("--fips-csv", default=None)
    every.add_argument("--overrides-csv", default=None)
    every.add_argument("--crosswalk-csv", default=None)
    every.add_argument("--refs-dir", default=None)
    every.add_argument("--only", nargs="*", default=None)
    every.add_argument("--force", action="store_true")
    every.set_defaults(func=_cmd_everything)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    _setup_logging(args.verbose)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
