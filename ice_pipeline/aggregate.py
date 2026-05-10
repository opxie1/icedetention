"""Join the facility crosswalk to the per-FY extracts and roll up to county.

Produces three tidy panels under ``data/processed/``:

  * ``county_year_panel.csv``   — county x calendar year of book-in
  * ``county_month_panel.csv``  — county x year-month of book-in
  * ``unmapped_facilities.csv`` — facility-level rows whose county is still
    unresolved, so the academic team can see exactly what is being dropped.

Detentions are counted by ``Detention Book In Date``. We also report
unique persons (distinct ``Anonymized Identifier``) and total
detention-days (sum of book-out minus book-in for stays where both dates
are present).
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from . import config

log = logging.getLogger(__name__)

YEAR_PANEL_FILENAME = "county_year_panel.csv"
MONTH_PANEL_FILENAME = "county_month_panel.csv"
UNMAPPED_FILENAME = "unmapped_facilities.csv"


def _load_crosswalk(path: Path) -> pd.DataFrame:
    cw = pd.read_csv(path, dtype=str).fillna("")
    cw["facility_name"] = cw["facility_name"].str.strip().str.upper()
    cw["facility_code"] = cw["facility_code"].str.strip().str.upper()
    cw["unusual_flag"] = cw["unusual_flag"].str.lower().isin({"true", "1", "yes"})
    return cw


def _aggregate_one_file(
    csv_path: Path, cw: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Aggregate one per-FY CSV into (year_panel, month_panel, unmapped_episodes).

    Done in chunks to keep memory flat on a Surface Pro.
    """
    year_parts: list[pd.DataFrame] = []
    month_parts: list[pd.DataFrame] = []
    unmapped_parts: list[pd.DataFrame] = []

    cols = ["fiscal_year", "facility_name", "facility_code",
            "book_in_date", "book_out_date", "person_id"]
    dtypes = {
        "fiscal_year": "int32",
        "facility_name": str,
        "facility_code": str,
        "book_in_date": str,
        "book_out_date": str,
        "person_id": str,
    }

    for chunk in pd.read_csv(
        csv_path,
        usecols=cols,
        dtype=dtypes,
        chunksize=200_000,
        keep_default_na=False,
    ):
        chunk["facility_name"] = chunk["facility_name"].str.strip().str.upper()
        chunk["facility_code"] = chunk["facility_code"].str.strip().str.upper()

        merged = chunk.merge(
            cw[["facility_name", "facility_code", "county_fips",
                "county_name", "state_abbr", "state_name",
                "unusual_flag", "unusual_type"]],
            on=["facility_name", "facility_code"],
            how="left",
        )

        # Parse dates.
        merged["book_in_dt"] = pd.to_datetime(
            merged["book_in_date"], errors="coerce"
        )
        merged["book_out_dt"] = pd.to_datetime(
            merged["book_out_date"], errors="coerce"
        )
        merged["detention_days"] = (
            (merged["book_out_dt"] - merged["book_in_dt"]).dt.days
        ).clip(lower=0)

        # Track unmapped (no county) episodes per facility so the user can see
        # exactly what falls out.
        unmapped_mask = merged["county_fips"].fillna("").astype(str).str.strip() == ""
        if unmapped_mask.any():
            u = merged.loc[unmapped_mask].groupby(
                ["fiscal_year", "facility_name", "facility_code",
                 "unusual_flag", "unusual_type"],
                dropna=False,
            ).agg(
                n_episodes=("person_id", "size"),
                n_unique_persons=("person_id", "nunique"),
            ).reset_index()
            unmapped_parts.append(u)

        mapped = merged.loc[~unmapped_mask].copy()
        if mapped.empty:
            continue

        mapped["year"] = mapped["book_in_dt"].dt.year.astype("Int64")
        mapped["year_month"] = mapped["book_in_dt"].dt.strftime("%Y-%m")

        year_parts.append(
            mapped.groupby(
                ["county_fips", "county_name", "state_abbr", "state_name",
                 "fiscal_year", "year"],
                dropna=False,
            ).agg(
                n_episodes=("person_id", "size"),
                n_unique_persons=("person_id", "nunique"),
                detention_days=("detention_days", "sum"),
                n_unusual_episodes=("unusual_flag", "sum"),
            ).reset_index()
        )

        month_parts.append(
            mapped.groupby(
                ["county_fips", "county_name", "state_abbr", "state_name",
                 "fiscal_year", "year_month"],
                dropna=False,
            ).agg(
                n_episodes=("person_id", "size"),
                n_unique_persons=("person_id", "nunique"),
                detention_days=("detention_days", "sum"),
                n_unusual_episodes=("unusual_flag", "sum"),
            ).reset_index()
        )

    yp = pd.concat(year_parts, ignore_index=True) if year_parts else pd.DataFrame()
    mp = pd.concat(month_parts, ignore_index=True) if month_parts else pd.DataFrame()
    up = pd.concat(unmapped_parts, ignore_index=True) if unmapped_parts else pd.DataFrame()
    return yp, mp, up


def _final_rollup(parts: list[pd.DataFrame], group_cols: list[str]) -> pd.DataFrame:
    """Concatenate per-FY chunk aggregates and re-group to fold duplicates."""
    if not parts:
        return pd.DataFrame()
    df = pd.concat(parts, ignore_index=True)
    if df.empty:
        return df
    return df.groupby(group_cols, dropna=False).agg(
        n_episodes=("n_episodes", "sum"),
        n_unique_persons=("n_unique_persons", "sum"),
        detention_days=("detention_days", "sum"),
        n_unusual_episodes=("n_unusual_episodes", "sum"),
    ).reset_index()


def aggregate(
    interim_dir: Path = config.INTERIM_DIR,
    crosswalk_csv: Path | None = None,
    out_dir: Path = config.PROCESSED_DIR,
) -> dict:
    if crosswalk_csv is None:
        crosswalk_csv = out_dir / "facility_crosswalk.csv"
    if not crosswalk_csv.exists():
        raise FileNotFoundError(
            f"{crosswalk_csv} not found - run `crosswalk` first."
        )

    cw = _load_crosswalk(crosswalk_csv)
    files = sorted(interim_dir.glob("fy*_detentions.csv*"))
    if not files:
        raise FileNotFoundError(
            f"No per-FY extract CSVs found under {interim_dir}; run `extract` first."
        )

    all_year, all_month, all_unmapped = [], [], []
    for f in files:
        log.info("aggregating %s", f.name)
        yp, mp, up = _aggregate_one_file(f, cw)
        if not yp.empty:
            all_year.append(yp)
        if not mp.empty:
            all_month.append(mp)
        if not up.empty:
            all_unmapped.append(up)

    out_dir.mkdir(parents=True, exist_ok=True)
    year_panel = _final_rollup(
        all_year,
        ["county_fips", "county_name", "state_abbr", "state_name",
         "fiscal_year", "year"],
    )
    month_panel = _final_rollup(
        all_month,
        ["county_fips", "county_name", "state_abbr", "state_name",
         "fiscal_year", "year_month"],
    )

    # Note: n_unique_persons is approximate when the same person appears in
    # multiple chunks/files because we sum chunk-level distincts.
    if not year_panel.empty:
        year_panel = year_panel.sort_values(
            ["state_abbr", "county_name", "year"]
        ).reset_index(drop=True)
        year_panel.to_csv(out_dir / YEAR_PANEL_FILENAME, index=False)
    if not month_panel.empty:
        month_panel = month_panel.sort_values(
            ["state_abbr", "county_name", "year_month"]
        ).reset_index(drop=True)
        month_panel.to_csv(out_dir / MONTH_PANEL_FILENAME, index=False)

    if all_unmapped:
        unmapped = pd.concat(all_unmapped, ignore_index=True)
        unmapped = unmapped.groupby(
            ["facility_name", "facility_code", "unusual_flag", "unusual_type"],
            dropna=False,
        ).agg(
            n_episodes=("n_episodes", "sum"),
            n_unique_persons=("n_unique_persons", "sum"),
            n_fiscal_years=("fiscal_year", "nunique"),
        ).reset_index().sort_values("n_episodes", ascending=False)
        unmapped.to_csv(out_dir / UNMAPPED_FILENAME, index=False)
    else:
        unmapped = pd.DataFrame()

    log.info("year panel rows : %d", len(year_panel))
    log.info("month panel rows: %d", len(month_panel))
    log.info("unmapped rows   : %d", len(unmapped))
    return {
        "year_panel_rows": len(year_panel),
        "month_panel_rows": len(month_panel),
        "unmapped_rows": len(unmapped),
        "year_panel_path": str(out_dir / YEAR_PANEL_FILENAME),
        "month_panel_path": str(out_dir / MONTH_PANEL_FILENAME),
        "unmapped_path": str(out_dir / UNMAPPED_FILENAME),
    }
