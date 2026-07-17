from __future__ import annotations

from pathlib import Path

import pandas as pd

REPO = Path(r"C:\Users\xief\.local\bin\ucmerced")
PROC = REPO / "data" / "processed"

COVER_MIN, COVER_MAX = "2012-01", "2026-03"

STATE_ABBR = {
    "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR",
    "California": "CA", "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE",
    "District of Columbia": "DC", "Florida": "FL", "Georgia": "GA", "Hawaii": "HI",
    "Idaho": "ID", "Illinois": "IL", "Indiana": "IN", "Iowa": "IA", "Kansas": "KS",
    "Kentucky": "KY", "Louisiana": "LA", "Maine": "ME", "Maryland": "MD",
    "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN", "Mississippi": "MS",
    "Missouri": "MO", "Montana": "MT", "Nebraska": "NE", "Nevada": "NV",
    "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM", "New York": "NY",
    "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK",
    "Oregon": "OR", "Pennsylvania": "PA", "Rhode Island": "RI",
    "South Carolina": "SC", "South Dakota": "SD", "Tennessee": "TN", "Texas": "TX",
    "Utah": "UT", "Vermont": "VT", "Virginia": "VA", "Washington": "WA",
    "West Virginia": "WV", "Wisconsin": "WI", "Wyoming": "WY", "Puerto Rico": "PR",
}


def load_pop() -> pd.DataFrame:
    pop = pd.read_csv(PROC / "county_year_population.csv",
                      dtype={"county_fips": str}, low_memory=False)
    pop["county_fips"] = pop["county_fips"].str.zfill(5)
    pop = pop.sort_values(["county_fips", "year"])
    pcols = ["pop_total", "pop_hispanic", "pop_noncitizen",
             "pct_hispanic", "pct_noncitizen", "pop_total_refyear"]
    pop[pcols] = pop.groupby("county_fips")[pcols].bfill()
    return pop


def load_universe() -> pd.DataFrame:
    u = pd.read_csv(REPO / "references" / "balanced_panel_universe.csv",
                    dtype={"county5": str})
    u["county_fips"] = u["county5"].str.zfill(5)
    u["year_month"] = u["year"].astype(str) + "-" + u["month"].astype(str).str.zfill(2)
    return u[["county_fips", "year", "month", "year_month"]]


def period_of(ym: pd.Series) -> pd.Series:
    p = pd.Series("DDP", index=ym.index)
    p[ym <= "2023-11"] = "FOIA"
    p[ym > COVER_MAX] = "beyond_data"
    return p


def build_month() -> pd.DataFrame:
    grid = load_universe()
    grid["period"] = period_of(grid["year_month"])

    pop = load_pop()
    names = (pop[["county_fips", "county_name", "state_name"]]
             .drop_duplicates("county_fips"))
    popcols = ["county_fips", "year", "pop_total", "pop_hispanic", "pop_noncitizen",
               "pct_hispanic", "pct_noncitizen", "pop_total_refyear"]

    det = pd.read_csv(PROC / "county_month_detention_combined.csv",
                      dtype={"county_fips": str})
    det["county_fips"] = det["county_fips"].str.zfill(5)
    detcols = ["county_fips", "year_month", "n_detained", "n_episodes", "n_stays",
               "n_stints_total", "n_unique_persons", "detained_days"]

    out = (grid
           .merge(names, on="county_fips", how="left")
           .merge(pop[popcols], on=["county_fips", "year"], how="left")
           .merge(det[detcols], on=["county_fips", "year_month"], how="left"))

    out["state_abbr"] = out["state_name"].map(STATE_ABBR).fillna("")

    had_row = out["n_detained"].notna()
    in_window = out["year_month"] <= COVER_MAX
    zero = in_window & ~had_row

    out.loc[zero, ["n_detained", "n_unique_persons", "detained_days"]] = 0
    foia_zero = zero & (out["period"] == "FOIA")
    ddp_zero = zero & (out["period"] == "DDP")
    out.loc[foia_zero, "n_episodes"] = 0
    out.loc[ddp_zero, ["n_stays", "n_stints_total"]] = 0

    out["detained_per_100k"] = (
        100_000 * out["n_detained"] / out["pop_total"].where(out["pop_total"] > 0)
    )

    cols = ["county_fips", "county_name", "state_abbr", "state_name",
            "year", "month", "year_month", "period",
            "n_detained", "n_episodes", "n_stays", "n_stints_total",
            "n_unique_persons", "detained_days",
            "pop_total", "pop_hispanic", "pop_noncitizen",
            "pct_hispanic", "pct_noncitizen", "pop_total_refyear",
            "detained_per_100k"]
    out = out[cols].sort_values(["state_abbr", "county_name", "year_month"])
    out.to_csv(PROC / "county_month_detention_population_balanced.csv", index=False)
    return out


def build_year(month_bal: pd.DataFrame) -> pd.DataFrame:
    m = month_bal.copy()
    agg = (m.groupby(["county_fips", "county_name", "state_abbr", "state_name", "year"],
                     dropna=False)
           .agg(n_detained=("n_detained", "sum"),
                n_unique_persons=("n_unique_persons", "sum"),
                detained_days=("detained_days", "sum"),
                n_episodes=("n_episodes", "sum"),
                n_stays=("n_stays", "sum"),
                n_stints_total=("n_stints_total", "sum"),
                months_with_data=("n_detained", lambda s: int(s.notna().sum())))
           .reset_index())
    pop = load_pop()
    popcols = ["county_fips", "year", "pop_total", "pop_hispanic", "pop_noncitizen",
               "pct_hispanic", "pct_noncitizen", "pop_total_refyear"]
    agg = agg.merge(pop[popcols], on=["county_fips", "year"], how="left")
    agg["detained_per_100k"] = (
        100_000 * agg["n_detained"] / agg["pop_total"].where(agg["pop_total"] > 0)
    )
    agg = agg.sort_values(["state_abbr", "county_name", "year"])
    agg.to_csv(PROC / "county_year_detention_population_balanced.csv", index=False)
    return agg


mb = build_month()
yb = build_year(mb)

det_src = pd.read_csv(PROC / "county_month_detention_combined.csv", dtype={"county_fips": str})
det_src["county_fips"] = det_src["county_fips"].str.zfill(5)
terr = det_src[det_src.county_fips.isin(["66010", "69110", "78030"])]["n_detained"].sum()
kept = mb["n_detained"].sum()
print(f"month balanced: {len(mb):,} rows, {mb.county_fips.nunique()} counties x "
      f"{mb.year_month.nunique()} months")
print(f"  dup key: {mb.duplicated(['county_fips','year_month']).sum()}")
print(f"  n_detained total in balanced: {int(kept):,}")
print(f"  + territories dropped (outside his grid): {int(terr):,}")
print(f"  = {int(kept)+int(terr):,} (source combined: {int(det_src.n_detained.sum()):,})")
print(f"  zero-detention rows: {int((mb.n_detained==0).sum()):,}")
print(f"  blank (beyond 2026-03) rows: {int(mb.n_detained.isna().sum()):,}")
print(f"  population present: {100*mb.pop_total.notna().mean():.2f}%")
print(f"year balanced: {len(yb):,} rows, years {yb.year.min()}..{yb.year.max()}")
