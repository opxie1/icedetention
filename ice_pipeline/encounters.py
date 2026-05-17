"""ERO Encounters site crosswalk and county roll-up."""

from __future__ import annotations

import logging
import re
from pathlib import Path

import pandas as pd

from . import config
from .known_facilities import (
    county_token_from_name,
    lookup_city_county,
    norm_compact,
    norm_county,
)
from .patterns import classify_unusual, USPS_STATE_ABBR

log = logging.getLogger(__name__)

SITE_OVERRIDES_FILENAME = "site_overrides.csv"
SITE_OVERRIDES_TEMPLATE_FILENAME = "site_overrides_template.csv"

SITE_CROSSWALK_FILENAME = "site_crosswalk.csv"
SITE_REVIEW_FILENAME = "site_crosswalk_review.csv"
ENC_YEAR_PANEL_FILENAME = "county_year_encounters_panel.csv"
ENC_MONTH_PANEL_FILENAME = "county_month_encounters_panel.csv"
ENC_UNMAPPED_FILENAME = "unmapped_sites.csv"

SITE_OVERRIDE_COLUMNS = [
    "responsible_site",
    "state_abbr",
    "county_fips",
    "county_name",
    "unusual_flag",
    "unusual_type",
    "notes",
]


def parse_site(site: str) -> dict:
    if not site:
        return {"city": "", "state": "", "suffix": ""}
    # Trailing space/end stops "MT." matching as Montana.
    _state_prefix = re.compile(r"^([A-Z]{2})(?:\s|$)")

    parts = [p.strip() for p in site.split(",")]
    for i, part in enumerate(parts):
        upper = part.strip().upper()
        m = _state_prefix.match(upper)
        if not m:
            continue
        state = m.group(1)
        if state not in USPS_STATE_ABBR:
            continue
        city = ", ".join(parts[:i]).strip()
        after = part.strip()[2:].strip(" ,-")
        suffix_parts = [p for p in [after, *parts[i + 1:]] if p]
        suffix = ", ".join(suffix_parts).strip()
        return {"city": city, "state": state, "suffix": suffix}
    return {"city": "", "state": "", "suffix": ""}


def _load_state_lookup(fips_csv: Path) -> pd.DataFrame:
    fips = pd.read_csv(fips_csv, dtype={"fips": str})
    fips["fips"] = fips["fips"].str.zfill(5)
    fips["state_fips"] = fips["fips"].str[:2]
    fips["county_fips"] = fips["fips"]
    fips["state_name"] = fips["state_name"].str.strip()
    fips["county_name"] = fips["county_name"].str.strip()
    state_abbr_map = {
        "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR",
        "California": "CA", "Colorado": "CO", "Connecticut": "CT",
        "Delaware": "DE", "District of Columbia": "DC", "Florida": "FL",
        "Georgia": "GA", "Hawaii": "HI", "Idaho": "ID", "Illinois": "IL",
        "Indiana": "IN", "Iowa": "IA", "Kansas": "KS", "Kentucky": "KY",
        "Louisiana": "LA", "Maine": "ME", "Maryland": "MD",
        "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN",
        "Mississippi": "MS", "Missouri": "MO", "Montana": "MT",
        "Nebraska": "NE", "Nevada": "NV", "New Hampshire": "NH",
        "New Jersey": "NJ", "New Mexico": "NM", "New York": "NY",
        "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH",
        "Oklahoma": "OK", "Oregon": "OR", "Pennsylvania": "PA",
        "Rhode Island": "RI", "South Carolina": "SC", "South Dakota": "SD",
        "Tennessee": "TN", "Texas": "TX", "Utah": "UT", "Vermont": "VT",
        "Virginia": "VA", "Washington": "WA", "West Virginia": "WV",
        "Wisconsin": "WI", "Wyoming": "WY", "Puerto Rico": "PR",
        "Guam": "GU", "U.S. Virgin Islands": "VI", "American Samoa": "AS",
        "Northern Mariana Islands": "MP",
    }
    fips["state_abbr"] = fips["state_name"].map(state_abbr_map).fillna("")
    # Reference CSV split "District of Columbia" on the comma.
    dc_rows = fips["fips"] == "11001"
    if dc_rows.any():
        fips.loc[dc_rows, "state_name"] = "District of Columbia"
        fips.loc[dc_rows, "state_abbr"] = "DC"
    return fips


def _load_overrides(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=SITE_OVERRIDE_COLUMNS)
    df = pd.read_csv(path, dtype=str).fillna("")
    missing = [c for c in SITE_OVERRIDE_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(
            f"{path.name} is missing required columns: {missing}. "
            f"Expected: {SITE_OVERRIDE_COLUMNS}"
        )
    df["responsible_site"] = df["responsible_site"].str.strip().str.upper()
    df["state_abbr"] = df["state_abbr"].str.strip().str.upper()
    cf = df["county_fips"].str.strip()
    df["county_fips"] = cf.apply(lambda x: x.zfill(5) if x else "")
    df["county_name"] = df["county_name"].str.strip()
    return df


def _unique_sites(interim_dir: Path) -> pd.DataFrame:
    files = sorted(interim_dir.glob("encounters_*.csv*"))
    if not files:
        raise FileNotFoundError(
            f"No encounters CSVs found in {interim_dir} - run "
            f"`extract-encounters` first."
        )

    counts: dict[str, dict] = {}
    for f in files:
        log.info("scanning %s", f.name)
        for chunk in pd.read_csv(
            f,
            usecols=["period_tag", "responsible_site"],
            dtype=str,
            chunksize=200_000,
            keep_default_na=False,
        ):
            chunk["responsible_site"] = chunk["responsible_site"].str.strip().str.upper()
            grouped = chunk.groupby(["responsible_site", "period_tag"]).size()
            for (site, tag), n in grouped.items():
                rec = counts.setdefault(site, {"n_events": 0, "tags": set()})
                rec["n_events"] += int(n)
                rec["tags"].add(tag)

    rows = []
    for site, rec in counts.items():
        if not site:
            continue
        rows.append(
            {
                "responsible_site": site,
                "n_events": rec["n_events"],
                "period_tags": "|".join(sorted(rec["tags"])),
            }
        )
    out = pd.DataFrame(rows).sort_values("n_events", ascending=False).reset_index(drop=True)
    log.info("found %d unique encounter sites", len(out))
    return out


def build_site_crosswalk(
    interim_dir: Path = config.INTERIM_DIR,
    fips_csv: Path | None = None,
    overrides_csv: Path | None = None,
    out_dir: Path = config.PROCESSED_DIR,
    refs_dir: Path = config.REFERENCES_DIR,
) -> dict:
    if fips_csv is None:
        candidates = sorted(refs_dir.glob("fips*state*.csv")) + sorted(
            refs_dir.glob("fips*.csv")
        )
        if not candidates:
            raise FileNotFoundError(
                f"No FIPS reference CSV found under {refs_dir}."
            )
        fips_csv = candidates[0]
    if overrides_csv is None:
        overrides_csv = refs_dir / SITE_OVERRIDES_FILENAME

    fips_df = _load_state_lookup(fips_csv)
    overrides = _load_overrides(overrides_csv)
    sites = _unique_sites(interim_dir)

    parsed = sites["responsible_site"].apply(parse_site).apply(pd.Series)
    sites["city_auto"] = parsed["city"]
    sites["state_abbr_auto"] = parsed["state"]
    sites["suffix_auto"] = parsed["suffix"]

    flags = sites.apply(
        lambda r: classify_unusual(
            r["suffix_auto"] or r["responsible_site"], code=None
        ),
        axis=1,
        result_type="expand",
    )
    sites[["unusual_flag_auto", "unusual_type_auto"]] = flags

    if not overrides.empty:
        sites = sites.merge(overrides, on="responsible_site", how="left")
    for col in SITE_OVERRIDE_COLUMNS:
        if col == "responsible_site":
            continue
        if col not in sites.columns:
            sites[col] = ""
        else:
            sites[col] = sites[col].fillna("").astype(str).str.strip()

    sites["state_abbr"] = sites.apply(
        lambda r: r["state_abbr"] if r["state_abbr"] else r["state_abbr_auto"],
        axis=1,
    )
    sites["unusual_flag"] = sites.apply(
        lambda r: (r["unusual_flag"].lower() in {"true", "1", "yes"})
        or bool(r["unusual_flag_auto"]),
        axis=1,
    )
    sites["unusual_type"] = sites.apply(
        lambda r: r["unusual_type"] if r["unusual_type"] else r["unusual_type_auto"],
        axis=1,
    )
    sites["county_fips"] = sites["county_fips"].apply(lambda x: x.zfill(5) if x else "")

    auto_county = sites["city_auto"].apply(
        lambda c: lookup_city_county(c) if c else None
    )
    sites["state_auto_kf"] = auto_county.map(
        lambda h: h[0] if h else ""
    )
    sites["county_name_auto_kf"] = auto_county.map(
        lambda h: h[1] if h else ""
    )
    sites["state_abbr_auto"] = sites.apply(
        lambda r: r["state_abbr_auto"] if r["state_abbr_auto"] else r["state_auto_kf"],
        axis=1,
    )
    sites["state_abbr"] = sites.apply(
        lambda r: r["state_abbr"] if r["state_abbr"] else r["state_abbr_auto"],
        axis=1,
    )

    # Remembered before resolution overwrites the columns.
    sites["_origin_override_county"] = (
        (sites["county_fips"] != "")
        | (sites["county_name"].astype(str).str.strip() != "")
    )

    fips_lookup = fips_df[["county_fips", "county_name", "state_name", "state_abbr"]].copy()
    fips_lookup["county_name_norm"] = fips_lookup["county_name"].apply(norm_county)
    fips_lookup["county_name_compact"] = fips_lookup["county_name"].apply(norm_compact)

    # "{X} COUNTY ..." resolves ONLY when X is in exactly one state. No guessing.
    _norm_counts = fips_lookup.groupby("county_name_norm").size()
    _unique_norms = set(_norm_counts[_norm_counts == 1].index)
    unique_county_idx = {
        r["county_name_norm"]: r
        for _, r in fips_lookup.iterrows()
        if r["county_name_norm"] in _unique_norms
    }

    def _lookup(state: str, county: str) -> pd.Series | None:
        if not (state and county):
            return None
        sa = state.upper()
        cn = norm_county(county)
        cnc = norm_compact(county)
        same_state = fips_lookup[fips_lookup["state_abbr"] == sa]
        if same_state.empty:
            return None
        m = same_state[same_state["county_name_norm"] == cn]
        if m.empty:
            m = same_state[same_state["county_name_compact"] == cnc]
        if m.empty:
            m = same_state[same_state["county_name_norm"].apply(
                lambda c: cn.startswith(c) and len(c) >= 5
            )]
        if m.empty:
            m = same_state[same_state["county_name_compact"].apply(
                lambda c: cnc.startswith(c) and len(c) >= 5
            )]
        if not m.empty:
            r = m.iloc[0]
            return pd.Series([r["county_fips"], r["county_name"], r["state_name"], r["state_abbr"]])
        return None

    def _resolve(row):
        cf = row["county_fips"]
        if cf:
            match = fips_lookup[fips_lookup["county_fips"] == cf]
            if not match.empty:
                m = match.iloc[0]
                return pd.Series([cf, m["county_name"], m["state_name"], m["state_abbr"], ""])
        result = _lookup(row["state_abbr"], row["county_name"])
        if result is not None:
            return pd.Series([*result.tolist(), ""])
        result = _lookup(row["state_auto_kf"], row["county_name_auto_kf"])
        if result is not None:
            return pd.Series([*result.tolist(), ""])
        tok = county_token_from_name(row["responsible_site"])
        # County token + a state ALSO explicitly present in the source string
        # (parsed into state_abbr/_auto). Both facts are literally in the data.
        if tok:
            st = row["state_abbr"] or row["state_auto_kf"]
            if st:
                r2 = _lookup(st, tok)
                if r2 is not None:
                    return pd.Series([*r2.tolist(), "auto:county_in_named_state"])
        if tok and tok in unique_county_idx:
            m = unique_county_idx[tok]
            return pd.Series([
                m["county_fips"], m["county_name"], m["state_name"],
                m["state_abbr"], "auto:county_name_in_fips",
            ])
        sa = (row["state_abbr"] or row["state_auto_kf"]).upper()
        if sa:
            sn = fips_lookup.loc[fips_lookup["state_abbr"] == sa, "state_name"]
            if not sn.empty:
                return pd.Series(["", "", sn.iloc[0], sa, ""])
        return pd.Series(["", "", "", sa, ""])

    resolved = sites.apply(_resolve, axis=1)
    resolved.columns = [
        "county_fips", "county_name", "state_name", "state_abbr",
        "_resolve_src_hint",
    ]
    sites[
        ["county_fips", "county_name", "state_name", "state_abbr",
         "_resolve_src_hint"]
    ] = resolved

    def _source(row):
        if row["county_fips"]:
            if row["_origin_override_county"]:
                return "override"
            if row["_resolve_src_hint"]:
                return row["_resolve_src_hint"]
            if row["county_name_auto_kf"]:
                return "auto:city"
            return "auto"
        if row["state_abbr"]:
            if row["state_abbr_auto"] and row["state_abbr_auto"] == row["state_abbr"]:
                return "auto:site_string"
            return "override"
        return "unknown"

    sites["resolution_source"] = sites.apply(_source, axis=1)

    out_dir.mkdir(parents=True, exist_ok=True)
    cw_cols = [
        "responsible_site",
        "city_auto", "suffix_auto",
        "state_abbr", "state_name",
        "county_fips", "county_name",
        "unusual_flag", "unusual_type",
        "n_events", "period_tags",
        "state_abbr_auto", "unusual_type_auto",
        "resolution_source", "notes",
    ]
    cw = sites[cw_cols].copy().sort_values("n_events", ascending=False).reset_index(drop=True)
    cw_path = out_dir / SITE_CROSSWALK_FILENAME
    cw.to_csv(cw_path, index=False)
    log.info("wrote %s (%d rows)", cw_path.name, len(cw))

    needs_review = cw[
        (cw["county_fips"].astype(str).str.strip() == "")
        | (cw["unusual_flag"] == True)  # noqa: E712
        | (cw["resolution_source"] == "unknown")
    ].copy()
    review_path = out_dir / SITE_REVIEW_FILENAME
    needs_review.to_csv(review_path, index=False)

    template_path = refs_dir / SITE_OVERRIDES_TEMPLATE_FILENAME
    template = pd.DataFrame({
        "responsible_site": sites["responsible_site"],
        "state_abbr": sites["state_abbr_auto"],
        "county_fips": "",
        "county_name": "",
        "unusual_flag": sites["unusual_flag_auto"].map(lambda v: "TRUE" if v else ""),
        "unusual_type": sites["unusual_type_auto"],
        "notes": "",
    })
    template = template.sort_values("responsible_site").reset_index(drop=True)
    template.to_csv(template_path, index=False)

    return {
        "n_sites": len(cw),
        "n_with_county": int((cw["county_fips"].astype(str).str.len() > 0).sum()),
        "n_unusual": int(cw["unusual_flag"].sum()),
        "n_needs_review": len(needs_review),
        "crosswalk_path": str(cw_path),
        "review_path": str(review_path),
        "template_path": str(template_path),
    }


def _load_site_crosswalk(path: Path) -> pd.DataFrame:
    cw = pd.read_csv(path, dtype=str).fillna("")
    cw["responsible_site"] = cw["responsible_site"].str.strip().str.upper()
    cw["unusual_flag"] = cw["unusual_flag"].str.lower().isin({"true", "1", "yes"})
    return cw


def _aggregate_one(csv_path: Path, cw: pd.DataFrame):
    year_parts: list[pd.DataFrame] = []
    month_parts: list[pd.DataFrame] = []
    unmapped_parts: list[pd.DataFrame] = []

    cols = config.ENCOUNTERS_EXTRACT_COLUMNS
    dtypes = {c: str for c in cols}
    dtypes["period_tag"] = str

    for chunk in pd.read_csv(
        csv_path,
        usecols=cols,
        dtype=dtypes,
        chunksize=200_000,
        keep_default_na=False,
    ):
        chunk["responsible_site"] = chunk["responsible_site"].str.strip().str.upper()
        merged = chunk.merge(
            cw[["responsible_site", "county_fips", "county_name",
                "state_abbr", "state_name", "unusual_flag", "unusual_type"]],
            on="responsible_site",
            how="left",
        )
        merged["event_dt"] = pd.to_datetime(merged["event_date"], errors="coerce")

        unmapped_mask = merged["county_fips"].fillna("").astype(str).str.strip() == ""
        if unmapped_mask.any():
            u = merged.loc[unmapped_mask].groupby(
                ["responsible_site", "unusual_flag", "unusual_type"],
                dropna=False,
            ).agg(
                n_events=("person_id", "size"),
                n_unique_persons=("person_id", "nunique"),
            ).reset_index()
            unmapped_parts.append(u)

        mapped = merged.loc[~unmapped_mask].copy()
        if mapped.empty:
            continue
        mapped["year"] = mapped["event_dt"].dt.year.astype("Int64")
        mapped["year_month"] = mapped["event_dt"].dt.strftime("%Y-%m")

        year_parts.append(
            mapped.groupby(
                ["county_fips", "county_name", "state_abbr", "state_name",
                 "period_tag", "year"],
                dropna=False,
            ).agg(
                n_events=("person_id", "size"),
                n_unique_persons=("person_id", "nunique"),
                n_unusual_events=("unusual_flag", "sum"),
            ).reset_index()
        )
        month_parts.append(
            mapped.groupby(
                ["county_fips", "county_name", "state_abbr", "state_name",
                 "period_tag", "year_month"],
                dropna=False,
            ).agg(
                n_events=("person_id", "size"),
                n_unique_persons=("person_id", "nunique"),
                n_unusual_events=("unusual_flag", "sum"),
            ).reset_index()
        )

    return (
        pd.concat(year_parts, ignore_index=True) if year_parts else pd.DataFrame(),
        pd.concat(month_parts, ignore_index=True) if month_parts else pd.DataFrame(),
        pd.concat(unmapped_parts, ignore_index=True) if unmapped_parts else pd.DataFrame(),
    )


def _final_rollup(parts: list[pd.DataFrame], group_cols: list[str]) -> pd.DataFrame:
    if not parts:
        return pd.DataFrame()
    df = pd.concat(parts, ignore_index=True)
    if df.empty:
        return df
    return df.groupby(group_cols, dropna=False).agg(
        n_events=("n_events", "sum"),
        n_unique_persons=("n_unique_persons", "sum"),
        n_unusual_events=("n_unusual_events", "sum"),
    ).reset_index()


def aggregate(
    interim_dir: Path = config.INTERIM_DIR,
    crosswalk_csv: Path | None = None,
    out_dir: Path = config.PROCESSED_DIR,
) -> dict:
    if crosswalk_csv is None:
        crosswalk_csv = out_dir / SITE_CROSSWALK_FILENAME
    if not crosswalk_csv.exists():
        raise FileNotFoundError(
            f"{crosswalk_csv} not found - run `crosswalk-encounters` first."
        )

    cw = _load_site_crosswalk(crosswalk_csv)
    files = sorted(interim_dir.glob("encounters_*.csv*"))
    if not files:
        raise FileNotFoundError(
            f"No encounters CSVs in {interim_dir}; run `extract-encounters` first."
        )

    all_year, all_month, all_unmapped = [], [], []
    for f in files:
        log.info("aggregating %s", f.name)
        yp, mp, up = _aggregate_one(f, cw)
        if not yp.empty:
            all_year.append(yp)
        if not mp.empty:
            all_month.append(mp)
        if not up.empty:
            all_unmapped.append(up)

    out_dir.mkdir(parents=True, exist_ok=True)
    year_panel = _final_rollup(
        all_year,
        ["county_fips", "county_name", "state_abbr", "state_name",
         "period_tag", "year"],
    )
    month_panel = _final_rollup(
        all_month,
        ["county_fips", "county_name", "state_abbr", "state_name",
         "period_tag", "year_month"],
    )

    if not year_panel.empty:
        year_panel = year_panel.sort_values(
            ["state_abbr", "county_name", "year"]
        ).reset_index(drop=True)
        year_panel.to_csv(out_dir / ENC_YEAR_PANEL_FILENAME, index=False)
    if not month_panel.empty:
        month_panel = month_panel.sort_values(
            ["state_abbr", "county_name", "year_month"]
        ).reset_index(drop=True)
        month_panel.to_csv(out_dir / ENC_MONTH_PANEL_FILENAME, index=False)

    if all_unmapped:
        unmapped = pd.concat(all_unmapped, ignore_index=True)
        unmapped = unmapped.groupby(
            ["responsible_site", "unusual_flag", "unusual_type"],
            dropna=False,
        ).agg(
            n_events=("n_events", "sum"),
            n_unique_persons=("n_unique_persons", "sum"),
        ).reset_index().sort_values("n_events", ascending=False)
        unmapped.to_csv(out_dir / ENC_UNMAPPED_FILENAME, index=False)
    else:
        unmapped = pd.DataFrame()

    return {
        "year_panel_rows": len(year_panel),
        "month_panel_rows": len(month_panel),
        "unmapped_rows": len(unmapped),
        "year_panel_path": str(out_dir / ENC_YEAR_PANEL_FILENAME),
        "month_panel_path": str(out_dir / ENC_MONTH_PANEL_FILENAME),
        "unmapped_path": str(out_dir / ENC_UNMAPPED_FILENAME),
    }
