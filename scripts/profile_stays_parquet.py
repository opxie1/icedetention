"""Profile the Deportation Data Project stays parquet vs our current data.

Outputs the facts a non-technical professor needs to decide whether to switch:
  - Actual date coverage (real min/max book-in / book-out)
  - Volume comparison vs current pipeline
  - Schema alignment
  - County coverage already present in their data
  - Sample of any data the FY12-23 FOIA files have that stays does NOT
"""

import pandas as pd

PARQUET = r"C:\Users\xief\Downloads\detention-stays_filtered_20260528_033202.parquet"

print("Loading parquet ...")
s = pd.read_parquet(PARQUET)
print(f"Shape: {s.shape[0]:,} stays x {s.shape[1]} columns")
print()

for col in ["stay_book_in_date_time", "book_in_date_time_first",
            "stay_book_out_date_time", "book_out_date_time_last"]:
    if col in s.columns:
        ser = pd.to_datetime(s[col], errors="coerce", utc=True)
        print(f"{col}: min={ser.min()}, max={ser.max()}, "
              f"non-null={ser.notna().sum():,}")
print()

s["year"] = pd.to_datetime(s["stay_book_in_date_time"], errors="coerce", utc=True).dt.year
print("Stays by book-in year (top 20 years):")
print(s["year"].value_counts().sort_index().tail(25).to_string())
print()

print("County coverage in pre-resolved columns:")
for col in ["county_first", "county_longest", "county_last"]:
    n_set = s[col].astype(str).str.strip().replace("None", "").astype(bool).sum()
    print(f"  {col}: {n_set:,} / {len(s):,} non-empty ({100*n_set/len(s):.1f}%)")
print()

print("Top 15 detention_facility_code_longest in stays:")
print(s["detention_facility_code_longest"].value_counts().head(15).to_string())
print()

print(f"Unique persons (unique_identifier): {s['unique_identifier'].nunique():,}")
print(f"Stays per person quantiles:")
print(s.groupby("unique_identifier").size().describe().to_string())
print()

print("---- COMPARISON TO CURRENT PIPELINE ----")
print("Our pipeline (FY12-FY23 ICE FOIA detention extracts):")
print("  unit of analysis: detention episode (one row per book-in event)")
print("  rows: ~8,458,563")
print("  time: FY2012 - FY2023 (book-in date)")
print("  county resolution: built locally via crosswalk")
print()
print("DDP stays parquet:")
print(f"  unit of analysis: STAY (a custody journey that may span multiple facilities/stints)")
print(f"  rows: {len(s):,}")
print(f"  stints column 'n_stints' distribution:")
print(s["n_stints"].describe().to_string())
