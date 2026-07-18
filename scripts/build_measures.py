from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

PROC = Path(r"C:\Users\xief\.local\bin\ucmerced\data\processed")
COVER_MAX = "2026-03"
K = 1.5
Z_CAP = 10.0


def spike_series(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values(["county_fips", "year_month"]).copy()
    g = df.groupby("county_fips")["n_detained"]
    df["roll_mean"] = g.transform(lambda s: s.rolling(12).mean().shift(1))
    df["roll_sd"] = g.transform(lambda s: s.rolling(12).std(ddof=1).shift(1))
    elig = df["roll_mean"].notna() & df["roll_sd"].notna()
    df["eligible"] = elig
    df["spike"] = np.where(
        elig, (df["n_detained"] > df["roll_mean"] + K * df["roll_sd"]).astype(float),
        np.nan)
    df["excess"] = np.where(df["spike"] == 1, df["n_detained"] - df["roll_mean"], 0.0)
    raw_z = (df["n_detained"] - df["roll_mean"]) / df["roll_sd"].where(df["roll_sd"] > 0)
    df["excess_sd"] = np.where(
        (df["spike"] == 1) & (df["roll_sd"] > 0),
        np.minimum(raw_z, Z_CAP),
        0.0)
    return df


def runs(spikes: list[float]) -> list[int]:
    lengths, cur = [], 0
    for v in spikes:
        if v == 1:
            cur += 1
        elif cur:
            lengths.append(cur)
            cur = 0
    if cur:
        lengths.append(cur)
    return lengths


def county_measures(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for fips, g in df.groupby("county_fips"):
        e = g[g["eligible"]]
        n_elig = len(e)
        if n_elig == 0:
            continue
        n_spike = int(e["spike"].sum())
        rl = runs(list(e["spike"]))
        n_epi = len(rl)
        longest = max(rl) if rl else 0
        rows.append({
            "county_fips": fips,
            "county_name": g["county_name"].iloc[0],
            "state_abbr": g["state_abbr"].iloc[0],
            "n_months_eligible": n_elig,
            "n_spike_months": n_spike,
            "spike_frequency": n_spike / n_elig,
            "longest_streak": longest,
            "n_spike_episodes": n_epi,
            "mean_episode_months": (n_spike / n_epi) if n_epi else 0.0,
            "spike_fragmentation": (n_epi / n_spike) if n_spike else np.nan,
            "intensity_excess": float(e["excess"].sum()),
            "intensity_sd": float(e["excess_sd"].sum()),
            "total_detained": int(g["n_detained"].sum()),
        })
    return pd.DataFrame(rows)


det = pd.read_csv(PROC / "county_month_detention_population_balanced.csv",
                  dtype={"county_fips": str}, low_memory=False)
det["county_fips"] = det["county_fips"].str.zfill(5)
det = det[det["year_month"] <= COVER_MAX].copy()
det["n_detained"] = det["n_detained"].fillna(0)

detail = spike_series(det)
keep = ["county_fips", "county_name", "state_abbr", "year_month", "n_detained",
        "roll_mean", "roll_sd", "eligible", "spike", "excess", "excess_sd"]
detail[keep].to_csv(PROC / "county_month_enforcement_detail.csv", index=False)

meas = county_measures(detail).sort_values("intensity_excess", ascending=False)
meas.to_csv(PROC / "county_enforcement_measures.csv", index=False)

print(f"detail rows: {len(detail):,}")
print(f"measures: {len(meas):,} counties with >=12 months of history")
print(f"  counties with any spike: {(meas.n_spike_months>0).sum()}")
print(f"  total spike-months: {int(meas.n_spike_months.sum()):,}")
print(f"  overall spike rate: {100*meas.n_spike_months.sum()/meas.n_months_eligible.sum():.2f}%")
print("\ntop 8 counties by intensity_excess (total extra detentions above normal):")
cols = ["county_fips", "county_name", "state_abbr", "spike_frequency",
        "longest_streak", "n_spike_episodes", "spike_fragmentation",
        "intensity_excess", "intensity_sd"]
with pd.option_context("display.width", 200, "display.max_columns", 20):
    print(meas[cols].head(8).to_string(index=False))
