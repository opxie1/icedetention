"""Coverage report for both pipelines."""

import pandas as pd

print("=" * 70)
print("DETENTION FACILITY CROSSWALK")
print("=" * 70)
df = pd.read_csv("data/processed/facility_crosswalk.csv", dtype={"county_fips": str})
df["county_fips"] = df["county_fips"].fillna("")
resolved = df[df["county_fips"] != ""]
total_eps = df["n_episodes"].sum()
res_eps = resolved["n_episodes"].sum()
print(f"Facilities resolved: {len(resolved)}/{len(df)} ({100*len(resolved)/len(df):.1f}%)")
print(f"Episodes resolved:   {res_eps:,}/{total_eps:,} ({100*res_eps/total_eps:.1f}%)")
print()
print("Resolution sources by facility count:")
print(resolved["resolution_source"].value_counts().to_string())
print()

flagged = df[df["unusual_flag"] == True]
print(f"Flagged unusual: {len(flagged)} facilities, "
      f"{flagged['n_episodes'].sum():,} episodes "
      f"({100*flagged['n_episodes'].sum()/total_eps:.1f}%)")
print(flagged["unusual_type"].value_counts().to_string())
print()

print("=" * 70)
print("ENCOUNTERS SITE CROSSWALK")
print("=" * 70)
sdf = pd.read_csv("data/processed/site_crosswalk.csv", dtype={"county_fips": str})
sdf["county_fips"] = sdf["county_fips"].fillna("")
sres = sdf[sdf["county_fips"] != ""]
stotal = sdf["n_events"].sum()
sres_e = sres["n_events"].sum()
print(f"Sites resolved:  {len(sres)}/{len(sdf)} ({100*len(sres)/len(sdf):.1f}%)")
print(f"Events resolved: {sres_e:,}/{stotal:,} ({100*sres_e/stotal:.1f}%)")
print()
print("Resolution sources:")
print(sres["resolution_source"].value_counts().to_string())
print()

sflagged = sdf[sdf["unusual_flag"] == True]
print(f"Flagged unusual: {len(sflagged)} sites, "
      f"{sflagged['n_events'].sum():,} events "
      f"({100*sflagged['n_events'].sum()/stotal:.1f}%)")
print(sflagged["unusual_type"].value_counts().to_string())

print()
print("=" * 70)
print("COUNTY PANELS")
print("=" * 70)
yp = pd.read_csv("data/processed/county_year_panel.csv")
print(f"Detention county-year panel:   {len(yp):,} rows, "
      f"{yp['county_fips'].nunique()} counties, "
      f"FY{yp['fiscal_year'].min()}-{yp['fiscal_year'].max()}")
ep = pd.read_csv("data/processed/county_year_encounters_panel.csv")
print(f"Encounters county-year panel:  {len(ep):,} rows, "
      f"{ep['county_fips'].nunique()} counties")
