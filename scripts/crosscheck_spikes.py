"""Independent recomputation of the Task-1 spike measure, in Python.

Same definition as the professor's R script (trailing 12-month mean/sd,
spike if E > mean + 1.5*sd, burn-in months NA), implemented separately so
the two can be compared row-for-row. Also produces the diagnostics we
promised to flag rather than silently fix: splice-month artifacts,
zero-sd spikes, infinite intensity ratios.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

DIR = Path(r"C:\Users\xief\.local\bin\ucmerced\analysis\task1_spikes")

df = pd.read_csv(DIR / "detention_county_month.csv", dtype={"county_fips": str})
df["county_fips"] = df["county_fips"].str.zfill(5)
df["date"] = pd.to_datetime(dict(year=df.year, month=df.month, day=1))
df = df.sort_values(["county_fips", "date"]).reset_index(drop=True)

g = df.groupby("county_fips")["detention_count"]
df["roll_mean"] = g.transform(lambda s: s.rolling(12).mean().shift(1))
df["roll_sd"] = g.transform(lambda s: s.rolling(12).std(ddof=1).shift(1))

eligible = df["roll_mean"].notna() & df["roll_sd"].notna()
df["spike"] = np.where(
    eligible,
    (df["detention_count"] > df["roll_mean"] + 1.5 * df["roll_sd"]).astype(float),
    np.nan,
)

el = df[eligible]
print("=== Python recomputation ===")
print(f"eligible county-months: {len(el):,}")
print(f"spike months: {int(el.spike.sum()):,} ({100*el.spike.mean():.2f}% of eligible)")

def longest_streak(s: pd.Series) -> int:
    best = cur = 0
    for v in s.dropna():
        cur = cur + 1 if v == 1 else 0
        best = max(best, cur)
    return best

summ = []
for fips, grp in df.groupby("county_fips"):
    e = grp[grp.spike.notna()]
    n_el, n_sp = len(e), int(e.spike.sum())
    spike_e = e[e.spike == 1]["detention_count"].mean()
    non_e = e[e.spike == 0]["detention_count"].mean()
    inten = spike_e / non_e if (non_e and non_e > 0) else np.inf if n_sp else np.nan
    summ.append((fips, n_el, n_sp, n_sp / n_el if n_el else np.nan,
                 longest_streak(e.spike), inten))
py = pd.DataFrame(summ, columns=["county_fips", "n_months_eligible", "n_spike_months",
                                 "spike_frequency", "longest_streak", "intensity"])
py.to_csv(DIR / "python_crosscheck_summary.csv", index=False)

r_path = DIR / "table_spike_summary_by_county.csv"
if r_path.exists():
    r = pd.read_csv(r_path, dtype={"county_fips": str})
    r["county_fips"] = r["county_fips"].str.zfill(5)
    m = py.merge(r, on="county_fips", suffixes=("_py", "_r"))
    print("\n=== R vs Python comparison ===")
    for col in ["n_months_eligible", "n_spike_months", "longest_streak"]:
        same = (m[f"{col}_py"] == m[f"{col}_r"]).sum()
        print(f"{col}: {same}/{len(m)} counties identical")
    freq_close = np.isclose(m.spike_frequency_py, m.spike_frequency_r,
                            atol=1e-9, equal_nan=True).sum()
    print(f"spike_frequency: {freq_close}/{len(m)} within 1e-9")
    both = m.intensity_py.replace([np.inf], np.nan).notna() & m.intensity_r.notna()
    int_close = np.isclose(m.loc[both, "intensity_py"], m.loc[both, "intensity_r"],
                           rtol=1e-6).sum()
    print(f"intensity (finite both sides): {int_close}/{int(both.sum())} within 1e-6")
    bad = m[(m.n_spike_months_py != m.n_spike_months_r)]
    if len(bad):
        print("MISMATCHES:")
        print(bad.head(10).to_string(index=False))
else:
    print("\n(R summary not present yet; run again after the R script finishes)")

print("\n=== Diagnostics to flag ===")
z = el[el.roll_sd == 0]
zs = z[z.spike == 1]
print(f"1. zero-sd months: {len(z):,}; spikes among them: {len(zs):,} "
      f"({100*len(zs)/max(int(el.spike.sum()),1):.1f}% of ALL spikes)")
print(f"   of those, spikes where the month's count is 1: {int((zs.detention_count==1).sum()):,}")

nat = el.groupby("date")["spike"].mean()
w = nat.loc["2023-08-01":"2024-04-01"]
print("2. national spike share around the Nov-2023/Dec-2023 splice:")
print((100 * w).round(1).to_string())

n_inf = np.isinf(py.intensity).sum()
print(f"3. counties with infinite intensity (never a nonzero non-spike month): {n_inf}")

top = py.nlargest(5, "spike_frequency")[["county_fips", "n_spike_months",
                                         "spike_frequency", "longest_streak"]]
print("4. highest spike-frequency counties:")
print(top.to_string(index=False))
