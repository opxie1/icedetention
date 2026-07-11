"""Build county-year population panels and merge onto the detention panels.

Variables (per Prof. Polo-Muro's 2026-07 request):
  pop_total      - PEP county totals. V2019 flat file for 2012-2019,
                   V2025 flat file for 2020-2025 (one vintage per decade
                   block; each vintage revises prior 2020s years).
                   PR municipios are not in the PEP national files, so PR
                   totals come from ACS B05001_001E (flagged in source col).
  pop_hispanic   - ACS 5-year table B03002 (B03002_012E), vintages 2012-2024.
                   Chosen over annual PEP cc-est because ACS covers Puerto
                   Rico and matches the non-citizen source. (PEP annual is
                   the documented alternative.)
  pop_noncitizen - ACS 5-year table B05001 (B05001_006E = "Not a U.S.
                   citizen"), vintages 2012-2024. ACS-only variable; 5-year
                   estimates required because 1-year ACS excludes counties
                   under 65k population.

Coverage: population reaches 2025 (PEP) / 2024 (ACS). Detention runs to
2026-03. Years past a variable's last real value are carried forward and
flagged via *_refyear columns.

Geography: keyed on 5-digit county FIPS matching the detention panel.
  - CT: detention uses legacy counties (only 09003 Hartford appears).
    ACS vintages through 2021 and PEP through V2021 publish legacy CT
    counties; 2022+ publish planning regions. Legacy CT rows are carried
    forward past their last real year (flagged); planning-region rows are
    also kept for anyone merging on the new basis.
  - Old FIPS in early ACS vintages are normalized: 46113->46102,
    02270->02158, 51515 summed into 51019. 02261 (Valdez-Cordova, split
    2019) is kept as-is and flagged; it never appears in the detention data.
  - Island territories (GU/VI/MP) have no annual Census population program;
    their detention rows will not receive population (expected, documented).

API key: env CENSUS_API_KEY or references/census_api_key.txt (gitignored).
"""
from __future__ import annotations

import io
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

import pandas as pd

REPO = Path(r"C:\Users\xief\.local\bin\ucmerced")
PROC = REPO / "data" / "processed"
RAW = REPO / "data" / "raw_population"
RAW.mkdir(parents=True, exist_ok=True)

PEP_V2019 = "https://www2.census.gov/programs-surveys/popest/datasets/2010-2019/counties/totals/co-est2019-alldata.csv"
PEP_V2025 = "https://www2.census.gov/programs-surveys/popest/datasets/2020-2025/counties/totals/co-est2025-alldata.csv"
PEP_V2021 = "https://www2.census.gov/programs-surveys/popest/datasets/2020-2021/counties/totals/co-est2021-alldata.csv"

ACS_YEARS = list(range(2012, 2025))
FIPS_ALIAS = {"46113": "46102", "02270": "02158"}
BEDFORD_CITY, BEDFORD_COUNTY = "51515", "51019"

FINAL_YEARS = list(range(2012, 2027))


def api_key() -> str:
    k = os.environ.get("CENSUS_API_KEY", "").strip()
    if not k:
        f = REPO / "references" / "census_api_key.txt"
        if f.is_file():
            k = f.read_text().strip()
    if not k:
        sys.exit("No Census API key found (env CENSUS_API_KEY or references/census_api_key.txt).")
    return k


def fetch(url: str, dest: Path, desc: str) -> Path:
    if dest.exists() and dest.stat().st_size > 0:
        print(f"  [cached] {desc}: {dest.name}")
        return dest
    print(f"  [fetch] {desc}: {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "research-data-build/1.0"})
    with urllib.request.urlopen(req, timeout=120) as r, open(dest, "wb") as f:
        f.write(r.read())
    return dest


def acs_pull(year: int, varlist: str, key: str, geo: str = "for=county:*") -> list[list[str]]:
    url = (f"https://api.census.gov/data/{year}/acs/acs5"
           f"?get={varlist}&{geo}&key={key}")
    req = urllib.request.Request(url, headers={"User-Agent": "research-data-build/1.0"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            if attempt == 2:
                raise
            print(f"    retry {year} after error: {e}")
            time.sleep(5)
    return []


def build_pep_totals() -> pd.DataFrame:
    v19 = pd.read_csv(fetch(PEP_V2019, RAW / "co-est2019-alldata.csv", "PEP V2019"),
                      encoding="latin-1", dtype=str)
    v25 = pd.read_csv(fetch(PEP_V2025, RAW / "co-est2025-alldata.csv", "PEP V2025"),
                      encoding="latin-1", dtype=str)
    v21 = pd.read_csv(fetch(PEP_V2021, RAW / "co-est2021-alldata.csv", "PEP V2021 (CT legacy 2020-21)"),
                      encoding="latin-1", dtype=str)

    rows = []

    def melt(df: pd.DataFrame, years: list[int], vintage: str,
             state_filter=None) -> None:
        d = df[df["SUMLEV"] == "050"].copy()
        if state_filter is not None:
            d = d[d["STATE"] == state_filter]
        d["county_fips"] = d["STATE"].str.zfill(2) + d["COUNTY"].str.zfill(3)
        for y in years:
            col = f"POPESTIMATE{y}"
            if col not in d.columns:
                continue
            for _, r in d.iterrows():
                rows.append((r["county_fips"], y, int(r[col]), vintage))

    melt(v19, list(range(2012, 2020)), "PEP V2019")
    melt(v25, list(range(2020, 2026)), "PEP V2025")
    melt(v21, [2020, 2021], "PEP V2021 (CT legacy)", state_filter="09")

    out = pd.DataFrame(rows, columns=["county_fips", "year", "pop_total", "pop_total_vintage"])
    out = out.drop_duplicates(subset=["county_fips", "year"], keep="first")
    return out


def build_acs() -> tuple[pd.DataFrame, pd.DataFrame]:
    key = api_key()
    hisp_rows, ncit_rows = [], []
    for y in ACS_YEARS:
        cache = RAW / f"acs5_{y}.json"
        if cache.exists():
            data = json.loads(cache.read_text(encoding="utf-8"))
            print(f"  [cached] ACS {y}")
        else:
            print(f"  [pull] ACS {y} (B03002 + B05001)")
            data = {
                "b03002": acs_pull(y, "NAME,B03002_001E,B03002_012E,B03002_012M", key),
                "b05001": acs_pull(y, "NAME,B05001_001E,B05001_006E,B05001_006M", key),
            }
            cache.write_text(json.dumps(data), encoding="utf-8")
        if "b05001pr" not in data:
            print(f"  [pull] ACS {y} B05001PR (Puerto Rico)")
            data["b05001pr"] = acs_pull(
                y, "NAME,B05001PR_001E,B05001PR_006E,B05001PR_006M", key,
                geo="for=county:*&in=state:72")
            cache.write_text(json.dumps(data), encoding="utf-8")
        hdr05, *recs05 = data["b05001"]
        non_pr = [r for r in recs05 if r[hdr05.index("state")] != "72"]
        hdrpr, *recspr = data["b05001pr"]
        remap = [hdrpr.index(c) for c in
                 ("NAME", "B05001PR_001E", "B05001PR_006E", "B05001PR_006M",
                  "state", "county")]
        pr_rows = [[r[i] for i in remap] for r in recspr]
        data["b05001"] = [hdr05] + non_pr + pr_rows

        for tab, sink in (("b03002", hisp_rows), ("b05001", ncit_rows)):
            hdr, *recs = data[tab]
            idx = {c: i for i, c in enumerate(hdr)}
            for rec in recs:
                fips = rec[idx["state"]].zfill(2) + rec[idx["county"]].zfill(3)
                vals = []
                for c in hdr:
                    if c.startswith("B0"):
                        v = rec[idx[c]]
                        v = None if v is None or float(v) < 0 else float(v)
                        vals.append(v)
                sink.append((fips, y, *vals))

    hisp = pd.DataFrame(hisp_rows, columns=["county_fips", "year", "acs_total_b03002",
                                            "pop_hispanic", "pop_hispanic_moe"])
    ncit = pd.DataFrame(ncit_rows, columns=["county_fips", "year", "acs_total_b05001",
                                            "pop_noncitizen", "pop_noncitizen_moe"])

    def normalize(df: pd.DataFrame) -> pd.DataFrame:
        df["county_fips"] = df["county_fips"].replace(FIPS_ALIAS)
        bc = df["county_fips"] == BEDFORD_CITY
        if bc.any():
            df.loc[bc, "county_fips"] = BEDFORD_COUNTY
            num = [c for c in df.columns if c not in ("county_fips", "year")]
            df = df.groupby(["county_fips", "year"], as_index=False)[num].sum(min_count=1)
        return df.drop_duplicates(subset=["county_fips", "year"], keep="first")

    return normalize(hisp), normalize(ncit)


def carry_forward(panel: pd.DataFrame, col: str, refcol: str) -> pd.DataFrame:
    panel = panel.sort_values(["county_fips", "year"]).copy()
    panel[refcol] = panel["year"].where(panel[col].notna())
    panel[col] = panel.groupby("county_fips")[col].ffill()
    panel[refcol] = panel.groupby("county_fips")[refcol].ffill()
    return panel


def main() -> None:
    print("=== 1. PEP totals ===")
    pep = build_pep_totals()
    print(f"  pep rows: {len(pep):,}, years {pep.year.min()}..{pep.year.max()}, "
          f"counties {pep.county_fips.nunique():,}")

    print("=== 2. ACS pulls ===")
    hisp, ncit = build_acs()
    print(f"  hispanic rows: {len(hisp):,}; noncitizen rows: {len(ncit):,}")

    print("=== 3. Assemble county-year population panel ===")
    counties = sorted(set(pep.county_fips) | set(hisp.county_fips) | set(ncit.county_fips))
    grid = pd.MultiIndex.from_product([counties, FINAL_YEARS],
                                      names=["county_fips", "year"]).to_frame(index=False)
    panel = (grid
             .merge(pep, on=["county_fips", "year"], how="left")
             .merge(hisp, on=["county_fips", "year"], how="left")
             .merge(ncit, on=["county_fips", "year"], how="left"))

    pr = panel["county_fips"].str.startswith("72") & panel["pop_total"].isna()
    panel.loc[pr, "pop_total"] = panel.loc[pr, "acs_total_b05001"].fillna(
        panel.loc[pr, "acs_total_b03002"])
    panel.loc[pr & panel["pop_total"].notna(), "pop_total_vintage"] = "ACS5 total (PR)"

    panel = carry_forward(panel, "pop_total", "pop_total_refyear")
    panel = carry_forward(panel, "pop_hispanic", "pop_hispanic_refyear")
    panel = carry_forward(panel, "pop_noncitizen", "pop_noncitizen_refyear")
    panel["pop_total_vintage"] = panel.groupby("county_fips")["pop_total_vintage"].ffill()

    panel["pct_hispanic"] = panel["pop_hispanic"] / panel["acs_total_b03002"].where(
        panel["acs_total_b03002"] > 0)
    panel["pct_hispanic"] = panel.groupby("county_fips")["pct_hispanic"].ffill()
    panel["pct_noncitizen"] = panel["pop_noncitizen"] / panel["acs_total_b05001"].where(
        panel["acs_total_b05001"] > 0)
    panel["pct_noncitizen"] = panel.groupby("county_fips")["pct_noncitizen"].ffill()

    fipsref = pd.read_csv(REPO / "references" / "fips_state_county.csv", dtype={"fips": str})
    fipsref["fips"] = fipsref["fips"].str.zfill(5)
    panel = panel.merge(fipsref.rename(columns={"fips": "county_fips"}),
                        on="county_fips", how="left")

    ct_legacy = panel["county_fips"].isin(
        [f"090{n:02d}" for n in range(1, 16, 2)])
    ct_newreg = panel["county_fips"].str.startswith("091")
    panel["geo_basis"] = ""
    panel.loc[ct_legacy, "geo_basis"] = "CT-legacy-county"
    panel.loc[ct_newreg, "geo_basis"] = "CT-planning-region"

    keep = ["county_fips", "county_name", "state_name", "year", "geo_basis",
            "pop_total", "pop_total_vintage", "pop_total_refyear",
            "pop_hispanic", "pop_hispanic_moe", "pct_hispanic", "pop_hispanic_refyear",
            "pop_noncitizen", "pop_noncitizen_moe", "pct_noncitizen", "pop_noncitizen_refyear"]
    panel = panel[keep].sort_values(["county_fips", "year"])
    out1 = PROC / "county_year_population.csv"
    panel.to_csv(out1, index=False)
    print(f"  wrote {out1.name}: {len(panel):,} rows, {panel.county_fips.nunique():,} counties")

    print("=== 4. Merge onto detention panels ===")
    popcols = ["county_fips", "year", "pop_total", "pop_hispanic", "pop_noncitizen",
               "pct_hispanic", "pct_noncitizen",
               "pop_total_refyear", "pop_hispanic_refyear", "pop_noncitizen_refyear"]
    pslim = panel[popcols]

    cy = pd.read_csv(PROC / "county_year_detention_combined.csv", dtype={"county_fips": str})
    cy["county_fips"] = cy["county_fips"].str.zfill(5)
    cy = cy.merge(pslim, on=["county_fips", "year"], how="left")
    cy["detained_per_100k"] = 100_000 * cy["n_detained"] / cy["pop_total"].where(cy["pop_total"] > 0)
    out2 = PROC / "county_year_detention_population.csv"
    cy.to_csv(out2, index=False)

    cm = pd.read_csv(PROC / "county_month_detention_combined.csv", dtype={"county_fips": str})
    cm["county_fips"] = cm["county_fips"].str.zfill(5)
    cm = cm.merge(pslim, on=["county_fips", "year"], how="left")
    cm["detained_per_100k"] = 100_000 * cm["n_detained"] / cm["pop_total"].where(cm["pop_total"] > 0)
    out3 = PROC / "county_month_detention_population.csv"
    cm.to_csv(out3, index=False)

    matched = cy["pop_total"].notna().mean()
    unmatched = cy[cy["pop_total"].isna()]["county_fips"].str[:2].value_counts()
    print(f"  wrote {out2.name}: {len(cy):,} rows; population matched {100*matched:.2f}%")
    print(f"  wrote {out3.name}: {len(cm):,} rows")
    print("  unmatched detention rows by state prefix (expected: 66/69/78 territories):")
    print(unmatched.to_string())


if __name__ == "__main__":
    main()
