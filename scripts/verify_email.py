"""Verify every numerical claim in the email."""

import pandas as pd
from pathlib import Path
from collections import Counter

print("=" * 72)
print("EMAIL FACT-CHECK")
print("=" * 72)

cw = pd.read_csv("data/processed/facility_crosswalk.csv",
                 dtype={"county_fips": str})
cw["county_fips"] = cw["county_fips"].fillna("")

total_eps = int(cw["n_episodes"].sum())
n_fac = len(cw)
n_resolved = int((cw["county_fips"] != "").sum())
n_unmapped = n_fac - n_resolved
pct_resolved = 100 * n_resolved / n_fac

flagged = cw[cw["unusual_flag"] == True]
n_flag = len(flagged)
flag_types = sorted(flagged["unusual_type"].dropna().unique())

print(f"\n[Detentions]")
print(f"  CLAIM: 8,458,563 total detention episodes")
print(f"  ACTUAL: {total_eps:,}  {'OK' if total_eps == 8458563 else 'WRONG'}")

print(f"\n  CLAIM: 1,141 unique facilities identified")
print(f"  ACTUAL: {n_fac:,}  {'OK' if n_fac == 1141 else 'WRONG'}")

print(f"\n  CLAIM: 1,066 facilities (93.4%) resolved to a specific county")
print(f"  ACTUAL: {n_resolved:,} ({pct_resolved:.1f}%)  "
      f"{'OK' if n_resolved == 1066 else 'WRONG'}")

print(f"\n  CLAIM: 405 facilities flagged as unusual across 9 categories")
print(f"  ACTUAL: {n_flag} facilities, {len(flag_types)} categories")
print(f"  Categories: {flag_types}")
print(f"  {'OK' if n_flag == 405 and len(flag_types) == 9 else 'WRONG'}")

print(f"\n  CLAIM: 75 facilities remain unmapped")
print(f"  ACTUAL: {n_unmapped}  {'OK' if n_unmapped == 75 else 'WRONG'}")

print(f"\n  EMAIL says: 'mostly Puerto Rico hold rooms and staging areas'")
print(f"  Top 10 unmapped facilities:")
unmapped_df = cw[cw["county_fips"] == ""].sort_values(
    "n_episodes", ascending=False
).head(10)
for _, r in unmapped_df.iterrows():
    print(f"    {r['facility_name']:50s} ({r['facility_code']:8s}) "
          f"{r['n_episodes']:>7,}")

unmapped_all = cw[cw["county_fips"] == ""].copy()
def categorize(row):
    name = (row["facility_name"] or "").upper()
    code = (row["facility_code"] or "").upper()
    if any(s in name for s in ["SAN JUAN", "GUAYNABO", "BAYAMON",
                                "AGUADILLA", "VEGA ALTA"]) or code.endswith("PR"):
        return "Puerto Rico"
    if any(s in name for s in ["HAGATNA", "AGANA", "GUAM"]) or code.endswith("GU"):
        return "Guam"
    if any(s in name for s in ["SAIPAN", "SAIPAIN"]) or code.endswith("MP") or code.endswith("CMP"):
        return "N. Mariana Is."
    if "CHARLOTTE AMALIE" in name or code.endswith("VI"):
        return "Virgin Islands"
    ut = row.get("unusual_type", "")
    if ut == "hotel_motel":
        return "hotel/motel"
    if ut == "hospital":
        return "hospital"
    if ut == "hold_room":
        return "other hold room"
    return "other"

unmapped_all["bucket"] = unmapped_all.apply(categorize, axis=1)
print(f"\n  Unmapped breakdown by bucket:")
for bucket, count in unmapped_all["bucket"].value_counts().items():
    eps = int(unmapped_all[unmapped_all["bucket"] == bucket]["n_episodes"].sum())
    print(f"    {bucket:18s} {count:>3} facilities  {eps:>6,} episodes")

yp = pd.read_csv("data/processed/county_year_panel.csv")
mp = pd.read_csv("data/processed/county_month_panel.csv")
n_counties = yp["county_fips"].nunique()

print(f"\n  CLAIM: county-year panel (3,961 rows across 564 counties)")
print(f"  ACTUAL: {len(yp):,} rows, {n_counties} counties  "
      f"{'OK' if len(yp) == 3961 and n_counties == 564 else 'WRONG'}")

print(f"\n  CLAIM: county-month panel (36,379 rows)")
print(f"  ACTUAL: {len(mp):,}  {'OK' if len(mp) == 36379 else 'WRONG'}")

review = pd.read_csv("data/processed/facility_crosswalk_review.csv")
print(f"\n  CLAIM: 430 detention facilities in review file")
print(f"  ACTUAL: {len(review)}  {'OK' if len(review) == 430 else 'WRONG'}")

print(f"\n[Encounters]")
sc = pd.read_csv("data/processed/site_crosswalk.csv",
                 dtype={"county_fips": str})
sc["county_fips"] = sc["county_fips"].fillna("")
total_events = int(sc["n_events"].sum())
n_sites = len(sc)
n_resolved_sites = int((sc["county_fips"] != "").sum())
n_flagged_sites = int(sc["unusual_flag"].sum())

print(f"\n  CLAIM: 1,360,318 encounter events processed")
print(f"  ACTUAL: {total_events:,}  {'OK' if total_events == 1360318 else 'WRONG'}")

print(f"\n  CLAIM: 413 unique sites identified, 272 resolved")
print(f"  ACTUAL: {n_sites} sites, {n_resolved_sites} resolved  "
      f"{'OK' if n_sites == 413 and n_resolved_sites == 272 else 'WRONG'}")

print(f"\n  CLAIM: 186 sites flagged as unusual")
print(f"  ACTUAL: {n_flagged_sites}  {'OK' if n_flagged_sites == 186 else 'WRONG'}")

interim = list(Path("data/interim").glob("encounters_*.csv*"))
if interim:
    dates = []
    for chunk in pd.read_csv(interim[0], usecols=["event_date"],
                              dtype=str, chunksize=200000, keep_default_na=False):
        d = pd.to_datetime(chunk["event_date"], errors="coerce")
        d = d.dropna()
        if not d.empty:
            dates.append((d.min(), d.max()))
    if dates:
        mn = min(t[0] for t in dates)
        mx = max(t[1] for t in dates)
        print(f"\n  CLAIM: 'September 2023 through July 2025'")
        print(f"  ACTUAL: {mn.date()} to {mx.date()}")

ey = pd.read_csv("data/processed/county_year_encounters_panel.csv")
em = pd.read_csv("data/processed/county_month_encounters_panel.csv")
print(f"\n  CLAIM: county-year panel (664 rows), county-month (3,736 rows)")
print(f"  ACTUAL: {len(ey)}, {len(em)}  "
      f"{'OK' if len(ey) == 664 and len(em) == 3736 else 'WRONG'}")

sr = pd.read_csv("data/processed/site_crosswalk_review.csv")
print(f"\n  CLAIM: 306 encounter sites in review file")
print(f"  ACTUAL: {len(sr)}  {'OK' if len(sr) == 306 else 'WRONG'}")
