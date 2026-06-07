"""Check how many blank-county DDP stays can be rescued via our FOIA crosswalk."""
import pandas as pd

PQ = r"C:\Users\xief\Downloads\detention-stays_filtered_20260528_033200.parquet"

df = pd.read_parquet(PQ)
df = df[df["book_in_date_time_first"] >= "2023-12-01"]
blank = df[df["county_longest"].isna()].copy()
print(f"blank-county stays after Dec 2023 cutoff: {len(blank):,}")
print()

cw = pd.read_csv("data/processed/facility_crosswalk.csv", dtype=str).fillna("")
fac2county = dict(zip(cw["facility_code"], cw["county_fips"]))
fac2name = dict(zip(cw["facility_code"], cw["county_name"]))
fac2state = dict(zip(cw["facility_code"], cw["state_abbr"]))

blank["rescued_fips"] = blank["detention_facility_code_longest"].map(fac2county)
mapped = blank[blank["rescued_fips"].astype(str).str.len() == 5]
print(f"rescued via FOIA crosswalk: {len(mapped):,} ({100*len(mapped)/len(blank):.1f}%)")
print()

still = blank[blank["rescued_fips"].astype(str).str.len() != 5]
top = still["detention_facility_code_longest"].value_counts().head(15)
print(f"still unmapped: {len(still):,}")
print("top still-unmapped facility codes:")
print(top.to_string())
print()

key_blank = "detention_facility_code_longest"
print(f"distinct codes among blank: {blank[key_blank].nunique()}")
print(f"distinct codes among rescued: {mapped[key_blank].nunique()}")
print(f"distinct codes still unmapped: {still[key_blank].nunique()}")
