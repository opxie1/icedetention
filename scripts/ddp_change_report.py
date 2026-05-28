"""Show every facility where DDP changed our prior county assignment."""

import pandas as pd

cw = pd.read_csv("data/processed/facility_crosswalk.csv", dtype=str).fillna("")
cw["n_episodes"] = cw["n_episodes"].astype(int)

ddp_now = cw[cw["resolution_source"] == "ddp"].copy()
print(f"Total DDP-resolved: {len(ddp_now)} facilities, "
      f"{ddp_now['n_episodes'].sum():,} episodes")
print()

ddp_src = pd.read_csv("references/ddp_facilities.csv", dtype=str).fillna("")
ddp_src["county_fips_code"] = ddp_src["county_fips_code"].str.zfill(5)
ddp_src = ddp_src.rename(columns={"detention_facility_code": "facility_code"})

from ice_pipeline.known_facilities import resolve_facility

rows = []
for _, r in ddp_now.iterrows():
    prior = resolve_facility(r["facility_name"], r["facility_code"])
    prior_state = prior.state_abbr if prior else ""
    prior_county = prior.county_name if prior else ""
    same_state = (prior_state == r["state_abbr"])
    pc_first = prior_county.split()[0].lower() if prior_county else ""
    same_county_token = bool(pc_first) and pc_first in r["county_name"].lower()
    if prior is not None and not (same_state and same_county_token):
        rows.append({
            "facility_name": r["facility_name"],
            "code": r["facility_code"],
            "n_episodes": r["n_episodes"],
            "prior_heuristic": f"{prior_state} / {prior_county}",
            "ddp_authoritative": f"{r['state_abbr']} / {r['county_name']}",
        })

if rows:
    df = pd.DataFrame(rows).sort_values("n_episodes", ascending=False)
    print(f"Facilities where DDP CHANGED our prior answer: {len(df)}")
    print(f"  total episodes affected: {df['n_episodes'].sum():,}")
    print()
    print(df.head(40).to_string(index=False))
