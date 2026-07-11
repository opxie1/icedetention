"""Master verification: every request Catalina and Eduardo have made, checked."""
from __future__ import annotations

import hashlib
import io
import subprocess
import sys
import tokenize
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(r"C:\Users\xief\.local\bin\ucmerced")
PROC = REPO / "data" / "processed"
DBOX = Path(r"C:\Users\xief\Dropbox\ethan xie\ice crosswalk")
SPIKE = REPO / "analysis" / "task1_spikes"

results = []


def check(label, ok, detail=""):
    flag = "PASS" if ok else "FAIL"
    print(f"[{flag}] {label}" + (f"  ({detail})" if detail else ""))
    results.append(flag)


def section(name):
    print(f"\n{'='*70}\n {name}\n{'='*70}")


def md5(p: Path) -> str:
    h = hashlib.md5()
    with p.open("rb") as f:
        for c in iter(lambda: f.read(65536), b""):
            h.update(c)
    return h.hexdigest()


section("A. Eduardo (Apr): crosswalk, unusual flags, county panels")
cw = pd.read_csv(PROC / "facility_crosswalk.csv", dtype=str).fillna("")
check("facility crosswalk exists with county assignment", len(cw) == 1141, f"{len(cw)} facilities")
check("unusual flags present", (cw["unusual_flag"] == "True").sum() > 300,
      f"{(cw['unusual_flag']=='True').sum()} flagged")
mapped_eps = cw[cw["county_fips"] != ""]["n_episodes"].astype(int).sum()
check("episode coverage 99.96%", mapped_eps == 8_455_175, f"{mapped_eps:,}")
for f in ["county_year_panel.csv", "county_month_panel.csv",
          "county_year_encounters_panel.csv", "county_month_encounters_panel.csv"]:
    check(f"panel: {f}", (PROC / f).stat().st_size > 10_000)

section("B. Catalina (May 25): San Juan, DDP list, stays data")
sju = cw[cw["facility_code"].isin(["SJUHOLD", "AIRHOPR"])]
check("both SJU airport facilities -> San Juan 72127",
      len(sju) == 2 and (sju["county_fips"] == "72127").all())
check("DDP facility list wired in as source",
      (cw["resolution_source"] == "ddp").sum() > 400,
      f"{(cw['resolution_source']=='ddp').sum()} facilities resolved via DDP")
sy = pd.read_csv(PROC / "county_month_stays_panel.csv")
det = pd.read_csv(PROC / "county_month_panel.csv")
overlap = set(sy.year_month) & set(det.year_month)
check("stays panel extends to present", sy.year_month.max() >= "2026-03", sy.year_month.max())
check("no FOIA/stays month overlap", not overlap)
stays_total = pd.read_csv(PROC / "county_year_stays_panel.csv").n_stays.sum()
check("stays coverage 99.8% (749,142 mapped)", stays_total == 749_142, f"{stays_total:,}")

section("C. Catalina (Jun): single combined 2012-2026 files")
cyc = pd.read_csv(PROC / "county_year_detention_combined.csv", dtype={"county_fips": str})
cmc = pd.read_csv(PROC / "county_month_detention_combined.csv", dtype={"county_fips": str})
months = sorted(cmc.year_month.unique())
allm = pd.period_range("2012-01", "2026-03", freq="M").astype(str)
check("month file spans 2012-01..2026-03 with no gaps",
      months[0] == "2012-01" and months[-1] == "2026-03" and len(months) == len(allm))
check("month file unique (county, year_month) key",
      cmc.duplicated(["county_fips", "year_month"]).sum() == 0)
check("year file unique (county, year) key",
      cyc.duplicated(["county_fips", "year"]).sum() == 0)
check("totals preserved (episodes+stints)",
      int(cmc.n_episodes.dropna().sum()) == 8_455_175
      and int(cmc.n_stints_total.dropna().sum()) == 1_924_485)
check("n_detained never null", cmc.n_detained.notna().all())

section("D. Eduardo (Jul): population, Hispanic, non-citizen, shares")
pop = pd.read_csv(PROC / "county_year_population.csv", dtype={"county_fips": str})
pop["county_fips"] = pop["county_fips"].str.zfill(5)
check("population panel exists 2012-2026",
      pop.year.min() == 2012 and pop.year.max() == 2026, f"{len(pop):,} rows")
for col in ["pop_total", "pop_hispanic", "pop_noncitizen",
            "pct_hispanic", "pct_noncitizen",
            "pop_total_refyear", "pop_hispanic_refyear", "pop_noncitizen_refyear"]:
    check(f"column present: {col}", col in pop.columns)
la = pop[(pop.county_fips == "06037") & (pop.year == 2022)].iloc[0]
sj = pop[(pop.county_fips == "72127") & (pop.year == 2022)].iloc[0]
check("LA 2022 noncitizen == live API (1,517,330)", la.pop_noncitizen == 1_517_330)
check("San Juan PR 2022 noncitizen == live API (20,036)", sj.pop_noncitizen == 20_036)
one = pop[(pop.geo_basis != "CT-legacy-county") & (~pop.county_fips.str.startswith("72"))]
us20 = one[one.year == 2020].pop_total.sum()
check("US 2020 total matches Census (331.5M)", 330e6 < us20 < 333e6, f"{us20/1e6:.1f}M")
for c in ["pct_hispanic", "pct_noncitizen"]:
    check(f"{c} in [0,1]", pop[c].dropna().between(0, 1).all())
mrg = pd.read_csv(PROC / "county_year_detention_population.csv", dtype={"county_fips": str})
check("merged file has detained_per_100k", "detained_per_100k" in mrg.columns)
match_rate = mrg.pop_total.notna().mean()
check("population matched to >=99% of detention rows", match_rate >= 0.99, f"{100*match_rate:.2f}%")
unmatched_states = set(mrg[mrg.pop_total.isna()].county_fips.str[:2])
check("only island territories unmatched", unmatched_states <= {"66", "69", "78"},
      str(sorted(unmatched_states)))

section("E. Catalina Task 1: spike deliverables")
for f in ["fig1_national_spike_map.png", "fig1b_central_valley_spike_map.png",
          "fig2_time_series.png", "table_spike_summary_by_county.csv",
          "detention_county_month.csv", "task1_spike_maps_adapted.R"]:
    p = SPIKE / f
    check(f"deliverable: {f}", p.is_file() and p.stat().st_size > 1000,
          f"{p.stat().st_size:,} B" if p.exists() else "MISSING")
inp = pd.read_csv(SPIKE / "detention_county_month.csv", dtype={"county_fips": str})
check("spike input grid complete (635 x 171)",
      len(inp) == 635 * 171 and inp.groupby("county_fips").size().nunique() == 1)
check("spike input totals preserved",
      int(inp.detention_count.sum()) == int(cmc.n_detained.sum()),
      f"{int(inp.detention_count.sum()):,}")
r_sum = pd.read_csv(SPIKE / "table_spike_summary_by_county.csv", dtype={"county_fips": str})
py_sum = pd.read_csv(SPIKE / "python_crosscheck_summary.csv", dtype={"county_fips": str})
for d in (r_sum, py_sum):
    d["county_fips"] = d["county_fips"].str.zfill(5)
m = py_sum.merge(r_sum, on="county_fips", suffixes=("_py", "_r"))
check("R vs Python spike stats identical (635 counties)",
      len(m) == 635
      and (m.n_spike_months_py == m.n_spike_months_r).all()
      and (m.longest_streak_py == m.longest_streak_r).all()
      and np.isclose(m.spike_frequency_py, m.spike_frequency_r, atol=1e-9).all())
el_total = r_sum.n_months_eligible.sum()
sp_total = r_sum.n_spike_months.sum()
check("spike rate plausible (~7% of eligible)",
      0.05 < sp_total / el_total < 0.10, f"{100*sp_total/el_total:.2f}%")

section("F. Dropbox tree matches repo (all folders)")
TREE = {
    "README_PANELS.txt": PROC / "README_PANELS.txt",
    "panels/county_year_panel.csv": PROC / "county_year_panel.csv",
    "panels/county_month_panel.csv": PROC / "county_month_panel.csv",
    "panels/county_year_encounters_panel.csv": PROC / "county_year_encounters_panel.csv",
    "panels/county_month_encounters_panel.csv": PROC / "county_month_encounters_panel.csv",
    "panels/county_year_stays_panel.csv": PROC / "county_year_stays_panel.csv",
    "panels/county_month_stays_panel.csv": PROC / "county_month_stays_panel.csv",
    "panels/county_year_detention_combined.csv": PROC / "county_year_detention_combined.csv",
    "panels/county_month_detention_combined.csv": PROC / "county_month_detention_combined.csv",
    "crosswalks/facility_crosswalk.csv": PROC / "facility_crosswalk.csv",
    "crosswalks/facility_crosswalk_review.csv": PROC / "facility_crosswalk_review.csv",
    "crosswalks/site_crosswalk.csv": PROC / "site_crosswalk.csv",
    "crosswalks/site_crosswalk_review.csv": PROC / "site_crosswalk_review.csv",
    "crosswalks/unmapped_facilities.csv": PROC / "unmapped_facilities.csv",
    "crosswalks/unmapped_sites.csv": PROC / "unmapped_sites.csv",
    "crosswalks/unmapped_stays.csv": PROC / "unmapped_stays.csv",
    "for review/facilities_need_county.csv": REPO / "references/facilities_need_county.csv",
    "for review/sites_need_county.csv": REPO / "references/sites_need_county.csv",
    "population/county_year_population.csv": PROC / "county_year_population.csv",
    "population/county_year_detention_population.csv": PROC / "county_year_detention_population.csv",
    "population/county_month_detention_population.csv": PROC / "county_month_detention_population.csv",
    "task 1 spike maps/fig1_national_spike_map.png": SPIKE / "fig1_national_spike_map.png",
    "task 1 spike maps/fig1b_central_valley_spike_map.png": SPIKE / "fig1b_central_valley_spike_map.png",
    "task 1 spike maps/fig2_time_series.png": SPIKE / "fig2_time_series.png",
    "task 1 spike maps/table_spike_summary_by_county.csv": SPIKE / "table_spike_summary_by_county.csv",
    "task 1 spike maps/task1_spike_maps_adapted.R": SPIKE / "task1_spike_maps_adapted.R",
    "task 1 spike maps/detention_county_month.csv": SPIKE / "detention_county_month.csv",
}
bad = []
for rel, src in TREE.items():
    d = DBOX / rel
    if not (d.is_file() and src.is_file() and md5(d) == md5(src)):
        bad.append(rel)
check(f"all {len(TREE)} Dropbox files present and md5-identical to repo",
      not bad, f"mismatches: {bad}" if bad else "")

section("G. Hygiene: comments gone, code compiles, git clean")
n_comments = 0
for p in sorted((REPO / "ice_pipeline").glob("*.py")) + sorted((REPO / "scripts").glob("*.py")):
    if p.name == "strip_comments.py":
        continue
    src = p.read_text(encoding="utf-8")
    try:
        toks = tokenize.generate_tokens(io.StringIO(src).readline)
        n_comments += sum(1 for t in toks if t.type == tokenize.COMMENT)
    except tokenize.TokenizeError:
        pass
check("zero # comments in ice_pipeline + scripts", n_comments == 0, f"{n_comments} remaining")
r = subprocess.run([sys.executable, "-m", "compileall", "-q",
                    str(REPO / "ice_pipeline"), str(REPO / "scripts")],
                   capture_output=True, text=True)
check("all python compiles", r.returncode == 0)
g = subprocess.run(["git", "-C", str(REPO), "status", "--porcelain"],
                   capture_output=True, text=True)
dirty = [l for l in g.stdout.splitlines()
         if not l.startswith("??") or "ice_pipeline/" in l or "scripts/" in l]
check("no unexpected modified tracked files pre-commit",
      all(l.split()[-1].startswith(("ice_pipeline/", "scripts/", ".gitignore")) or l.startswith("??")
          for l in g.stdout.splitlines()),
      f"{len(g.stdout.splitlines())} entries in git status")

print(f"\n{'='*70}")
fails = results.count("FAIL")
print(f"SUMMARY: {results.count('PASS')} PASS, {fails} FAIL of {len(results)}")
sys.exit(1 if fails else 0)
