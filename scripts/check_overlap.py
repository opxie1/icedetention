import pandas as pd

det = pd.read_csv("data/processed/county_month_panel.csv")
print("FOIA panel months from Jul 2023 onwards:")
for ym in sorted(det["year_month"].unique()):
    if ym >= "2023-07":
        sub = det[det["year_month"] == ym]
        rows = len(sub)
        eps = sub["n_episodes"].sum()
        print(f"  {ym}: {rows:,} county rows, {eps:,} episodes")
