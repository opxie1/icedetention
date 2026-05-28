"""Cross-check our crosswalk against the Deportation Data Project facility list.

Produces three reports:
  1. Unmapped facilities that DDP CAN resolve (would be a clean win).
  2. Existing resolutions where DDP and we disagree on the county.
  3. Facilities in our data not present in the DDP list (these stay manual).
"""

import pandas as pd

ddp = pd.read_excel(
    r"C:\Users\xief\Downloads\detention-facilities_filtered_20260528_032745.xlsx",
    sheet_name="data",
    dtype={"detention_facility_code": str, "county_fips_code": str},
)
ddp = ddp[ddp["detention_facility_code"].notna()].copy()
ddp["code"] = ddp["detention_facility_code"].str.upper().str.strip()
ddp["fips5"] = ddp["county_fips_code"].fillna("").str.split(".").str[0].str.zfill(5)
ddp.loc[ddp["fips5"] == "00000", "fips5"] = ""

cw = pd.read_csv(
    "data/processed/facility_crosswalk.csv",
    dtype={"facility_code": str, "county_fips": str},
).fillna("")
cw["code"] = cw["facility_code"].str.upper().str.strip()
cw["fips5"] = cw["county_fips"].astype(str).str.zfill(5).replace("00000", "")

unmapped = cw[cw["fips5"] == ""].copy()
hit = unmapped.merge(
    ddp[["code", "name", "city", "state", "county", "fips5"]],
    on="code", how="left", suffixes=("", "_ddp"),
)
resolvable = hit[hit["fips5_ddp"] != ""].copy()
print("=" * 76)
print(f"UNMAPPED FACILITIES WE COULD RESOLVE VIA DDP: "
      f"{len(resolvable)} of {len(unmapped)} unmapped")
print("=" * 76)
ep_resolvable = resolvable["n_episodes"].astype(int).sum()
print(f"  total episodes recoverable: {ep_resolvable:,}")
print()
print(resolvable[[
    "facility_name", "facility_code", "n_episodes", "city", "state",
    "county", "fips5_ddp",
]].sort_values("n_episodes", key=lambda s: s.astype(int), ascending=False
).head(30).to_string(index=False))
print()

mapped = cw[cw["fips5"] != ""].copy()
both = mapped.merge(
    ddp[["code", "name", "county", "state", "fips5"]],
    on="code", how="inner", suffixes=("_us", "_ddp"),
)
disagree = both[
    (both["fips5_ddp"] != "") & (both["fips5_us"] != both["fips5_ddp"])
].copy()
print("=" * 76)
print(f"EXISTING RESOLUTIONS WHERE DDP DISAGREES: {len(disagree)}")
print("=" * 76)
if len(disagree):
    print(disagree[[
        "facility_name", "facility_code", "county_name", "fips5_us",
        "county", "fips5_ddp", "n_episodes",
    ]].sort_values("n_episodes", key=lambda s: s.astype(int), ascending=False
    ).head(40).to_string(index=False))
print()

no_ddp = cw[~cw["code"].isin(ddp["code"])].copy()
no_ddp_unmapped = no_ddp[no_ddp["fips5"] == ""]
print("=" * 76)
print(f"OUR FACILITIES NOT IN DDP LIST AT ALL: {len(no_ddp)}")
print(f"  of which still unmapped after DDP join: {len(no_ddp_unmapped)}")
print("=" * 76)
print(no_ddp_unmapped[["facility_name", "facility_code", "n_episodes"]].sort_values(
    "n_episodes", key=lambda s: s.astype(int), ascending=False
).head(20).to_string(index=False))
