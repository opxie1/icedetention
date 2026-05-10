"""Sanity-check unusual-flag classification."""

import pandas as pd

df = pd.read_csv("data/processed/facility_crosswalk.csv")

not_flagged = df[df["unusual_flag"] == False]
pat = (
    r"HOTEL|HOSPITAL|\bINN\b|MOTEL|CLINIC|MEDICAL|HEALTH|HOLD|CPC|CUST|HOSP|"
    r"STES|SUITES|WYNDHAM|RAMADA|HILTON|MARRIOTT|HAMPTON|EXPRESS|SUPER\s*8|"
    r"LA QUINTA|CASA"
)
sus = not_flagged[not_flagged["facility_name"].str.contains(pat, regex=True, na=False)]
sus = sus.sort_values("n_episodes", ascending=False)
print(f"Suspicious-looking but unflagged: {len(sus)}")
if len(sus):
    print(sus[["facility_name", "facility_code", "n_episodes"]].to_string(index=False))

print()
print("Unusual breakdown:")
print(df[df["unusual_flag"]]["unusual_type"].value_counts().to_string())
total = df["n_episodes"].sum()
unus = df[df["unusual_flag"]]["n_episodes"].sum()
print(f"\nEpisodes flagged unusual: {unus:,} / {total:,} ({100*unus/total:.1f}%)")

print()
print("Real detention centers should NOT flag:")
for kw in ["STEWART DETENTION", "PORT ISABEL SPC", "ELOY FED", "ADELANTO ICE",
          "OTAY MESA DETENTION", "KARNES CO IMM", "CIBOLA COUNTY CORR",
          "OTERO COUNTY PRISON", "EL PASO SPC", "FLORENCE SPC"]:
    m = df[df["facility_name"].str.contains(kw, na=False, regex=False)]
    if not m.empty:
        flagged = m["unusual_flag"].any()
        types = list(m[m["unusual_flag"]]["unusual_type"].unique())
        print(f"  {kw:30s} flagged={flagged} types={types}")

print()
print("Known unusual sites SHOULD flag:")
for kw, expected in [
    ("DALLAS F.O. HOLD", "hold_room"),
    ("PHOENIX DIST OFFICE", "hold_room"),
    ("ALEXANDRIA STAGING", "staging_processing"),
    ("FLORENCE STAGING", "staging_processing"),
    ("RIO GRANDE VALLEY STAGING", "staging_processing"),
    ("HOLIDAY INN", "hotel_motel"),
    ("HAMPTON INN", "hotel_motel"),
    ("LARKIN HOSPITAL", "hospital"),
    ("VALLEY BAPTIST HOSPITAL", "hospital"),
    ("COURTHOUSE", "courthouse"),
]:
    m = df[df["facility_name"].str.contains(kw, na=False, regex=False)]
    if not m.empty:
        types = list(m["unusual_type"].dropna().unique())
        ok = expected in [t for t in types if t]
        print(f"  {kw:30s} expected={expected} got={types} {'OK' if ok else 'MISS'}")
