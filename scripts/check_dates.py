"""Look at the actual distribution of encounter event dates."""

import pandas as pd
from pathlib import Path
from collections import Counter

interim = list(Path("data/interim").glob("encounters_*.csv*"))
counts = Counter()
all_dates = []
for chunk in pd.read_csv(interim[0], usecols=["event_date"],
                          dtype=str, chunksize=200_000, keep_default_na=False):
    d = pd.to_datetime(chunk["event_date"], errors="coerce")
    d = d.dropna()
    all_dates.append(d)

d = pd.concat(all_dates)
print(f"Total parseable dates: {len(d):,}")
print(f"Earliest: {d.min().date()}")
print(f"Latest:   {d.max().date()}")

# Per-year counts
print("\nEvents per year:")
yr = d.dt.year.value_counts().sort_index()
for y, n in yr.items():
    print(f"  {y}: {n:>10,}")

# 99th-percentile latest date (to filter out outlier typos)
p99 = d.quantile(0.999)
print(f"\n99.9th-percentile date: {p99.date()}")

# Months at the upper end
print("\nLatest 5 years/months with events:")
ym = d.dt.to_period("M").value_counts().sort_index().tail(15)
for p, n in ym.items():
    print(f"  {p}: {n:>8,}")
