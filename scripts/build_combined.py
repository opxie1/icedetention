"""Build single combined detention panels spanning 2012-2026.

Stacks the FOIA detention panel (book-in episodes, 2012-01..2023-11) on top
of the DDP stays panel (custody stays, 2023-12..2026-03). The two sources
were built with a clean one-month splice, so there is no overlap and no
double counting.

A `source` column flags which half each row came from. The unified
`n_detained` column uses n_episodes for the FOIA half and n_stints_total
for the DDP half, because a "stint" (one facility booking inside a stay) is
the closest equivalent to a FOIA "episode" (one book-in event). The native
columns (n_episodes / n_stays / n_stints_total / detention_days /
total_days) are preserved so nothing is hidden.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

PROC = Path("data/processed")

FOIA_SRC = "FOIA: book-in episodes (2012-2023)"
DDP_SRC = "DDP: custody stays (2023-2026)"

LEAD_COLS = [
    "county_fips", "county_name", "state_abbr", "state_name",
    "year", "source", "n_detained", "n_unique_persons", "detained_days",
]
NATIVE_COLS = ["n_episodes", "n_stays", "n_stints_total"]


def build(period_col: str, foia_file: str, stays_file: str, out_file: str) -> None:
    foia = pd.read_csv(PROC / foia_file, dtype={"county_fips": str})
    stays = pd.read_csv(PROC / stays_file, dtype={"county_fips": str})

    foia = foia.copy()
    foia["source"] = FOIA_SRC
    foia["n_detained"] = foia["n_episodes"]
    foia["detained_days"] = foia["detention_days"]
    foia["n_stays"] = pd.NA
    foia["n_stints_total"] = pd.NA

    stays = stays.copy()
    stays["source"] = DDP_SRC
    stays["n_detained"] = stays["n_stints_total"]
    stays["detained_days"] = stays["total_days"]
    stays["n_episodes"] = pd.NA

    if period_col == "year":
        foia["year"] = foia["year_month"].str[:4].astype(int) if "year_month" in foia else foia["year"]
        # the FOIA/stays YEAR panels already have a `year` column; use it
        foia = pd.read_csv(PROC / foia_file, dtype={"county_fips": str})
        foia["source"] = FOIA_SRC
        foia["n_detained"] = foia["n_episodes"]
        foia["detained_days"] = foia["detention_days"]
        foia["n_stays"] = pd.NA
        foia["n_stints_total"] = pd.NA
        stays = pd.read_csv(PROC / stays_file, dtype={"county_fips": str})
        stays["source"] = DDP_SRC
        stays["n_detained"] = stays["n_stints_total"]
        stays["detained_days"] = stays["total_days"]
        stays["n_episodes"] = pd.NA
        keys = LEAD_COLS + NATIVE_COLS
    else:
        foia["year"] = foia["year_month"].str[:4].astype(int)
        stays["year"] = stays["year_month"].str[:4].astype(int)
        keys = ["county_fips", "county_name", "state_abbr", "state_name",
                "year_month", "year", "source", "n_detained",
                "n_unique_persons", "detained_days"] + NATIVE_COLS

    combined = pd.concat([foia, stays], ignore_index=True)
    combined = combined[keys]
    sort_cols = ["state_abbr", "county_name"]
    sort_cols += ["year_month"] if period_col == "month" else ["year", "source"]
    combined = combined.sort_values(sort_cols).reset_index(drop=True)
    combined.to_csv(PROC / out_file, index=False)

    print(f"wrote {out_file}: {len(combined):,} rows")
    print(f"  FOIA rows : {(combined['source'] == FOIA_SRC).sum():,}")
    print(f"  DDP rows  : {(combined['source'] == DDP_SRC).sum():,}")
    print(f"  n_episodes total (FOIA half) : {combined['n_episodes'].dropna().astype(int).sum():,}")
    print(f"  n_stays total (DDP half)     : {combined['n_stays'].dropna().astype(int).sum():,}")
    print(f"  n_stints total (DDP half)    : {combined['n_stints_total'].dropna().astype(int).sum():,}")


build("month", "county_month_panel.csv", "county_month_stays_panel.csv",
      "county_month_detention_combined.csv")
print()
build("year", "county_year_panel.csv", "county_year_stays_panel.csv",
      "county_year_detention_combined.csv")
