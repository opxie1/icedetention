"""End-to-end thoroughness check. Prints PASS / FAIL per assertion.

Covers: source data integrity, pipeline modules, FIPS reference,
panel schema, coverage numbers, splice integrity, DDP corrections,
Catalina's overrides, README accuracy, Dropbox <-> repo md5 match,
git state, junk file scan.
"""
from __future__ import annotations

import hashlib
import re
import subprocess
import sys
from pathlib import Path

import pandas as pd

REPO = Path(r"C:\Users\xief\.local\bin\ucmerced")
DBOX = Path(r"C:\Users\xief\Dropbox\ethan xie\ice crosswalk")

results = []


def check(label: str, ok: bool, detail: str = "") -> None:
    flag = "PASS" if ok else "FAIL"
    line = f"[{flag}] {label}"
    if detail:
        line += f"  ({detail})"
    print(line)
    results.append((flag, label, detail))


def section(name: str) -> None:
    print()
    print("=" * 70)
    print(f" {name}")
    print("=" * 70)


# ---------------------------------------------------------------------------
section("1. Source data files")
# ---------------------------------------------------------------------------
DOWNLOADS = Path(r"C:\Users\xief\Downloads")
for name in [
    "detention-stays_filtered_20260528_033200.parquet",
    "detention-facilities_filtered_20260528_032745.xlsx",
]:
    check(f"source: {name}", (DOWNLOADS / name).is_file())

foia_files = sorted(DOWNLOADS.glob("2023-ICFO_42034_Detentions_FY*_LESA*"))
check(
    "FOIA detention workbooks (FY12-FY23)",
    len(foia_files) == 12,
    f"found {len(foia_files)} files",
)

ero = list(DOWNLOADS.glob("2025-ICLI-00019_2024-ICFO-39357_ERO Encounters_*"))
check("ERO Encounters workbook", len(ero) >= 1)

# ---------------------------------------------------------------------------
section("2. Pipeline modules import cleanly")
# ---------------------------------------------------------------------------
for mod in [
    "ice_pipeline.config",
    "ice_pipeline.known_facilities",
    "ice_pipeline.extract",
    "ice_pipeline.crosswalk",
    "ice_pipeline.aggregate",
    "ice_pipeline.encounters",
    "ice_pipeline.stays",
    "ice_pipeline.cli",
]:
    try:
        __import__(mod)
        check(f"import {mod}", True)
    except Exception as e:
        check(f"import {mod}", False, str(e))

# ---------------------------------------------------------------------------
section("3. FIPS reference is clean (no truncation)")
# ---------------------------------------------------------------------------
fips = pd.read_csv(REPO / "references/fips_state_county.csv", dtype={"fips": str})
check("FIPS file has ~3235 rows", abs(len(fips) - 3235) < 5, f"{len(fips)} rows")
check(
    "FIPS fips column is 5-digit string",
    fips["fips"].str.len().eq(5).all(),
    f"min/max len: {fips['fips'].str.len().min()}/{fips['fips'].str.len().max()}",
)
truncated_lens = (fips["county_name"].str.len() == 16).sum()
check(
    "no 16-char-truncated county names",
    truncated_lens < 5,
    f"{truncated_lens} rows have exact-16-char names (Census originals)",
)

key_checks = {
    "02170": "Matanuska-Susitna",
    "02020": "Anchorage",
    "51550": "Chesapeake",
    "72127": "San Juan",
    "72031": "Carolina",
    "72061": "Guaynabo",
    "66010": "Guam",
    "78030": "St. Thomas",
    "35013": "Doña Ana",
}
fips_map = dict(zip(fips["fips"], fips["county_name"]))
for f, expect in key_checks.items():
    actual = fips_map.get(f, "MISSING")
    ok = expect.lower() in actual.lower()
    check(f"FIPS {f} contains {expect!r}", ok, f"got {actual!r}")

# ---------------------------------------------------------------------------
section("4. All 16 deliverable files exist in repo")
# ---------------------------------------------------------------------------
DELIVERABLES = {
    "README_PANELS.txt": "data/processed/README_PANELS.txt",
    "county_year_panel.csv": "data/processed/county_year_panel.csv",
    "county_month_panel.csv": "data/processed/county_month_panel.csv",
    "county_year_encounters_panel.csv": "data/processed/county_year_encounters_panel.csv",
    "county_month_encounters_panel.csv": "data/processed/county_month_encounters_panel.csv",
    "county_year_stays_panel.csv": "data/processed/county_year_stays_panel.csv",
    "county_month_stays_panel.csv": "data/processed/county_month_stays_panel.csv",
    "facility_crosswalk.csv": "data/processed/facility_crosswalk.csv",
    "facility_crosswalk_review.csv": "data/processed/facility_crosswalk_review.csv",
    "site_crosswalk.csv": "data/processed/site_crosswalk.csv",
    "site_crosswalk_review.csv": "data/processed/site_crosswalk_review.csv",
    "unmapped_facilities.csv": "data/processed/unmapped_facilities.csv",
    "unmapped_sites.csv": "data/processed/unmapped_sites.csv",
    "unmapped_stays.csv": "data/processed/unmapped_stays.csv",
    "facilities_need_county.csv": "references/facilities_need_county.csv",
    "sites_need_county.csv": "references/sites_need_county.csv",
}
for fn, rel in DELIVERABLES.items():
    p = REPO / rel
    ok = p.is_file() and p.stat().st_size > 0
    check(f"repo file: {fn}", ok, f"{p.stat().st_size if p.exists() else 0} B")

# ---------------------------------------------------------------------------
section("5. CSV files are valid and have expected columns")
# ---------------------------------------------------------------------------
PANEL_COLS_DETENTION = {
    "county_fips", "county_name", "state_abbr", "state_name",
    "n_episodes", "n_unique_persons", "detention_days",
    "n_unusual_episodes",
}
for fn in ["county_year_panel.csv", "county_month_panel.csv"]:
    df = pd.read_csv(REPO / "data/processed" / fn, dtype={"county_fips": str})
    cols = set(df.columns)
    missing = PANEL_COLS_DETENTION - cols
    check(
        f"{fn}: required columns present",
        not missing,
        f"missing={missing}" if missing else f"{len(df):,} rows, cols={sorted(cols)}",
    )
    check(
        f"{fn}: county_fips is 5-digit",
        df["county_fips"].str.zfill(5).str.len().eq(5).all(),
    )

PANEL_COLS_STAYS = {
    "county_fips", "county_name", "state_abbr", "state_name",
    "n_stays", "n_unique_persons", "n_stints_total", "total_days",
}
for fn in ["county_year_stays_panel.csv", "county_month_stays_panel.csv"]:
    df = pd.read_csv(REPO / "data/processed" / fn, dtype={"county_fips": str})
    cols = set(df.columns)
    missing = PANEL_COLS_STAYS - cols
    check(
        f"{fn}: required columns present",
        not missing,
        f"missing={missing}" if missing else f"{len(df):,} rows",
    )
    check(
        f"{fn}: county_fips is 5-digit",
        df["county_fips"].str.zfill(5).str.len().eq(5).all(),
    )

PANEL_COLS_ENC = {
    "county_fips", "county_name", "state_abbr", "state_name",
    "n_events", "n_unique_persons", "n_unusual_events",
}
for fn in ["county_year_encounters_panel.csv", "county_month_encounters_panel.csv"]:
    df = pd.read_csv(REPO / "data/processed" / fn, dtype={"county_fips": str})
    cols = set(df.columns)
    missing = PANEL_COLS_ENC - cols
    check(
        f"{fn}: required columns present",
        not missing,
        f"missing={missing}" if missing else f"{len(df):,} rows",
    )

# ---------------------------------------------------------------------------
section("6. Coverage matches README claims")
# ---------------------------------------------------------------------------
cw = pd.read_csv(REPO / "data/processed/facility_crosswalk.csv", dtype=str).fillna("")
mapped = cw[cw["county_fips"] != ""]
total_eps = cw["n_episodes"].astype(int).sum()
mapped_eps = mapped["n_episodes"].astype(int).sum()
fac_cov = 100 * len(mapped) / len(cw)
eps_cov = 100 * mapped_eps / total_eps
check(
    "FOIA facility coverage = 96.3% (1099/1141)",
    abs(fac_cov - 96.3) < 0.1 and len(mapped) == 1099 and len(cw) == 1141,
    f"{len(mapped)}/{len(cw)} = {fac_cov:.2f}%",
)
check(
    "FOIA episode coverage = 99.96% (8,455,175 / 8,458,563)",
    mapped_eps == 8_455_175 and total_eps == 8_458_563,
    f"{mapped_eps:,} / {total_eps:,}",
)

yr_stays = pd.read_csv(REPO / "data/processed/county_year_stays_panel.csv")
un_stays = pd.read_csv(REPO / "data/processed/unmapped_stays.csv")
mapped_stays = yr_stays["n_stays"].sum()
unmapped_stays_n = un_stays["n_stays"].sum()
total_stays = mapped_stays + unmapped_stays_n
stays_cov = 100 * mapped_stays / total_stays
check(
    "Stays coverage >= 99.80% (was 94.1% before rescue)",
    stays_cov >= 99.80,
    f"{mapped_stays:,} / {total_stays:,} = {stays_cov:.3f}%",
)
check(
    "Stays mapped count = 749,142 (per README)",
    mapped_stays == 749_142,
    f"got {mapped_stays:,}",
)

# ---------------------------------------------------------------------------
section("7. Splice integrity (no FOIA/stays overlap)")
# ---------------------------------------------------------------------------
det_mo = pd.read_csv(REPO / "data/processed/county_month_panel.csv")
st_mo = pd.read_csv(REPO / "data/processed/county_month_stays_panel.csv")
det_months = set(det_mo["year_month"])
st_months = set(st_mo["year_month"])
overlap = sorted(det_months & st_months)
check("no month overlap between FOIA and stays", not overlap, f"overlap={overlap}")
check("FOIA last month = 2023-11", max(det_months) == "2023-11", f"got {max(det_months)}")
check("Stays first month = 2023-12", min(st_months) == "2023-12", f"got {min(st_months)}")
check("Stays last month >= 2026-03", max(st_months) >= "2026-03", f"got {max(st_months)}")

# ---------------------------------------------------------------------------
section("8. Catalina's overrides applied")
# ---------------------------------------------------------------------------
sjs_rows = cw[cw["facility_code"].isin(["SJUHOLD", "AIRHOPR"])]
all_sj = (sjs_rows["county_fips"] == "72127").all() and len(sjs_rows) == 2
check(
    "both SJU airport facilities -> San Juan Municipio (72127)",
    all_sj,
    sjs_rows[["facility_code", "county_name", "county_fips"]].to_string(index=False),
)

# Carolina PR should now be empty
yr_det = pd.read_csv(REPO / "data/processed/county_year_panel.csv", dtype={"county_fips": str})
yr_det["county_fips"] = yr_det["county_fips"].str.zfill(5)
carolina = yr_det[yr_det["county_fips"] == "72031"]["n_episodes"].sum()
check("Carolina PR (72031) has 0 episodes", carolina == 0, f"got {carolina}")

# ---------------------------------------------------------------------------
section("9. DDP corrections reflected in panel totals")
# ---------------------------------------------------------------------------
expected = {
    "48061": ("Cameron TX (RGV Staging here)", 763_472),
    "48215": ("Hidalgo TX (RGV used to live here)", 77_645),
    "12086": ("Miami-Dade FL (Miami Staging here)", 186_151),
    "12011": ("Broward FL (Miami Staging used to live here)", 52_828),
    "51059": ("Fairfax VA (Washington FO here)", 43_014),
    "72127": ("San Juan PR (SJU airport here)", 5_397),
    "72061": ("Guaynabo PR (San Juan Staging here)", 8_815),
}
for f, (label, exp) in expected.items():
    got = int(yr_det[yr_det["county_fips"] == f]["n_episodes"].sum())
    check(
        f"  {f} {label}: expect {exp:,}",
        got == exp,
        f"got {got:,}",
    )

# ---------------------------------------------------------------------------
section("10. README is internally consistent with data")
# ---------------------------------------------------------------------------
readme = (REPO / "data/processed/README_PANELS.txt").read_text(encoding="utf-8")
for needle in [
    "San Juan",
    "Deportation Data Project",
    "99.96",
    "99.8",
    "December 2023",
    "n_stints_total",
    "county_fips",
    "for review",
    "Guantanamo",
]:
    check(f"README mentions: {needle!r}", needle in readme)

# ---------------------------------------------------------------------------
section("11. Dropbox <-> repo md5 match (all 16 files)")
# ---------------------------------------------------------------------------
def md5(p: Path) -> str:
    h = hashlib.md5()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()

DBOX_LAYOUT = {
    "README_PANELS.txt": "README_PANELS.txt",
    "county_year_panel.csv": "panels/county_year_panel.csv",
    "county_month_panel.csv": "panels/county_month_panel.csv",
    "county_year_encounters_panel.csv": "panels/county_year_encounters_panel.csv",
    "county_month_encounters_panel.csv": "panels/county_month_encounters_panel.csv",
    "county_year_stays_panel.csv": "panels/county_year_stays_panel.csv",
    "county_month_stays_panel.csv": "panels/county_month_stays_panel.csv",
    "facility_crosswalk.csv": "crosswalks/facility_crosswalk.csv",
    "facility_crosswalk_review.csv": "crosswalks/facility_crosswalk_review.csv",
    "site_crosswalk.csv": "crosswalks/site_crosswalk.csv",
    "site_crosswalk_review.csv": "crosswalks/site_crosswalk_review.csv",
    "unmapped_facilities.csv": "crosswalks/unmapped_facilities.csv",
    "unmapped_sites.csv": "crosswalks/unmapped_sites.csv",
    "unmapped_stays.csv": "crosswalks/unmapped_stays.csv",
    "facilities_need_county.csv": "for review/facilities_need_county.csv",
    "sites_need_county.csv": "for review/sites_need_county.csv",
}
for fn, repo_rel in DELIVERABLES.items():
    repo_p = REPO / repo_rel
    dbox_p = DBOX / DBOX_LAYOUT[fn]
    if not dbox_p.is_file():
        check(f"Dropbox: {fn}", False, "MISSING")
        continue
    same = md5(repo_p) == md5(dbox_p)
    check(f"Dropbox = repo md5: {fn}", same)

# Check obsolete files are gone
for orphan in [
    "for review/facility_overrides_template.csv",
    "for review/site_overrides_template.csv",
]:
    check(f"obsolete file removed: {orphan}", not (DBOX / orphan).exists())

# ---------------------------------------------------------------------------
section("12. Repo junk scan (loose stray files)")
# ---------------------------------------------------------------------------
junk_patterns = ["'", "{", "}", "%s", "str", "San"]
junk_found = []
for p in REPO.iterdir():
    if p.is_file() and p.name in junk_patterns:
        junk_found.append(p.name)
check("no junk files in repo root", not junk_found, f"found {junk_found}")

# ---------------------------------------------------------------------------
section("13. Git state")
# ---------------------------------------------------------------------------
r = subprocess.run(
    ["git", "-C", str(REPO), "status", "--porcelain"],
    capture_output=True, text=True,
)
unstaged_critical = [
    l for l in r.stdout.splitlines()
    if "ice_pipeline/" in l or "references/fips" in l or "docs/PANELS.md" in l
]
check(
    "no uncommitted changes to critical files",
    not unstaged_critical,
    f"{unstaged_critical}" if unstaged_critical else "",
)

r2 = subprocess.run(
    ["git", "-C", str(REPO), "log", "-1", "--format=%H %s"],
    capture_output=True, text=True,
)
check("git HEAD reachable", r2.returncode == 0, r2.stdout.strip())

r3 = subprocess.run(
    ["git", "-C", str(REPO), "rev-list", "origin/master..HEAD", "--count"],
    capture_output=True, text=True,
)
ahead = (r3.stdout.strip() or "0")
check("repo is pushed (0 commits ahead of origin)", ahead == "0", f"ahead by {ahead}")

# ---------------------------------------------------------------------------
section("14. Encounters integrity")
# ---------------------------------------------------------------------------
yr_enc = pd.read_csv(REPO / "data/processed/county_year_encounters_panel.csv", dtype={"county_fips": str})
yr_enc["year"] = yr_enc["year"].astype(int) if yr_enc["year"].dtype != "int64" else yr_enc["year"]
check(
    "Encounters panel covers 2023-2025",
    yr_enc["year"].min() <= 2023 and yr_enc["year"].max() >= 2025,
    f"years {yr_enc['year'].min()}..{yr_enc['year'].max()}",
)
mo_enc = pd.read_csv(REPO / "data/processed/county_month_encounters_panel.csv")
check(
    "Encounters month panel earliest month",
    "2023-09" <= mo_enc["year_month"].min() <= "2023-10",
    f"min = {mo_enc['year_month'].min()}",
)

# ---------------------------------------------------------------------------
print()
print("=" * 70)
fails = [r for r in results if r[0] == "FAIL"]
passes = [r for r in results if r[0] == "PASS"]
print(f"SUMMARY: {len(passes)} PASS, {len(fails)} FAIL  (of {len(results)} total)")
if fails:
    print()
    print("FAILURES:")
    for _, lbl, det in fails:
        print(f"  - {lbl}  {det}")
    sys.exit(1)
else:
    print("ALL CHECKS PASSED.")
    sys.exit(0)
