"""Prove the FOIA and stays panels do not overlap, and surface any anomalies."""

import pandas as pd

print("=" * 70)
print("FOIA detention panel — book-in coverage")
print("=" * 70)
det = pd.read_csv("data/processed/county_month_panel.csv")
mins = det["year_month"].min()
maxs = det["year_month"].max()
print(f"  county_month_panel.csv: {len(det):,} rows; months {mins}..{maxs}")
det_yr = pd.read_csv("data/processed/county_year_panel.csv")
print(f"  county_year_panel.csv:  {len(det_yr):,} rows; "
      f"years {det_yr['year'].min()}..{det_yr['year'].max()}")
print()

print("=" * 70)
print("DDP stays panel — book-in coverage (Dec 2023 cutoff)")
print("=" * 70)
stays = pd.read_csv("data/processed/county_month_stays_panel.csv")
print(f"  county_month_stays_panel.csv: {len(stays):,} rows; "
      f"months {stays['year_month'].min()}..{stays['year_month'].max()}")
stays_yr = pd.read_csv("data/processed/county_year_stays_panel.csv")
print(f"  county_year_stays_panel.csv:  {len(stays_yr):,} rows; "
      f"years {stays_yr['year'].min()}..{stays_yr['year'].max()}")
print()

print("=" * 70)
print("No-overlap check")
print("=" * 70)
det_months = set(det["year_month"])
stays_months = set(stays["year_month"])
overlap = sorted(det_months & stays_months)
if overlap:
    print(f"  WARNING: month overlap detected: {overlap}")
else:
    print(f"  OK — no months appear in both panels.")
    print(f"  FOIA panel last month:  {max(det_months)}")
    print(f"  Stays panel first month: {min(stays_months)}")
print()

print("=" * 70)
print("Coverage at the splice point — check the transition makes sense")
print("=" * 70)
print("  FOIA panel Nov 2023 (last FOIA month):")
last = det[det["year_month"] == "2023-11"]
print(f"    {len(last):,} county rows, {last['n_episodes'].sum():,} episodes")
print("  Stays panel Dec 2023 (first stays month):")
first = stays[stays["year_month"] == "2023-12"]
print(f"    {len(first):,} county rows, {first['n_stays'].sum():,} stays")
print()

print("=" * 70)
print("Sanity check — top 10 counties match across both panels")
print("=" * 70)
det_tops = (
    det_yr.groupby(["county_fips", "county_name", "state_abbr"])["n_episodes"]
    .sum().sort_values(ascending=False).head(10)
)
print("FOIA top 10 (by episodes):")
print(det_tops.to_string())
print()
stays_tops = (
    stays_yr.groupby(["county_fips", "county_name", "state_abbr"])["n_stays"]
    .sum().sort_values(ascending=False).head(10)
)
print("Stays top 10 (by stays):")
print(stays_tops.to_string())
