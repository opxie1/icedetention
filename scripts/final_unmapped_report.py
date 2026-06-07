"""Print the residual unmapped stays — for the README."""
import pandas as pd

un = pd.read_csv("data/processed/unmapped_stays.csv")
print(un.to_string(index=False))
print()
print(f"total unmapped stays: {un['n_stays'].sum():,}")

yr = pd.read_csv("data/processed/county_year_stays_panel.csv")
mapped = yr["n_stays"].sum()
total = mapped + un["n_stays"].sum()
print(f"mapped: {mapped:,} / {total:,}  coverage: {100*mapped/total:.3f}%")
