"""Debug the NM 44-stay regression after the clean-FIPS update."""
import pandas as pd

PQ = r"C:\Users\xief\Downloads\detention-stays_filtered_20260528_033200.parquet"
df = pd.read_parquet(PQ)
df = df[df["book_in_date_time_first"] >= "2023-12-01"]

nm_blank = df[
    df["state_longest"].astype(str).str.upper().eq("NM")
    & df["county_longest"].isna()
]
print(f"NM blank-county stays: {len(nm_blank)}")
print()
print("top facility codes among NM blank-county stays:")
print(nm_blank["detention_facility_code_longest"].value_counts().head(10).to_string())
print()

cw = pd.read_csv("data/processed/facility_crosswalk.csv", dtype=str).fillna("")
codes = nm_blank["detention_facility_code_longest"].value_counts().head(10).index
for c in codes:
    row = cw[cw["facility_code"] == c]
    if len(row) == 0:
        print(f"  {c}: NOT IN CROSSWALK")
    else:
        r = row.iloc[0]
        print(
            f"  {c}: {r['facility_name'][:30]:30s} county_fips={r['county_fips']!r}"
            f" county={r['county_name']!r} state={r['state_abbr']!r}"
            f" source={r.get('resolution_source','')!r}"
        )
