from __future__ import annotations

import calendar
import glob
from pathlib import Path

import pandas as pd

from ice_pipeline.known_facilities import norm_compact, norm_county
from ice_pipeline.stays import _STATE_NAME, _build_fips_lookup

REPO = Path(r"C:\Users\xief\.local\bin\ucmerced")
PROC = REPO / "data" / "processed"
REFS = REPO / "references"
PARQUET = Path(r"C:\Users\xief\Downloads\detention-stays_filtered_20260528_033200.parquet")
FOIA_MAX = "2023-11"
DDP_MIN = "2023-12-01"


def foia_countydays() -> tuple[pd.DataFrame, pd.DataFrame]:
    cw = pd.read_csv(PROC / "facility_crosswalk.csv", dtype=str).fillna("")
    cw["facility_name"] = cw["facility_name"].str.strip().str.upper()
    cw["facility_code"] = cw["facility_code"].str.strip().str.upper()
    cwj = cw[["facility_name", "facility_code", "county_fips"]]

    triples, counts = [], []
    for f in sorted(glob.glob(str(REPO / "data/interim/fy*_detentions.csv.gz"))):
        for chunk in pd.read_csv(f, usecols=["facility_name", "facility_code", "book_in_date"],
                                 dtype=str, chunksize=200_000, keep_default_na=False):
            chunk["facility_name"] = chunk["facility_name"].str.strip().str.upper()
            chunk["facility_code"] = chunk["facility_code"].str.strip().str.upper()
            m = chunk.merge(cwj, on=["facility_name", "facility_code"], how="left")
            m["dt"] = pd.to_datetime(m["book_in_date"], errors="coerce")
            m = m[(m["county_fips"].fillna("") != "") & m["dt"].notna()]
            m["year_month"] = m["dt"].dt.strftime("%Y-%m")
            m = m[m["year_month"] <= FOIA_MAX]
            if m.empty:
                continue
            m["day"] = m["dt"].dt.day
            triples.append(m[["county_fips", "year_month", "day"]].drop_duplicates())
            counts.append(m.groupby(["county_fips", "year_month"]).size()
                          .rename("n_bookins").reset_index())
    trip = pd.concat(triples, ignore_index=True).drop_duplicates()
    cnt = (pd.concat(counts, ignore_index=True)
           .groupby(["county_fips", "year_month"])["n_bookins"].sum().reset_index())
    return trip, cnt


def ddp_countydays() -> tuple[pd.DataFrame, pd.DataFrame]:
    fips_csv = sorted(REFS.glob("fips*state*.csv"))[0]
    lookup = _build_fips_lookup(fips_csv)
    s = pd.read_parquet(PARQUET, columns=[
        "book_in_date_time_first", "state_longest", "county_longest",
        "detention_facility_code_longest"])
    s["dt"] = pd.to_datetime(s["book_in_date_time_first"], errors="coerce", utc=True)
    s = s[s["dt"] >= pd.Timestamp(DDP_MIN, tz="UTC")].copy()
    s["state_abbr"] = s["state_longest"].fillna("").astype(str).str.strip().str.upper()
    s["county_raw"] = s["county_longest"].fillna("").astype(str).str.strip()

    def resolve(row):
        sa, cr = row["state_abbr"], row["county_raw"]
        if sa and cr:
            hit = lookup.get((sa, norm_county(cr))) or lookup.get((sa, norm_compact(cr)))
            if hit:
                return hit[0]
        return ""
    s["county_fips"] = s.apply(resolve, axis=1)

    cw = pd.read_csv(PROC / "facility_crosswalk.csv", dtype=str).fillna("")
    fac2fips = dict(zip(cw["facility_code"], cw["county_fips"]))
    need = s["county_fips"] == ""
    resc = s.loc[need, "detention_facility_code_longest"].astype(str).map(fac2fips).fillna("")
    s.loc[need, "county_fips"] = resc.where(resc.str.len() == 5, "")

    s = s[s["county_fips"] != ""].copy()
    s["year_month"] = s["dt"].dt.strftime("%Y-%m")
    s["day"] = s["dt"].dt.day
    trip = s[["county_fips", "year_month", "day"]].drop_duplicates()
    cnt = s.groupby(["county_fips", "year_month"]).size().rename("n_bookins").reset_index()
    return trip, cnt


def day_stats(days: list[int]) -> tuple[int, int, int, int]:
    days = sorted(days)
    runs, cur = [], 1
    for i in range(1, len(days)):
        if days[i] == days[i - 1] + 1:
            cur += 1
        else:
            runs.append(cur)
            cur = 1
    runs.append(cur)
    return len(days), max(runs), len(runs), days[-1] - days[0] + 1


print("=== FOIA daily ===")
ftrip, fcnt = foia_countydays()
print(f"  county-days: {len(ftrip):,}  county-months: {len(fcnt):,}")
print("=== DDP daily ===")
dtrip, dcnt = ddp_countydays()
print(f"  county-days: {len(dtrip):,}  county-months: {len(dcnt):,}")

trip = pd.concat([ftrip, dtrip], ignore_index=True)
cnt = pd.concat([fcnt, dcnt], ignore_index=True)

rows = []
for (fips, ym), g in trip.groupby(["county_fips", "year_month"]):
    ad, mx, nr, span = day_stats(list(g["day"]))
    rows.append((fips, ym, ad, mx, nr, span))
detail = pd.DataFrame(rows, columns=["county_fips", "year_month", "active_days",
                                     "max_consecutive_active_days", "n_active_runs",
                                     "span_days"])
detail = detail.merge(cnt, on=["county_fips", "year_month"], how="left")
detail["year"] = detail["year_month"].str[:4].astype(int)
detail["month"] = detail["year_month"].str[5:7].astype(int)
detail["days_in_month"] = detail.apply(
    lambda r: calendar.monthrange(r["year"], r["month"])[1], axis=1)
fipsref = pd.read_csv(REFS / "fips_state_county.csv", dtype={"fips": str})
fipsref["fips"] = fipsref["fips"].str.zfill(5)
detail = detail.merge(fipsref.rename(columns={"fips": "county_fips"})[
    ["county_fips", "county_name", "state_name"]], on="county_fips", how="left")
detail = detail[["county_fips", "county_name", "state_name", "year_month",
                 "n_bookins", "active_days", "max_consecutive_active_days",
                 "n_active_runs", "span_days", "days_in_month"]].sort_values(
    ["county_fips", "year_month"])
detail.to_csv(PROC / "county_month_daily_activity.csv", index=False)

active = detail[detail["n_bookins"] > 0]
summ = (active.groupby("county_fips")
        .agg(county_name=("county_name", "first"),
             state_name=("state_name", "first"),
             active_months=("year_month", "size"),
             mean_active_days=("active_days", "mean"),
             mean_longest_daily_run=("max_consecutive_active_days", "mean"),
             mean_daily_clusters=("n_active_runs", "mean"),
             mean_bookins_per_active_day=("n_bookins", "sum"))
        .reset_index())
summ["mean_bookins_per_active_day"] = (
    active.groupby("county_fips").apply(
        lambda g: g["n_bookins"].sum() / g["active_days"].sum(), include_groups=False).values)
summ["within_month_intermittency"] = summ["mean_daily_clusters"] / summ["mean_active_days"]
summ = summ.sort_values("active_months", ascending=False)
summ.to_csv(PROC / "county_daily_intermittency_summary.csv", index=False)

print(f"\nwrote county_month_daily_activity.csv: {len(detail):,} rows")
print(f"wrote county_daily_intermittency_summary.csv: {len(summ):,} counties")
