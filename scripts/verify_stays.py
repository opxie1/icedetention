import pandas as pd

yr = pd.read_csv("data/processed/county_year_stays_panel.csv", dtype={"county_fips": str})
yr["county_fips"] = yr["county_fips"].str.zfill(5)
print("Stays panel year coverage (year column = year of book_in_date_time_first):")
agg = yr.groupby("year").agg(
    n_stays=("n_stays", "sum"),
    total_days=("total_days", "sum"),
)
print(agg.to_string())
print()
print("Top 10 counties by stays (across all years):")
g = yr.groupby(["county_fips", "county_name", "state_abbr"])["n_stays"].sum()
print(g.sort_values(ascending=False).head(10).to_string())
print()
mo = pd.read_csv("data/processed/county_month_stays_panel.csv")
ym_min = mo["year_month"].min()
ym_max = mo["year_month"].max()
print(f"Month panel: {len(mo)} rows, months from {ym_min} to {ym_max}")
print()
un = pd.read_csv("data/processed/unmapped_stays.csv")
print(f"Unmapped: {len(un)} groups, {un['n_stays'].sum():,} stays")
print("Top unmapped (probably no state info):")
print(un.head(8).to_string(index=False))
