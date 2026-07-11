"""Prepare the input for Catalina's task1_spike_maps.R.

Her script expects columns county_fips, year, month, detention_count and
implicitly assumes every county has a row for every month (its 12-row
rolling window otherwise spans more than 12 calendar months). Our combined
panel is sparse - county-months with zero detentions have no row - so this
completes the grid: every county that ever appears x every month
2012-01..2026-03, detention_count = n_detained, zeros filled in.

No change to her spike definition; this is input plumbing only.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

REPO = Path(r"C:\Users\xief\.local\bin\ucmerced")
PROC = REPO / "data" / "processed"
OUT = REPO / "analysis" / "task1_spikes"
OUT.mkdir(parents=True, exist_ok=True)

cm = pd.read_csv(PROC / "county_month_detention_combined.csv",
                 dtype={"county_fips": str})
cm["county_fips"] = cm["county_fips"].str.zfill(5)

months = pd.period_range("2012-01", "2026-03", freq="M").astype(str)
counties = sorted(cm["county_fips"].unique())
grid = pd.MultiIndex.from_product(
    [counties, months], names=["county_fips", "year_month"]).to_frame(index=False)

slim = cm[["county_fips", "year_month", "n_detained"]]
full = grid.merge(slim, on=["county_fips", "year_month"], how="left")
full["detention_count"] = full["n_detained"].fillna(0).astype(int)
full["year"] = full["year_month"].str[:4].astype(int)
full["month"] = full["year_month"].str[5:7].astype(int)

out = full[["county_fips", "year", "month", "detention_count"]]
dest = OUT / "detention_county_month.csv"
out.to_csv(dest, index=False)

n_zero = (out["detention_count"] == 0).sum()
print(f"wrote {dest}")
print(f"rows: {len(out):,} ({len(counties)} counties x {len(months)} months)")
print(f"zero-filled rows: {n_zero:,} ({100*n_zero/len(out):.1f}%)")
print(f"total detained preserved: {out['detention_count'].sum():,} "
      f"(source: {int(cm['n_detained'].sum()):,})")
