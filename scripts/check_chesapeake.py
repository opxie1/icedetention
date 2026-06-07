"""Investigate why VA Chesapeake stays did not resolve."""
import pandas as pd

fips = pd.read_csv("references/fips_state_county.csv", dtype={"fips": str})
fips["fips"] = fips["fips"].str.zfill(5)
chk = fips[
    (fips["state_name"] == "Virginia")
    & (fips["county_name"].str.contains("Chesapeake", case=False, na=False))
]
print("Chesapeake VA in FIPS file:")
print(chk.to_string(index=False))
print()

va_cities = fips[
    (fips["state_name"] == "Virginia")
    & (fips["county_name"].str.contains("city", case=False, na=False))
]
print(f"VA rows containing 'city' (independent cities): {len(va_cities)}")
print(va_cities.head(8).to_string(index=False))
print()

PQ = r"C:\Users\xief\Downloads\detention-stays_filtered_20260528_033200.parquet"
df = pd.read_parquet(
    PQ, columns=["book_in_date_time_first", "state_longest", "county_longest"]
)
df = df[df["book_in_date_time_first"] >= "2023-12-01"]
ches = df[
    df["state_longest"].astype(str).str.upper().eq("VA")
    & df["county_longest"].astype(str).str.contains("Chesapeake", case=False, na=False)
]
print(f"DDP raw rows with VA + Chesapeake: {len(ches)}")
print(ches[["state_longest", "county_longest"]].head().to_string(index=False))
