from __future__ import annotations

from pathlib import Path

import pandas as pd

PROC = Path(r"C:\Users\xief\.local\bin\ucmerced\data\processed")

bal = pd.read_csv(PROC / "county_month_detention_population_balanced.csv",
                  dtype={"county_fips": str}, low_memory=False)
bal["county_fips"] = bal["county_fips"].str.zfill(5)

det = pd.read_csv(PROC / "county_month_enforcement_detail.csv",
                  dtype={"county_fips": str}, low_memory=False)
det["county_fips"] = det["county_fips"].str.zfill(5)

keep_bal = ["county_fips", "county_name", "state_abbr", "state_name",
            "year", "month", "year_month", "period",
            "n_detained", "pop_total", "pop_noncitizen", "detained_per_100k"]
keep_det = ["county_fips", "year_month", "roll_mean", "roll_sd",
            "eligible", "spike", "excess", "excess_sd"]

out = bal[keep_bal].merge(det[keep_det], on=["county_fips", "year_month"], how="left")

PARTIAL_MONTHS = {"2023-11", "2026-03"}
out["partial_month"] = out["year_month"].isin(PARTIAL_MONTHS)

out = out.sort_values(["county_fips", "year_month"]).reset_index(drop=True)
out.to_csv(PROC / "county_month_exposure.csv", index=False)

print(f"county_month_exposure.csv: {len(out):,} rows")
print(f"  counties {out.county_fips.nunique():,} x months {out.year_month.nunique()}")
print(f"  months {out.year_month.min()}..{out.year_month.max()}")
print(f"  dup key: {out.duplicated(['county_fips','year_month']).sum()}")
print(f"  population present: {100*out.pop_total.notna().mean():.2f}%")
print(f"  spike-eligible rows: {int(out.spike.notna().sum()):,}")
print(f"  total detained: {int(out.n_detained.sum()):,}")
print(f"  columns: {list(out.columns)}")
