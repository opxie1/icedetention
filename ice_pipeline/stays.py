"""DDP detention-stays parquet aggregator: county-year and county-month panels."""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from . import config
from .known_facilities import norm_compact, norm_county

log = logging.getLogger(__name__)

STAYS_YEAR_PANEL_FILENAME = "county_year_stays_panel.csv"
STAYS_MONTH_PANEL_FILENAME = "county_month_stays_panel.csv"
STAYS_UNMAPPED_FILENAME = "unmapped_stays.csv"
FACILITY_CROSSWALK_FILENAME = "facility_crosswalk.csv"


_STATE_NAME = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut",
    "DE": "Delaware", "DC": "District of Columbia", "FL": "Florida",
    "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois",
    "IN": "Indiana", "IA": "Iowa", "KS": "Kansas", "KY": "Kentucky",
    "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota",
    "MS": "Mississippi", "MO": "Missouri", "MT": "Montana",
    "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire",
    "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio",
    "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania",
    "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota",
    "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont",
    "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming", "PR": "Puerto Rico",
    "GU": "Guam", "VI": "U.S. Virgin Islands",
    "MP": "Northern Mariana Islands",
}


def _build_fips_lookup(fips_csv: Path) -> dict[tuple[str, str], tuple[str, str]]:
    fips = pd.read_csv(fips_csv, dtype={"fips": str})
    fips["fips"] = fips["fips"].str.zfill(5)
    state_to_abbr = {v: k for k, v in _STATE_NAME.items()}
    fips["state_abbr"] = fips["state_name"].map(state_to_abbr).fillna("")
    dc_rows = fips["fips"] == "11001"
    if dc_rows.any():
        fips.loc[dc_rows, "state_abbr"] = "DC"
        fips.loc[dc_rows, "state_name"] = "District of Columbia"

    lookup: dict[tuple[str, str], tuple[str, str]] = {}
    for _, r in fips.iterrows():
        sa = r["state_abbr"]
        if not sa:
            continue
        cn_norm = norm_county(r["county_name"])
        cn_compact = norm_compact(r["county_name"])
        lookup[(sa, cn_norm)] = (r["fips"], r["county_name"])
        lookup[(sa, cn_compact)] = (r["fips"], r["county_name"])
        # VA independent cities (and a few in MO, NV) appear in the FIPS file
        # as "X city" but in DDP/FOIA as bare "X". Register the bare form if
        # not already taken by another county in the same state.
        bare = cn_norm
        if bare.endswith(" city"):
            stripped = bare[:-5].strip()
            if stripped and (sa, stripped) not in lookup:
                lookup[(sa, stripped)] = (r["fips"], r["county_name"])
        bare_c = cn_compact
        if bare_c.endswith("city"):
            stripped_c = bare_c[:-4]
            if stripped_c and (sa, stripped_c) not in lookup:
                lookup[(sa, stripped_c)] = (r["fips"], r["county_name"])
    return lookup


def aggregate_stays(
    parquet_path: Path,
    fips_csv: Path | None = None,
    out_dir: Path = config.PROCESSED_DIR,
    refs_dir: Path = config.REFERENCES_DIR,
    cutoff_book_in: str = "2023-12-01",
) -> dict:
    if fips_csv is None:
        candidates = sorted(refs_dir.glob("fips*state*.csv")) + sorted(
            refs_dir.glob("fips*.csv")
        )
        if not candidates:
            raise FileNotFoundError(
                f"No FIPS reference CSV found under {refs_dir}."
            )
        fips_csv = candidates[0]

    log.info("loading %s", parquet_path.name)
    s = pd.read_parquet(parquet_path)
    log.info("loaded %d stays", len(s))

    s["book_in"] = pd.to_datetime(
        s["book_in_date_time_first"], errors="coerce", utc=True
    )
    s["book_out"] = pd.to_datetime(
        s["book_out_date_time_last"], errors="coerce", utc=True
    )
    s["stay_days"] = (
        (s["book_out"] - s["book_in"]).dt.total_seconds() / 86400
    ).clip(lower=0)

    if cutoff_book_in:
        cutoff = pd.Timestamp(cutoff_book_in, tz="UTC")
        before = len(s)
        s = s[s["book_in"] >= cutoff].copy()
        log.info(
            "applied cutoff book_in >= %s: kept %d / %d stays",
            cutoff_book_in, len(s), before,
        )

    s["year"] = s["book_in"].dt.year.astype("Int64")
    s["year_month"] = s["book_in"].dt.strftime("%Y-%m")
    s["state_abbr"] = s["state_longest"].fillna("").astype(str).str.strip().str.upper()
    s["county_raw"] = s["county_longest"].fillna("").astype(str).str.strip()
    s["state_name"] = s["state_abbr"].map(_STATE_NAME).fillna("")

    fips_lookup = _build_fips_lookup(fips_csv)

    def _resolve(row):
        sa = row["state_abbr"]
        if not sa or not row["county_raw"]:
            return ("", "")
        norm = norm_county(row["county_raw"])
        hit = fips_lookup.get((sa, norm))
        if hit:
            return hit
        compact = norm_compact(row["county_raw"])
        hit = fips_lookup.get((sa, compact))
        if hit:
            return hit
        return ("", "")

    resolved = s.apply(_resolve, axis=1, result_type="expand")
    s["county_fips"] = resolved[0]
    s["county_name"] = resolved[1]

    cw_path = out_dir / FACILITY_CROSSWALK_FILENAME
    if cw_path.exists():
        cw = pd.read_csv(cw_path, dtype=str).fillna("")
        fac2fips = dict(zip(cw["facility_code"], cw["county_fips"]))
        fac2cnty = dict(zip(cw["facility_code"], cw["county_name"]))
        fac2st = dict(zip(cw["facility_code"], cw["state_abbr"]))
        need = s["county_fips"] == ""
        fac = s.loc[need, "detention_facility_code_longest"].astype(str)
        rescued_fips = fac.map(fac2fips).fillna("")
        rescued_cnty = fac.map(fac2cnty).fillna("")
        rescued_st = fac.map(fac2st).fillna("")
        valid = rescued_fips.str.len() == 5
        idx = fac.index[valid]
        s.loc[idx, "county_fips"] = rescued_fips[valid].values
        s.loc[idx, "county_name"] = rescued_cnty[valid].values
        empty_state = s.loc[idx, "state_abbr"] == ""
        es_idx = idx[empty_state.values]
        s.loc[es_idx, "state_abbr"] = rescued_st.loc[es_idx].values
        s.loc[es_idx, "state_name"] = (
            s.loc[es_idx, "state_abbr"].map(_STATE_NAME).fillna("").values
        )
        log.info(
            "rescued %d / %d blank-county stays via FOIA facility crosswalk",
            int(valid.sum()), int(need.sum()),
        )
    else:
        log.info(
            "no %s found at %s; skipping facility-code rescue",
            FACILITY_CROSSWALK_FILENAME, out_dir,
        )

    unmapped_mask = (s["county_fips"] == "") | s["year"].isna()
    mapped = s[~unmapped_mask].copy()
    unmapped = s[unmapped_mask].copy()
    log.info(
        "mapped %d / %d stays (%.1f%%)",
        len(mapped), len(s), 100 * len(mapped) / max(len(s), 1),
    )

    year_panel = mapped.groupby(
        ["county_fips", "county_name", "state_abbr", "state_name", "year"],
        dropna=False,
    ).agg(
        n_stays=("stay_ID", "size"),
        n_unique_persons=("unique_identifier", "nunique"),
        n_stints_total=("n_stints", "sum"),
        total_days=("stay_days", "sum"),
    ).reset_index().sort_values(["state_abbr", "county_name", "year"])

    month_panel = mapped.groupby(
        ["county_fips", "county_name", "state_abbr", "state_name", "year_month"],
        dropna=False,
    ).agg(
        n_stays=("stay_ID", "size"),
        n_unique_persons=("unique_identifier", "nunique"),
        n_stints_total=("n_stints", "sum"),
        total_days=("stay_days", "sum"),
    ).reset_index().sort_values(["state_abbr", "county_name", "year_month"])

    unmapped_summary = unmapped.groupby(
        ["state_abbr", "county_raw"], dropna=False
    ).agg(
        n_stays=("stay_ID", "size"),
        n_unique_persons=("unique_identifier", "nunique"),
    ).reset_index().sort_values("n_stays", ascending=False)

    out_dir.mkdir(parents=True, exist_ok=True)
    yr_path = out_dir / STAYS_YEAR_PANEL_FILENAME
    mo_path = out_dir / STAYS_MONTH_PANEL_FILENAME
    un_path = out_dir / STAYS_UNMAPPED_FILENAME
    year_panel.to_csv(yr_path, index=False)
    month_panel.to_csv(mo_path, index=False)
    unmapped_summary.to_csv(un_path, index=False)
    log.info("wrote %s (%d rows)", yr_path.name, len(year_panel))
    log.info("wrote %s (%d rows)", mo_path.name, len(month_panel))
    log.info("wrote %s (%d rows)", un_path.name, len(unmapped_summary))

    return {
        "stays_total": len(s),
        "stays_mapped": len(mapped),
        "year_panel_rows": len(year_panel),
        "month_panel_rows": len(month_panel),
        "unmapped_rows": len(unmapped_summary),
        "year_panel_path": str(yr_path),
        "month_panel_path": str(mo_path),
        "unmapped_path": str(un_path),
    }
