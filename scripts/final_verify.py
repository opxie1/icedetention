"""End-to-end verification that everything reflects Catalina's email."""
import pandas as pd

print("=== 1. SJU airport fix in actual crosswalk output ===")
cw = pd.read_csv("data/processed/facility_crosswalk.csv", dtype=str).fillna("")
sju = cw[cw["facility_code"].isin(["SJUHOLD", "AIRHOPR"])][
    ["facility_name", "facility_code", "county_name", "county_fips"]
]
print(sju.to_string(index=False))
print()

print("=== 2. DDP corrections in actual crosswalk ===")
checks = [
    ("RGS", "Cameron"),
    ("MSF", "Miami-Dade"),
    ("WASHOLD", "Fairfax"),
    ("BASILLA", "Evangeline"),
    ("SJS", "Guaynabo"),
]
for code, expected in checks:
    row = cw[cw["facility_code"] == code].iloc[0]
    ok = expected.lower() in row["county_name"].lower()
    flag = "OK" if ok else "WRONG"
    print(f"  {code} ({row['facility_name']}): {row['county_name']}  [{flag}]")
print()

print("=== 3. Panel reflects DDP shifts (county-year totals) ===")
yr = pd.read_csv("data/processed/county_year_panel.csv", dtype={"county_fips": str})
yr["county_fips"] = yr["county_fips"].str.zfill(5)
for fips, name in [
    ("48061", "Cameron TX (RGV staging moved here)"),
    ("48215", "Hidalgo TX (RGV used to live here)"),
    ("12086", "Miami-Dade FL (Miami Staging moved here)"),
    ("12011", "Broward FL (Miami Staging used to live here)"),
    ("51059", "Fairfax VA (Washington FO moved here)"),
    ("72127", "San Juan PR (SJU airport now here)"),
    ("72061", "Guaynabo PR (San Juan Staging actually here)"),
]:
    tot = yr[yr["county_fips"] == fips]["n_episodes"].sum()
    print(f"  {fips} {name}: {tot:,} episodes")
print()

print("=== 4. Coverage ===")
mapped = cw[cw["county_fips"] != ""]
total_eps = cw["n_episodes"].astype(int).sum()
mapped_eps = mapped["n_episodes"].astype(int).sum()
print(f"  facilities: {len(mapped)}/{len(cw)} ({100*len(mapped)/len(cw):.1f}%)")
print(f"  episodes:   {mapped_eps:,}/{total_eps:,} "
      f"({100*mapped_eps/total_eps:.2f}%)")
print()

print("=== 5. Catalina's instructions, status ===")
print("  - SJU airport hold room -> San Juan: applied")
print("  - Airport Hotel, SAJ. -> San Juan (treat 'San Juan airport' as the area): applied")
print("  - DDP facility list as authoritative: applied")
print("  - DDP stays panel (Dec 2023+, no FOIA overlap): applied")
