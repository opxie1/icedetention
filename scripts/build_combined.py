"""Build single combined detention panels spanning 2012-2026.

Stacks the FOIA detention panel (book-in episodes, 2012-01..2023-11) on top
of the DDP stays panel (custody stays, 2023-12..2026-03). The two sources
were built with a clean one-month splice, so there is no overlap and no
double counting.

A `source` column flags which half each row came from. The unified
`n_detained` column uses n_episodes for the FOIA half and n_stints_total
for the DDP half, because a "stint" (one facility booking inside a stay) is
the closest equivalent to a FOIA "episode" (one book-in event). The native
columns (n_episodes / n_stays / n_stints_total) are preserved so nothing is
hidden.

MONTH file: FOIA and DDP months never overlap, so (county_fips, year_month)
is already a unique key.

YEAR file: only the splice year (2023) draws from both sources (FOIA
Jan-Nov, DDP Dec). We collapse those into one row per county so that
(county_fips, year) is a unique key and the file merges cleanly at the
county-year level. That single 2023 row is labelled as a mix of both
sources.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

PROC = Path("data/processed")

FOIA_SRC = "FOIA: book-in episodes (2012-2023)"
DDP_SRC = "DDP: custody stays (2023-2026)"
MIXED_SRC = "FOIA (Jan-Nov) + DDP (Dec)"

NATIVE = ["n_episodes", "n_stays", "n_stints_total"]
GEO = ["county_fips", "county_name", "state_abbr", "state_name"]


def _tag(df: pd.DataFrame, source: str) -> pd.DataFrame:
    df = df.copy()
    df["source"] = source
    if source == FOIA_SRC:
        df["n_detained"] = df["n_episodes"]
        df["detained_days"] = df["detention_days"]
        df["n_stays"] = pd.NA
        df["n_stints_total"] = pd.NA
    else:
        df["n_detained"] = df["n_stints_total"]
        df["detained_days"] = df["total_days"]
        df["n_episodes"] = pd.NA
    return df


def build_month() -> None:
    foia = _tag(pd.read_csv(PROC / "county_month_panel.csv", dtype={"county_fips": str}), FOIA_SRC)
    ddp = _tag(pd.read_csv(PROC / "county_month_stays_panel.csv", dtype={"county_fips": str}), DDP_SRC)
    for d in (foia, ddp):
        d["year"] = d["year_month"].str[:4].astype(int)
    cols = GEO + ["year_month", "year", "source", "n_detained",
                  "n_unique_persons", "detained_days"] + NATIVE
    out = pd.concat([foia[cols], ddp[cols]], ignore_index=True)
    out = out.sort_values(["state_abbr", "county_name", "year_month"]).reset_index(drop=True)
    out.to_csv(PROC / "county_month_detention_combined.csv", index=False)
    dup = out.duplicated(subset=["county_fips", "year_month"]).sum()
    print(f"county_month_detention_combined.csv: {len(out):,} rows, "
          f"{out['year_month'].min()}..{out['year_month'].max()}, dup-key={dup}")


def build_year() -> None:
    foia = _tag(pd.read_csv(PROC / "county_year_panel.csv", dtype={"county_fips": str}), FOIA_SRC)
    ddp = _tag(pd.read_csv(PROC / "county_year_stays_panel.csv", dtype={"county_fips": str}), DDP_SRC)
    cols = GEO + ["year", "source", "n_detained", "n_unique_persons",
                  "detained_days"] + NATIVE
    stacked = pd.concat([foia[cols], ddp[cols]], ignore_index=True)

    # Collapse to one row per county-year. Only 2023 has two source rows.
    def _agg(g: pd.DataFrame) -> pd.Series:
        srcs = list(dict.fromkeys(g["source"]))
        source = MIXED_SRC if len(srcs) > 1 else srcs[0]
        return pd.Series({
            "source": source,
            "n_detained": g["n_detained"].sum(min_count=1),
            "n_unique_persons": g["n_unique_persons"].sum(min_count=1),
            "detained_days": g["detained_days"].sum(min_count=1),
            "n_episodes": g["n_episodes"].sum(min_count=1),
            "n_stays": g["n_stays"].sum(min_count=1),
            "n_stints_total": g["n_stints_total"].sum(min_count=1),
        })

    out = stacked.groupby(GEO + ["year"], dropna=False).apply(
        _agg, include_groups=False
    ).reset_index()
    out = out.sort_values(["state_abbr", "county_name", "year"]).reset_index(drop=True)
    out.to_csv(PROC / "county_year_detention_combined.csv", index=False)
    dup = out.duplicated(subset=["county_fips", "year"]).sum()
    n_mixed = (out["source"] == MIXED_SRC).sum()
    print(f"county_year_detention_combined.csv: {len(out):,} rows, "
          f"{out['year'].min()}..{out['year'].max()}, dup-key={dup}, "
          f"mixed-2023-rows={n_mixed}")
    print(f"  totals: episodes={int(out['n_episodes'].sum()):,}  "
          f"stays={int(out['n_stays'].sum()):,}  "
          f"stints={int(out['n_stints_total'].sum()):,}")


build_month()
build_year()
