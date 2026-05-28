"""Categorize unmapped rows by whether they can be resolved DETERMINISTICALLY.

Ground truth = the FIPS reference the professors provided. A "{X} COUNTY ..."
name is only auto-resolvable if X appears in EXACTLY ONE state in that file.
Anything ambiguous or with no county token is left for manual review.
No external data, no guessing.
"""

import re
import pandas as pd

fips = pd.read_csv("references/fips_state_county.csv", dtype={"fips": str})
fips["fips"] = fips["fips"].str.zfill(5)


def norm(s):
    s = str(s).strip().lower().replace(".", "").replace(",", "")
    for tok in (" parish", " county", " coun", " count", " borough",
                " municipality", " census area", " city and borough"):
        if s.endswith(tok):
            s = s[: -len(tok)]
    return " ".join(s.split())


fips["cn"] = fips["county_name"].apply(norm)
by_name: dict[str, set] = {}
for _, r in fips.iterrows():
    by_name.setdefault(r["cn"], set()).add(r["state_name"])

COUNTY_RE = re.compile(
    r"\b([A-Z][A-Z .'\-/]*?)\s+COUNTY\b"
)


def classify(name: str):
    up = name.upper()
    m = COUNTY_RE.search(up)
    if not m:
        return ("no_county_token", "", "")
    cand = norm(m.group(1))
    states = by_name.get(cand)
    if not states:
        return ("county_not_in_fips", cand, "")
    if len(states) == 1:
        return ("unique_resolvable", cand, next(iter(states)))
    return (f"ambiguous_{len(states)}_states", cand, "|".join(sorted(states)))


for label, path, vol in [
    ("FACILITIES", "data/processed/unmapped_facilities.csv", "n_episodes"),
    ("SITES", "data/processed/unmapped_sites.csv", "n_events"),
]:
    df = pd.read_csv(path, dtype=str)
    namecol = "facility_name" if "facility_name" in df.columns else "responsible_site"
    df[vol] = df[vol].astype(int)
    rows = []
    for _, r in df.iterrows():
        cat, cand, st = classify(r[namecol])
        rows.append((r[namecol], r[vol], cat, cand, st))
    res = pd.DataFrame(rows, columns=[namecol, vol, "category", "county_guess", "state(s)"])
    print("=" * 78)
    print(f"{label}: {len(res)} unmapped rows")
    print("=" * 78)
    summary = res.groupby("category").agg(
        n=("category", "size"), volume=(vol, "sum")
    ).sort_values("volume", ascending=False)
    print(summary.to_string())
    print()
    print("-- uniquely resolvable (county name in exactly one state) --")
    u = res[res["category"] == "unique_resolvable"].sort_values(vol, ascending=False)
    print(u.head(40).to_string(index=False))
    print(f"  ... {len(u)} total uniquely resolvable, {u[vol].sum():,} {vol}")
    print()
