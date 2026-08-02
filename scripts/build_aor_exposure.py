from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(r"C:\Users\xief\.local\bin\ucmerced")
PROC = REPO / "data" / "processed"
REFS = REPO / "references"
OUT = REPO / "analysis" / "aor_exposure"
OUT.mkdir(parents=True, exist_ok=True)

ARRESTS = Path(r"C:\Users\xief\Downloads\arrests-latest.parquet")
AOR_XW = Path(r"C:\Users\xief\Downloads\ice-aor-county-shp.parquet")

K = 1.5
Z_CAP = 10.0
COVER_MAX = "2026-03"
PARTIAL_MONTHS = {"2023-11", "2026-03"}
TODAY = pd.Timestamp("2026-08-02")

CV_FIPS = ["06007", "06011", "06019", "06021", "06029", "06031", "06039",
           "06047", "06061", "06067", "06077", "06089", "06099", "06101",
           "06103", "06107", "06113", "06115"]


def norm_aor(s: pd.Series) -> pd.Series:
    return (s.astype(str)
            .str.replace(" Area of Responsibility", "", regex=False)
            .str.replace(".", "", regex=False)
            .str.strip())


def spike_recompute(df, key, value, prefix):
    df = df.sort_values([key, "year_month"]).copy()
    g = df.groupby(key)[value]
    rm = g.transform(lambda s: s.rolling(12).mean().shift(1))
    rs = g.transform(lambda s: s.rolling(12).std(ddof=1).shift(1))
    elig = rm.notna() & rs.notna() & df[value].notna()
    df[f"{prefix}_spike"] = np.where(elig, (df[value] > rm + K * rs).astype(float), np.nan)
    df[f"{prefix}_excess"] = np.where(df[f"{prefix}_spike"] == 1, df[value] - rm, 0.0)
    z = (df[value] - rm) / rs.where(rs > 0)
    df[f"{prefix}_excess_sd"] = np.where(
        (df[f"{prefix}_spike"] == 1) & (rs > 0), np.minimum(z, Z_CAP), 0.0)
    return df


print("=== crosswalk ===")
xw = pd.read_parquet(AOR_XW, columns=["GEOID", "NAME", "STUSPS",
                                      "area_of_responsibility_name"])
xw = xw.dropna(subset=["GEOID"]).copy()
xw["county_fips"] = xw["GEOID"].astype(str).str.zfill(5)
xw["aor"] = norm_aor(xw["area_of_responsibility_name"])
xw = xw[["county_fips", "aor"]].drop_duplicates()
xw.to_csv(REFS / "county_aor_crosswalk.csv", index=False)
print(f"  {xw.county_fips.nunique():,} counties -> {xw.aor.nunique()} AORs")

print("=== detentions by AOR-month ===")
exp = pd.read_csv(PROC / "county_month_exposure.csv",
                  dtype={"county_fips": str}, low_memory=False)
exp["county_fips"] = exp["county_fips"].str.zfill(5)
exp = exp[exp["year_month"] <= COVER_MAX]
m = exp.merge(xw, on="county_fips", how="inner")
lost = exp[~exp.county_fips.isin(set(xw.county_fips))].n_detained.sum()
print(f"  matched {m.county_fips.nunique():,} counties; "
      f"unmatched detentions {int(lost):,}")

det = (m.groupby(["aor", "year_month"])
       .agg(n_counties=("county_fips", "nunique"),
            n_detained=("n_detained", "sum"),
            pop_total=("pop_total", "sum"),
            county_spike_share=("spike", "mean"))
       .reset_index())

print("=== arrests by AOR-month ===")
ar = pd.read_parquet(ARRESTS, columns=["apprehension_date", "apprehension_aor",
                                       "duplicate_drop_row"])
n0 = len(ar)
ar = ar[~ar["duplicate_drop_row"].fillna(False)]
ar["dt"] = pd.to_datetime(ar["apprehension_date"], errors="coerce")
ar = ar[ar["dt"].notna() & (ar["dt"] <= TODAY)]
ar["aor"] = norm_aor(ar["apprehension_aor"])
ar = ar[ar["aor"].notna() & (ar["aor"] != "nan")]
ar["year_month"] = ar["dt"].dt.strftime("%Y-%m")
ar = ar[ar["year_month"] <= COVER_MAX]
print(f"  {n0:,} rows -> {len(ar):,} after dropping flagged duplicates, "
      f"missing/future dates, missing AOR")
print(f"  arrest months: {ar.year_month.min()} .. {ar.year_month.max()}")
arr = ar.groupby(["aor", "year_month"]).size().rename("n_arrests").reset_index()

print("=== combine ===")
months = sorted(exp.year_month.unique())
grid = pd.MultiIndex.from_product([sorted(xw.aor.unique()), months],
                                  names=["aor", "year_month"]).to_frame(index=False)
panel = (grid.merge(det, on=["aor", "year_month"], how="left")
             .merge(arr, on=["aor", "year_month"], how="left"))

arr_start = arr.year_month.min()
panel.loc[panel.year_month >= arr_start, "n_arrests"] = (
    panel.loc[panel.year_month >= arr_start, "n_arrests"].fillna(0))

panel["year"] = panel["year_month"].str[:4].astype(int)
panel["period"] = np.where(panel["year_month"] < "2023-12", "FOIA", "DDP")
panel["partial_month"] = panel["year_month"].isin(PARTIAL_MONTHS)
panel["detained_per_100k"] = (
    100_000 * panel["n_detained"] / panel["pop_total"].where(panel["pop_total"] > 0))
panel["arrests_per_100k"] = (
    100_000 * panel["n_arrests"] / panel["pop_total"].where(panel["pop_total"] > 0))

panel = spike_recompute(panel, "aor", "n_detained", "det")
panel = spike_recompute(panel, "aor", "n_arrests", "arr")

cols = ["aor", "year_month", "year", "period", "partial_month", "n_counties",
        "pop_total", "n_detained", "detained_per_100k",
        "det_spike", "det_excess", "det_excess_sd", "county_spike_share",
        "n_arrests", "arrests_per_100k",
        "arr_spike", "arr_excess", "arr_excess_sd"]
panel = panel[cols].sort_values(["aor", "year_month"])
panel.to_csv(OUT / "aor_month_exposure.csv", index=False)
print(f"  wrote aor_month_exposure.csv: {len(panel):,} rows "
      f"({panel.aor.nunique()} AORs x {panel.year_month.nunique()} months)")

live = panel[~panel.partial_month]
summ = (live.groupby("aor")
        .agg(n_counties=("n_counties", "max"),
             mean_pop=("pop_total", "mean"),
             total_detained=("n_detained", "sum"),
             det_spike_months=("det_spike", "sum"),
             det_total_excess=("det_excess", "sum"),
             det_total_excess_sd=("det_excess_sd", "sum"),
             total_arrests=("n_arrests", "sum"),
             arr_spike_months=("arr_spike", "sum"),
             arr_total_excess=("arr_excess", "sum"),
             arr_total_excess_sd=("arr_excess_sd", "sum"))
        .reset_index())
det_mo = live.groupby("aor")["n_detained"].apply(lambda s: s.notna().sum())
arr_mo = live.groupby("aor")["n_arrests"].apply(lambda s: s.notna().sum())
summ = summ.merge(det_mo.rename("det_months").reset_index(), on="aor")
summ = summ.merge(arr_mo.rename("arr_months").reset_index(), on="aor")
summ["mean_detained_per_100k"] = (
    100_000 * summ.total_detained / (summ.mean_pop * summ.det_months).where(summ.mean_pop > 0))
summ["mean_arrests_per_100k"] = (
    100_000 * summ.total_arrests / (summ.mean_pop * summ.arr_months).where(
        (summ.mean_pop > 0) & (summ.arr_months > 0)))
summ = summ.sort_values("arr_total_excess", ascending=False)
summ.to_csv(OUT / "aor_exposure_summary.csv", index=False)

cv_aor = sorted(xw[xw.county_fips.isin(CV_FIPS)].aor.unique())
cv_n = xw[xw.aor.isin(cv_aor)].county_fips.nunique()
print(f"  Central Valley -> {cv_aor} AOR ({cv_n} counties total)")
print(f"  wrote aor_exposure_summary.csv: {len(summ)} AORs")

no_aor = ar_unmatched = None
print("\n=== figures ===")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

CV_LABEL = "San Francisco"
cv_note = (f"San Francisco AOR ({cv_n} counties) contains every Central Valley\n"
           f"county, but also the Bay Area and the rest of northern California")

top = summ.nlargest(20, "arr_total_excess")
fig, ax = plt.subplots(figsize=(10, 7))
colors = ["#c1440e" if a == CV_LABEL else "#4c72b0" for a in top.aor]
ax.barh(top.aor[::-1], top.arr_total_excess[::-1], color=colors[::-1])
ax.set_xlabel("Total arrests above normal during spike months")
ax.set_title("Enforcement exposure by ICE area of responsibility\n"
             "Ranked by cumulative arrest spike intensity, Oct 2022 to Mar 2026")
fig.tight_layout()
fig.savefig(OUT / "fig1_aor_ranked_exposure.png", dpi=200)
plt.close(fig)

fig, ax = plt.subplots(figsize=(9, 5))
vals = summ.mean_arrests_per_100k.replace([np.inf, -np.inf], np.nan).dropna()
ax.hist(vals, bins=20, color="#4c72b0", alpha=.75)
sfv = summ.loc[summ.aor == CV_LABEL, "mean_arrests_per_100k"]
if len(sfv) and pd.notna(sfv.iloc[0]):
    ax.axvline(sfv.iloc[0], color="#c1440e", lw=2)
    ax.text(sfv.iloc[0], ax.get_ylim()[1] * .85,
            f"  San Francisco AOR\n  ({sfv.iloc[0]:.1f})", color="#c1440e", fontsize=9)
ax.set_xlabel("Arrests per 100,000 residents per month")
ax.set_ylabel("Number of areas of responsibility")
ax.set_title("The Central Valley's area against the national distribution")
ax.text(.98, .55, cv_note, transform=ax.transAxes, ha="right", fontsize=8, color="#555")
fig.tight_layout()
fig.savefig(OUT / "fig2_central_valley_vs_national.png", dpi=200)
plt.close(fig)

pl = panel[~panel.partial_month & panel.n_arrests.notna()]
nat = pl.groupby("year_month")["arrests_per_100k"].mean()
sf = pl[pl.aor == CV_LABEL].set_index("year_month")["arrests_per_100k"]
fig, ax = plt.subplots(figsize=(11, 5))
ax.plot(pd.to_datetime(nat.index + "-01"), nat.values, color="#4c72b0", lw=1.6,
        label="National average across areas")
ax.plot(pd.to_datetime(sf.index + "-01"), sf.values, color="#c1440e", lw=1.6,
        label="San Francisco area (contains Central Valley)")
ax.set_ylabel("Arrests per 100,000 residents")
ax.set_title("Enforcement exposure over time")
ax.legend(fontsize=9)
fig.tight_layout()
fig.savefig(OUT / "fig3_aor_time_series.png", dpi=200)
plt.close(fig)
print("  wrote 3 figures")

doc = f"""ENFORCEMENT EXPOSURE AROUND IMMIGRATION COURTS

Prepared by Ethan Xie (xief@udel.edu), August 2026.

UNIT OF OBSERVATION
One row per ICE area of responsibility per month, in
aor_month_exposure.csv. There are {panel.aor.nunique()} areas and
{panel.year_month.nunique()} months. A companion file,
aor_exposure_summary.csv, has one row per area for the whole period.

A NOTE ON THE GEOGRAPHY
Prof. Polo-Muro's crosswalk maps counties to ICE areas of
responsibility, so that is the unit here, not individual immigration
courts. This matters for the Central Valley. All of its counties sit in
the San Francisco area, but so do the Bay Area and the rest of northern
California, {cv_n} counties and about {int(panel[panel.aor==CV_LABEL].pop_total.max()):,}
residents in total. The Central Valley cannot be separated out at this
level, so the figures label that line as the San Francisco area rather
than the Central Valley.

DATE RANGE
Detentions run {panel[panel.n_detained.notna()].year_month.min()} to {panel[panel.n_detained.notna()].year_month.max()}.
Arrests run {panel[panel.n_arrests.notna()].year_month.min()} to {panel[panel.n_arrests.notna()].year_month.max()}, since the arrest file
does not go back further. Months before the arrest data starts are left
blank rather than zero.

TWO MEASURES, AND WHY BOTH
n_arrests counts where people were arrested, which is enforcement
itself. n_detained counts where people were held, which reflects where
facilities are. The arrest measure is the better one for this question,
and it is what the figures use. The detention measure is kept alongside
because it reaches back to 2012 while arrests only start in late 2022.

DENOMINATOR
Population is the county total from the Census, summed over the counties
in each area. Rates per 100,000 are computed from those sums rather than
averaged from county rates, so large counties carry their proper weight.

SPIKE DEFINITION
A month is a spike when the count runs more than {K} standard deviations
above that same area's own average over the prior twelve months. The
first twelve months of any series have no spike value. Excess is how far
above normal the spike months ran, and the _sd version is the same in
standard deviations, capped so a nearly flat area cannot produce a
runaway number. Both measures get their own spike columns, marked det_
for detentions and arr_ for arrests.

SOURCE CHANGE IN DECEMBER 2023
The detention data changes source then. Through November 2023 it counts
book-ins from the FOIA workbooks; from December 2023 it counts facility
bookings from the Deportation Data Project. The period column marks
which side each row falls on. The arrest data comes from one source
throughout and is not affected.

PARTIAL MONTHS
November 2023 and March 2026 are incomplete, flagged in the
partial_month column and left out of the figures. Both detentions and
arrests stop partway through March 2026.

ASSUMPTIONS AND WHAT IS LEFT OUT
Counties missing from the crosswalk hold {int(lost):,} detentions.
About one percent of arrests carry no area of responsibility, and a
further 80 are recorded under headquarters, which has no counties
attached; both are left out. One arrest dated September 2026 is a
future date and was dropped.

FILES
aor_month_exposure.csv            area by month
aor_exposure_summary.csv          one row per area
fig1_aor_ranked_exposure.png      areas ranked by arrest spike intensity
fig2_central_valley_vs_national.png  San Francisco area vs the national spread
fig3_aor_time_series.png          exposure over time
"""
(OUT / "documentation_note.txt").write_text(doc, encoding="utf-8")
print("  wrote documentation_note.txt")
