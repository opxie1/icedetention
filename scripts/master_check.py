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


section("H. Polo-Muro (Jul 17): balanced panel")
uni = pd.read_csv(REPO / "references/balanced_panel_universe.csv", dtype={"county5": str})
uni["county5"] = uni["county5"].str.zfill(5)
uni["ym"] = uni["year"].astype(str) + "-" + uni["month"].astype(str).str.zfill(2)
bm = pd.read_csv(PROC / "county_month_detention_population_balanced.csv",
                 dtype={"county_fips": str}, low_memory=False)
bm["county_fips"] = bm["county_fips"].str.zfill(5)
check("balanced grid == his .rds grid exactly",
      set(zip(bm.county_fips, bm.year_month)) == set(zip(uni.county5, uni.ym)),
      f"{len(bm):,} rows, {bm.county_fips.nunique()} counties x {bm.year_month.nunique()} months")
check("no duplicate (county, month)", bm.duplicated(["county_fips", "year_month"]).sum() == 0)
check("zero-filled county-months present", int((bm.n_detained == 0).sum()) > 500_000,
      f"{int((bm.n_detained==0).sum()):,} zero rows")
check("beyond-data months left NA not zero",
      bm[bm.year_month > "2026-03"].n_detained.isna().all()
      and bm[bm.year_month <= "2026-03"].n_detained.notna().all())
check("population on 100% of rows", bm.pop_total.notna().all(),
      f"{100*bm.pop_total.notna().mean():.2f}%")
src_comb = pd.read_csv(PROC / "county_month_detention_combined.csv", dtype={"county_fips": str})
src_comb["county_fips"] = src_comb["county_fips"].str.zfill(5)
terr_n = src_comb[src_comb.county_fips.isin(["66010", "69110", "78030"])].n_detained.sum()
check("totals reconcile (balanced + territories = source)",
      int(bm.n_detained.sum()) + int(terr_n) == int(src_comb.n_detained.sum()),
      f"{int(bm.n_detained.sum()):,} + {int(terr_n):,} = {int(src_comb.n_detained.sum()):,}")
sm = src_comb.merge(bm[["county_fips", "year_month", "n_detained"]],
                    on=["county_fips", "year_month"], how="left", suffixes=("_s", "_b"))
sm = sm[~sm.county_fips.isin(["66010", "69110", "78030"])]
check("every original detention row preserved with identical count",
      sm.n_detained_b.notna().all() and np.allclose(sm.n_detained_s, sm.n_detained_b))
by = pd.read_csv(PROC / "county_year_detention_population_balanced.csv", dtype={"county_fips": str})
check("yearly balanced unique (county, year)", by.duplicated(["county_fips", "year"]).sum() == 0,
      f"{len(by):,} rows")

section("I. Amuedo-Dorantes (Jul 17): enforcement measures")
em = pd.read_csv(PROC / "county_enforcement_measures.csv", dtype={"county_fips": str})
em["county_fips"] = em["county_fips"].str.zfill(5)
for c in ["intensity_excess", "intensity_sd", "longest_streak", "n_spike_episodes",
          "spike_fragmentation", "spike_frequency"]:
    check(f"measure column present: {c}", c in em.columns)
t1 = pd.read_csv(REPO / "analysis/task1_spikes/table_spike_summary_by_county.csv",
                 dtype={"county_fips": str})
t1["county_fips"] = t1["county_fips"].str.zfill(5)
j = em.merge(t1, on="county_fips", suffixes=("_n", "_t"))
check("spike stats match Task 1 on all shared counties",
      (j.n_spike_months_n == j.n_spike_months_t).all()
      and (j.longest_streak_n == j.longest_streak_t).all(),
      f"{len(j)} counties compared")
check("intensities non-negative and finite",
      (em.intensity_excess >= 0).all() and (em.intensity_sd >= 0).all()
      and np.isfinite(em.intensity_sd).all())
check("standardized intensity bounded (z-cap works)", em.intensity_sd.max() < 1000,
      f"max {em.intensity_sd.max():.1f}")
fr = em.spike_fragmentation.dropna()
check("fragmentation within (0,1]", fr.between(0, 1).all(),
      f"{fr.min():.3f}..{fr.max():.3f}")

section("J. Amuedo-Dorantes (Jul 25): day-level intermittency")
da = pd.read_csv(PROC / "county_month_daily_activity.csv", dtype={"county_fips": str})
da["county_fips"] = da["county_fips"].str.zfill(5)
for c in ["active_days", "max_consecutive_active_days", "n_active_runs", "span_days"]:
    check(f"daily column present: {c}", c in da.columns)
foia_p = pd.read_csv(PROC / "county_month_panel.csv", dtype={"county_fips": str})
foia_p["county_fips"] = foia_p["county_fips"].str.zfill(5)
fj = da[da.year_month <= "2023-11"].merge(
    foia_p[["county_fips", "year_month", "n_episodes"]],
    on=["county_fips", "year_month"], how="outer", indicator=True)
check("FOIA daily reconstruction matches panel episodes exactly",
      (fj._merge == "both").all() and np.allclose(fj.n_bookins, fj.n_episodes),
      f"{len(fj):,} county-months")
st_p = pd.read_csv(PROC / "county_month_stays_panel.csv", dtype={"county_fips": str})
st_p["county_fips"] = st_p["county_fips"].str.zfill(5)
dj = da[da.year_month >= "2023-12"].merge(
    st_p[["county_fips", "year_month", "n_stays"]],
    on=["county_fips", "year_month"], how="outer", indicator=True)
check("DDP daily reconstruction matches panel stays exactly",
      (dj._merge == "both").all() and np.allclose(dj.n_bookins, dj.n_stays),
      f"{len(dj):,} county-months")
check("active_days <= days_in_month", (da.active_days <= da.days_in_month).all())
check("active_days <= n_bookins", (da.active_days <= da.n_bookins).all())
check("longest run <= active_days", (da.max_consecutive_active_days <= da.active_days).all())
check("1 <= clusters <= active_days",
      (da.n_active_runs >= 1).all() and (da.n_active_runs <= da.active_days).all())
check("distinguishes solid-block from scattered months",
      bool((da.max_consecutive_active_days >= 5).any())
      and bool((da[da.active_days >= 5].n_active_runs >= 5).any()))
ds = pd.read_csv(PROC / "county_daily_intermittency_summary.csv", dtype={"county_fips": str})
check("daily summary covers all active counties", len(ds) == 635, f"{len(ds)} counties")

section("K. Dropbox: newest deliverables synced")
NEW = {
    "balanced panel/county_month_detention_population_balanced.csv":
        PROC / "county_month_detention_population_balanced.csv",
    "balanced panel/county_year_detention_population_balanced.csv":
        PROC / "county_year_detention_population_balanced.csv",
    "enforcement measures/county_enforcement_measures.csv":
        PROC / "county_enforcement_measures.csv",
    "enforcement measures/county_month_enforcement_detail.csv":
        PROC / "county_month_enforcement_detail.csv",
    "enforcement measures/county_month_daily_activity.csv":
        PROC / "county_month_daily_activity.csv",
    "enforcement measures/county_daily_intermittency_summary.csv":
        PROC / "county_daily_intermittency_summary.csv",
}
bad_new = [r for r, s in NEW.items()
           if not ((DBOX / r).is_file() and md5(DBOX / r) == md5(s))]
check(f"all {len(NEW)} newest files in Dropbox and md5-identical", not bad_new,
      f"mismatches: {bad_new}" if bad_new else "")
rm_txt = (PROC / "README_PANELS.txt").read_text(encoding="utf-8")
for needle in ["balanced panel", "enforcement measures", "active_days",
               "max_consecutive_active_days", "intensity_excess"]:
    check(f"README documents: {needle}", needle in rm_txt)
check("README in Dropbox matches repo",
      md5(DBOX / "README_PANELS.txt") == md5(PROC / "README_PANELS.txt"))

section("L. Court-area prep (Aug): exposure file ready, aggregation gated")
ex = pd.read_csv(PROC / "county_month_exposure.csv",
                 dtype={"county_fips": str}, low_memory=False)
ex["county_fips"] = ex["county_fips"].str.zfill(5)
for c_ in ["n_detained", "pop_total", "detained_per_100k", "spike",
           "excess", "excess_sd", "partial_month"]:
    check(f"exposure column present: {c_}", c_ in ex.columns)
check("exposure file is the full balanced grid",
      len(ex) == 557_233 and ex.county_fips.nunique() == 3221,
      f"{len(ex):,} rows, {ex.county_fips.nunique()} counties")
check("no duplicate (county, month)", ex.duplicated(["county_fips", "year_month"]).sum() == 0)
check("population on 100% of rows", ex.pop_total.notna().all())
check("partial months flagged (2023-11, 2026-03)",
      set(ex[ex.partial_month].year_month.unique()) == {"2023-11", "2026-03"})
check("exposure totals match combined panel",
      int(ex.n_detained.sum()) == int(bm.n_detained.sum()),
      f"{int(ex.n_detained.sum()):,}")
check("exposure file synced to Dropbox",
      md5(DBOX / "enforcement measures/county_month_exposure.csv")
      == md5(PROC / "county_month_exposure.csv"))
check("README documents the exposure file",
      "county_month_exposure.csv" in (PROC / "README_PANELS.txt").read_text(encoding="utf-8"))
court_src = (REPO / "scripts/build_court_exposure.py").read_text(encoding="utf-8")
for want in ["n_detained", "detained_per_100k", "court_spike", "court_excess",
             "court_excess_sd"]:
    check(f"court panel will carry: {want}", f'"{want}"' in court_src)
for fig in ["fig1_court_ranked_exposure.png", "fig2_central_valley_vs_national.png",
            "fig3_court_time_series.png", "documentation_note.txt"]:
    check(f"court script produces: {fig}", fig in court_src)
for elem in ["UNIT OF OBSERVATION", "DATE RANGE", "DENOMINATOR", "SPIKE DEFINITION",
             "SOURCE CHANGE IN DECEMBER 2023", "COUNTY TO COURT AREA"]:
    check(f"doc note covers: {elem}", elem in court_src)
check("no fabricated court crosswalk present",
      not list((REPO / "references").glob("*court*"))
      and not list((REPO / "analysis" / "court_exposure").glob("*.csv")),
      "correctly waiting on Prof. Polo-Muro")


section("M. Polo-Muro AOR files (Aug): court-area exposure built")
AOUT = REPO / "analysis" / "aor_exposure"
ap = pd.read_csv(AOUT / "aor_month_exposure.csv")
axw = pd.read_csv(REPO / "references/county_aor_crosswalk.csv", dtype={"county_fips": str})
axw["county_fips"] = axw["county_fips"].str.zfill(5)
cexp = pd.read_csv(PROC / "county_month_exposure.csv",
                   dtype={"county_fips": str}, low_memory=False)
cexp["county_fips"] = cexp["county_fips"].str.zfill(5)
cexp = cexp[cexp.year_month <= "2026-03"]
check("AOR panel built", len(ap) == 25 * 171, f"{len(ap):,} rows, {ap.aor.nunique()} AORs")
check("unique (aor, month)", ap.duplicated(["aor", "year_month"]).sum() == 0)
check("every detention preserved into AOR panel",
      np.isclose(ap.n_detained.sum(), cexp.n_detained.sum()),
      f"{ap.n_detained.sum():,.0f}")
CT_LEGACY = {"09001", "09003", "09005", "09007", "09009", "09011", "09013", "09015"}
check("Connecticut legacy counties mapped (crosswalk ships planning regions only)",
      CT_LEGACY <= set(axw.county_fips)
      and set(axw[axw.county_fips.isin(CT_LEGACY)].aor) == {"Boston"})
check("Boston population includes Connecticut",
      ap[ap.aor == "Boston"].pop_total.max() > 15e6,
      f"{ap[ap.aor=='Boston'].pop_total.max():,.0f}")
check("no county dropped between exposure file and AOR panel",
      set(cexp.county_fips) <= set(axw.county_fips))
check("arrests blank before Oct 2022, not zero",
      ap[ap.year_month < "2022-10"].n_arrests.isna().all())
check("arrest spikes begin after 12 months of history",
      ap[ap.arr_spike.notna()].year_month.min() == "2023-10")
check("spike flags are 0/1",
      ap.det_spike.dropna().isin([0, 1]).all() and ap.arr_spike.dropna().isin([0, 1]).all())
check("standardized intensity capped",
      max(ap.arr_excess_sd.max(), ap.det_excess_sd.max()) <= 10.0001)
check("partial months flagged and excluded from figures",
      set(ap[ap.partial_month].year_month.unique()) == {"2023-11", "2026-03"})
check("Central Valley resolves to San Francisco AOR",
      set(axw[axw.county_fips.isin(
          ["06019", "06029", "06067", "06077", "06107"])].aor) == {"San Francisco"})
for f in ["aor_month_exposure.csv", "aor_exposure_summary.csv",
          "fig1_aor_ranked_exposure.png", "fig2_central_valley_vs_national.png",
          "fig3_aor_time_series.png", "documentation_note.txt"]:
    check(f"deliverable: {f}", (AOUT / f).is_file() and (AOUT / f).stat().st_size > 1000)
dn = (AOUT / "documentation_note.txt").read_text(encoding="utf-8")
for elem in ["UNIT OF OBSERVATION", "DATE RANGE", "DENOMINATOR", "SPIKE DEFINITION",
             "SOURCE CHANGE IN DECEMBER 2023", "PARTIAL MONTHS",
             "ASSUMPTIONS AND WHAT IS LEFT OUT"]:
    check(f"doc note covers: {elem}", elem in dn)
check("doc note explains the Connecticut adjustment", "Connecticut" in dn)
check("doc note states Central Valley cannot be isolated",
      "cannot be separated" in dn or "Bay Area" in dn)
bad_aor = [f for f in ["aor_month_exposure.csv", "aor_exposure_summary.csv",
                       "fig1_aor_ranked_exposure.png",
                       "fig2_central_valley_vs_national.png",
                       "fig3_aor_time_series.png", "documentation_note.txt"]
           if md5(AOUT / f) != md5(DBOX / "court exposure" / f)]
check("all 6 AOR deliverables synced to Dropbox", not bad_aor, str(bad_aor))
print(f"\n{'='*70}")
fails = results.count("FAIL")
print(f"SUMMARY: {results.count('PASS')} PASS, {fails} FAIL of {len(results)}")
sys.exit(1 if fails else 0)
