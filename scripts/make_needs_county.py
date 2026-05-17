"""Build simple 'fill in the county' sheets containing only unresolved rows."""

import pandas as pd

proc = "data/processed"
refs = "references"

# --- Detention facilities -------------------------------------------------
unmapped = pd.read_csv(f"{proc}/unmapped_facilities.csv", dtype=str)
tmpl = pd.read_csv(f"{refs}/facility_overrides_template.csv", dtype=str).fillna("")

key = ["facility_name", "facility_code"]
need = unmapped.merge(tmpl[key + ["state_abbr"]], on=key, how="left")
need["n_episodes"] = need["n_episodes"].astype(int)
need = need.sort_values("n_episodes", ascending=False)

out = pd.DataFrame({
    "facility_name": need["facility_name"],
    "number_of_detentions": need["n_episodes"],
    "state": need["state_abbr"].fillna(""),
    "county": "",
    "facility_code_do_not_edit": need["facility_code"],
})
out.to_csv(f"{refs}/facilities_need_county.csv", index=False)
print(f"facilities_need_county.csv: {len(out)} rows")

# --- Encounter sites ------------------------------------------------------
usites = pd.read_csv(f"{proc}/unmapped_sites.csv", dtype=str)
stmpl = pd.read_csv(f"{refs}/site_overrides_template.csv", dtype=str).fillna("")

sneed = usites.merge(
    stmpl[["responsible_site", "state_abbr"]], on="responsible_site", how="left"
)
sneed["n_events"] = sneed["n_events"].astype(int)
sneed = sneed.sort_values("n_events", ascending=False)

sout = pd.DataFrame({
    "site_name": sneed["responsible_site"],
    "number_of_encounters": sneed["n_events"],
    "state": sneed["state_abbr"].fillna(""),
    "county": "",
})
sout.to_csv(f"{refs}/sites_need_county.csv", index=False)
print(f"sites_need_county.csv: {len(sout)} rows")
