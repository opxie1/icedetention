from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(r"C:\Users\xief\.local\bin\ucmerced")
PROC = REPO / "data" / "processed"
REFS = REPO / "references"
OUT = REPO / "analysis" / "court_exposure"
OUT.mkdir(parents=True, exist_ok=True)

K = 1.5
Z_CAP = 10.0
COVER_MAX = "2026-03"
SPLICE = "2023-12"
PARTIAL_MONTHS = {"2023-11", "2026-03"}

CV_FIPS = ["06007", "06011", "06019", "06021", "06029", "06031", "06039",
           "06047", "06061", "06067", "06077", "06089", "06099", "06101",
           "06103", "06107", "06113", "06115"]


def find_crosswalk() -> Path | None:
    for pat in ["*court*crosswalk*.csv", "*county*court*.csv", "*court*.csv",
                "*eoir*.csv"]:
        hits = sorted(REFS.glob(pat))
        if hits:
            return hits[0]
    return None


def load_crosswalk(path: Path) -> pd.DataFrame:
    cw = pd.read_csv(path, dtype=str)
    cols = {c.lower().strip(): c for c in cw.columns}
    fips_col = next((cols[c] for c in cols
                     if "fips" in c or c in ("county5", "county_id", "countyfips")), None)
    court_col = next((cols[c] for c in cols
                      if "court" in c or "eoir" in c or "base_city" in c), None)
    if fips_col is None or court_col is None:
        raise SystemExit(
            f"Could not identify columns in {path.name}.\n"
            f"  found columns: {list(cw.columns)}\n"
            f"  need one county FIPS column and one court-area column.")
    out = cw[[fips_col, court_col]].copy()
    out.columns = ["county_fips", "court_area"]
    out["county_fips"] = out["county_fips"].str.strip().str.zfill(5)
    out["court_area"] = out["court_area"].str.strip()
    out = out.dropna().drop_duplicates()
    dup = out[out.duplicated("county_fips", keep=False)]
    if len(dup):
        print(f"  NOTE: {dup.county_fips.nunique()} counties map to more than one "
              f"court area; keeping all rows (detentions will be split evenly).")
    return out


def spike_recompute(df: pd.DataFrame, key: str, value: str) -> pd.DataFrame:
    df = df.sort_values([key, "year_month"]).copy()
    g = df.groupby(key)[value]
    df["roll_mean"] = g.transform(lambda s: s.rolling(12).mean().shift(1))
    df["roll_sd"] = g.transform(lambda s: s.rolling(12).std(ddof=1).shift(1))
    elig = df["roll_mean"].notna() & df["roll_sd"].notna()
    df["eligible"] = elig
    df["spike"] = np.where(elig, (df[value] > df["roll_mean"] + K * df["roll_sd"]).astype(float),
                           np.nan)
    df["excess"] = np.where(df["spike"] == 1, df[value] - df["roll_mean"], 0.0)
    raw_z = (df[value] - df["roll_mean"]) / df["roll_sd"].where(df["roll_sd"] > 0)
    df["excess_sd"] = np.where((df["spike"] == 1) & (df["roll_sd"] > 0),
                               np.minimum(raw_z, Z_CAP), 0.0)
    return df


def main() -> None:
    global OUT
    xw_path = Path(sys.argv[1]) if len(sys.argv) > 1 else find_crosswalk()
    if len(sys.argv) > 2:
        OUT = Path(sys.argv[2])
        OUT.mkdir(parents=True, exist_ok=True)
    if xw_path is None:
        print("No county-to-court-area crosswalk found in references/.")
        print("Expected a CSV with a county FIPS column and a court-area column,")
        print("e.g. references/county_court_crosswalk.csv")
        print("\nEverything upstream is ready: data/processed/county_month_exposure.csv")
        print("Drop the crosswalk in references/ and rerun this script.")
        sys.exit(0)

    print(f"Using crosswalk: {xw_path.name}")
    xw = load_crosswalk(xw_path)
    print(f"  {xw.county_fips.nunique():,} counties -> {xw.court_area.nunique()} court areas")

    exp = pd.read_csv(PROC / "county_month_exposure.csv",
                      dtype={"county_fips": str}, low_memory=False)
    exp["county_fips"] = exp["county_fips"].str.zfill(5)
    exp = exp[exp["year_month"] <= COVER_MAX].copy()

    unmatched = sorted(set(exp.county_fips) - set(xw.county_fips))
    if unmatched:
        lost = exp[exp.county_fips.isin(unmatched)].n_detained.sum()
        print(f"  {len(unmatched)} counties not in crosswalk "
              f"({int(lost):,} detentions, {100*lost/exp.n_detained.sum():.2f}%)")

    m = exp.merge(xw, on="county_fips", how="inner")
    share = m.groupby(["county_fips", "year_month"])["court_area"].transform("size")
    for c in ["n_detained", "pop_total", "pop_noncitizen"]:
        m[c] = m[c] / share

    panel = (m.groupby(["court_area", "year_month"], dropna=False)
             .agg(n_counties=("county_fips", "nunique"),
                  n_detained=("n_detained", "sum"),
                  pop_total=("pop_total", "sum"),
                  pop_noncitizen=("pop_noncitizen", "sum"),
                  county_spike_share=("spike", "mean"),
                  county_excess_sum=("excess", "sum"))
             .reset_index())
    panel["detained_per_100k"] = (
        100_000 * panel["n_detained"] / panel["pop_total"].where(panel["pop_total"] > 0))
    panel["year"] = panel["year_month"].str[:4].astype(int)
    panel["period"] = np.where(panel["year_month"] < SPLICE, "FOIA", "DDP")

    panel = spike_recompute(panel, "court_area", "n_detained")
    panel = panel.rename(columns={"spike": "court_spike",
                                  "excess": "court_excess",
                                  "excess_sd": "court_excess_sd",
                                  "roll_mean": "court_roll_mean",
                                  "roll_sd": "court_roll_sd",
                                  "eligible": "court_eligible"})
    cols = ["court_area", "year_month", "year", "period", "n_counties",
            "n_detained", "pop_total", "pop_noncitizen", "detained_per_100k",
            "court_roll_mean", "court_roll_sd", "court_eligible", "court_spike",
            "court_excess", "court_excess_sd",
            "county_spike_share", "county_excess_sum"]
    panel["partial_month"] = panel["year_month"].isin(PARTIAL_MONTHS)
    cols = cols + ["partial_month"]
    panel = panel[cols].sort_values(["court_area", "year_month"])
    panel.to_csv(OUT / "court_area_month_exposure.csv", index=False)
    print(f"\nwrote court_area_month_exposure.csv: {len(panel):,} rows, "
          f"{panel.court_area.nunique()} court areas x {panel.year_month.nunique()} months")

    summ = (panel.groupby("court_area")
            .agg(n_counties=("n_counties", "max"),
                 months_eligible=("court_eligible", "sum"),
                 total_detained=("n_detained", "sum"),
                 mean_pop=("pop_total", "mean"),
                 spike_months=("court_spike", "sum"),
                 total_excess=("court_excess", "sum"),
                 total_excess_sd=("court_excess_sd", "sum"))
            .reset_index())
    summ["mean_detained_per_100k"] = (
        100_000 * summ["total_detained"] / (summ["mean_pop"] * summ["months_eligible"]).where(
            summ["mean_pop"] > 0))
    summ["spike_frequency"] = summ["spike_months"] / summ["months_eligible"].where(
        summ["months_eligible"] > 0)
    summ = summ.sort_values("total_excess", ascending=False)
    summ.to_csv(OUT / "court_area_exposure_summary.csv", index=False)

    cv_courts = sorted(xw[xw.county_fips.isin(CV_FIPS)].court_area.unique())
    print(f"Central Valley counties map to {len(cv_courts)} court area(s): {cv_courts}")
    make_figures(panel, summ, cv_courts)
    write_doc(panel, summ, xw, xw_path, cv_courts, unmatched)


def make_figures(panel, summ, cv_courts) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    top = summ.nlargest(25, "total_excess")
    fig, ax = plt.subplots(figsize=(10, 8))
    colors = ["#c1440e" if c in cv_courts else "#4c72b0" for c in top.court_area]
    ax.barh(top.court_area[::-1], top.total_excess[::-1], color=colors[::-1])
    ax.set_xlabel("Total excess detentions during spike months")
    ax.set_title("Enforcement exposure around immigration courts\n"
                 "Top 25 court areas by cumulative spike intensity, 2012-2026")
    if any(c in cv_courts for c in top.court_area):
        ax.text(0.98, 0.02, "Central Valley court area(s) in orange",
                transform=ax.transAxes, ha="right", fontsize=9, color="#c1440e")
    fig.tight_layout()
    fig.savefig(OUT / "fig1_court_ranked_exposure.png", dpi=200)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(9, 5))
    vals = summ.mean_detained_per_100k.replace([np.inf, -np.inf], np.nan).dropna()
    ax.hist(vals, bins=40, color="#4c72b0", alpha=.75)
    for c in cv_courts:
        row = summ[summ.court_area == c]
        if len(row) and pd.notna(row.mean_detained_per_100k.iloc[0]):
            ax.axvline(row.mean_detained_per_100k.iloc[0], color="#c1440e", lw=2)
            ax.text(row.mean_detained_per_100k.iloc[0], ax.get_ylim()[1] * .9, f" {c}",
                    color="#c1440e", fontsize=9)
    ax.set_xlabel("Detentions per 100,000 residents per month")
    ax.set_ylabel("Number of court areas")
    ax.set_title("Central Valley court area(s) against the national distribution")
    fig.tight_layout()
    fig.savefig(OUT / "fig2_central_valley_vs_national.png", dpi=200)
    plt.close(fig)

    plotp = panel[~panel["partial_month"]]
    nat = plotp.groupby("year_month")["detained_per_100k"].mean()
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(pd.to_datetime(nat.index + "-01"), nat.values, color="#4c72b0",
            lw=1.5, label="National average")
    for c in cv_courts:
        s = plotp[plotp.court_area == c].set_index("year_month")["detained_per_100k"]
        ax.plot(pd.to_datetime(s.index + "-01"), s.values, color="#c1440e",
                lw=1.5, label=c)
    ax.axvline(pd.Timestamp("2023-12-01"), color="grey", ls="--", lw=1)
    ax.text(pd.Timestamp("2023-12-01"), ax.get_ylim()[1] * .95,
            " data source changes", fontsize=8, color="grey")
    ax.set_ylabel("Detentions per 100,000 residents")
    ax.set_title("Enforcement exposure over time: Central Valley against national average")
    ax.legend(fontsize=9)
    fig.tight_layout()
    fig.savefig(OUT / "fig3_court_time_series.png", dpi=200)
    plt.close(fig)
    print("wrote 3 figures")


def write_doc(panel, summ, xw, xw_path, cv_courts, unmatched) -> None:
    txt = f"""ENFORCEMENT EXPOSURE AROUND IMMIGRATION COURTS

Prepared by Ethan Xie (xief@udel.edu).

UNIT OF OBSERVATION
One row per immigration court area per month, in
court_area_month_exposure.csv. A companion file,
court_area_exposure_summary.csv, has one row per court area across the
whole period. Both come from the balanced county-month detention file,
aggregated up using the crosswalk described below.

DATE RANGE
{panel.year_month.min()} through {panel.year_month.max()}. The county data runs two
months further, to 2026-05, but the detention records stop at
{COVER_MAX}, so the later months are left out rather than shown as zeros.

COUNTY TO COURT AREA
Crosswalk file: {xw_path.name}
{xw.county_fips.nunique():,} counties mapped to {xw.court_area.nunique()} court areas.
Counties in the detention data with no court area in the crosswalk: {len(unmatched)}.
Where a county maps to more than one court area, its detentions and
population are split evenly among them, so no county is counted twice.

DENOMINATOR
Population is the county total from the Census, summed across the
counties in each court area. Detentions per 100,000 is computed from
those sums, not averaged from county rates, so large counties carry
their proper weight.

SPIKE DEFINITION
A month is a spike when detentions run more than {K} standard deviations
above that same court area's own average over the prior twelve months.
The first twelve months of any series have no spike value, since there
is not yet a year of history to compare against.

Two versions are in the file and they answer different questions.
court_spike recomputes the rule on the court area's own monthly totals,
which is the natural reading of a court area spiking. county_spike_share
is the share of that court area's counties that were spiking, which
picks up whether a surge was broad or concentrated in one county.
court_excess is how many detentions above normal the spike months ran,
and court_excess_sd is the same in standard deviations, capped so that a
nearly flat court area cannot produce a runaway figure.

PARTIAL MONTHS
Two months are incomplete and are flagged in the partial_month column.
November 2023 is where the FOIA file stops partway through, and March
2026 is where the newer data currently ends, with records only through
the 11th. Both would read as sharp collapses if plotted, so the figures
leave them out while the panel keeps them, flagged. February 2026 is
structurally complete but may still be revised upward, since recent
months in the newer source can lag.


SOURCE CHANGE IN DECEMBER 2023
The detention data changes source at {SPLICE}. Through November 2023 it
comes from the FOIA workbooks and counts book-ins. From December 2023 it
comes from the Deportation Data Project and counts facility bookings
within a custody stay, which is the closest matching unit. The two line
up closely month to month, but the break is a sensible place for a
control. November 2023 is also a partial month, since the FOIA file
stops partway through it. The period column marks which side each row
falls on, and the dashed line in the time-series figure marks the break.

WHAT THESE NUMBERS DO AND DO NOT SHOW
The detention records give the county of the facility where someone was
held, not the county where the arrest happened. These figures therefore
describe detention activity in the counties around each court, which is
why we are calling it enforcement exposure rather than enforcement.

CENTRAL VALLEY
Central Valley counties fall into: {', '.join(cv_courts) if cv_courts else 'none found'}.

FILES
court_area_month_exposure.csv    court area by month
court_area_exposure_summary.csv  one row per court area
fig1_court_ranked_exposure.png   top 25 court areas by spike intensity
fig2_central_valley_vs_national.png  Central Valley against the national spread
fig3_court_time_series.png       exposure over time
"""
    (OUT / "documentation_note.txt").write_text(txt, encoding="utf-8")
    print("wrote documentation_note.txt")


if __name__ == "__main__":
    main()
