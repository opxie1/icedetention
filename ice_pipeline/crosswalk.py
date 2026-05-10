"""Build the detention facility -> county crosswalk."""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from . import config
from .known_facilities import norm_compact, norm_county, resolve_facility
from .patterns import classify_unusual, guess_state

log = logging.getLogger(__name__)

OVERRIDES_FILENAME = "facility_overrides.csv"
OVERRIDES_TEMPLATE_FILENAME = "facility_overrides_template.csv"

CROSSWALK_FILENAME = "facility_crosswalk.csv"
REVIEW_FILENAME = "facility_crosswalk_review.csv"

OVERRIDE_COLUMNS = [
    "facility_name",
    "facility_code",
    "state_abbr",
    "county_fips",
    "county_name",
    "unusual_flag",
    "unusual_type",
    "notes",
]


def _load_state_lookup(fips_csv: Path) -> tuple[pd.DataFrame, dict[str, str]]:
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
    return fips, state_abbr_map


def _load_overrides(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=OVERRIDE_COLUMNS)
    df = pd.read_csv(path, dtype=str).fillna("")
    missing = [c for c in OVERRIDE_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(
            f"{path.name} is missing required columns: {missing}. "
            f"Expected: {OVERRIDE_COLUMNS}"
        )
    df["facility_name"] = df["facility_name"].str.strip().str.upper()
    df["facility_code"] = df["facility_code"].str.strip().str.upper()
    df["state_abbr"] = df["state_abbr"].str.strip().str.upper()
    cf = df["county_fips"].str.strip()
    df["county_fips"] = cf.apply(lambda x: x.zfill(5) if x else "")
    df["county_name"] = df["county_name"].str.strip()
    return df


def _unique_facilities(interim_dir: Path) -> pd.DataFrame:
    files = sorted(interim_dir.glob("fy*_detentions.csv*"))
    if not files:
        raise FileNotFoundError(
            f"No per-FY extract CSVs found in {interim_dir} - run `extract` first."
        )

    counts: dict[tuple[str, str], dict] = {}
    for f in files:
        log.info("scanning %s", f.name)
        usecols = ["fiscal_year", "facility_name", "facility_code"]
        for chunk in pd.read_csv(
            f,
            usecols=usecols,
            dtype={"fiscal_year": "int32", "facility_name": str, "facility_code": str},
            chunksize=200_000,
            keep_default_na=False,
        ):
            chunk["facility_name"] = chunk["facility_name"].str.strip().str.upper()
            chunk["facility_code"] = chunk["facility_code"].str.strip().str.upper()
            grouped = chunk.groupby(
                ["facility_name", "facility_code", "fiscal_year"], dropna=False
            ).size()
            for (name, code, fy), n in grouped.items():
                key = (name, code)
                rec = counts.setdefault(
                    key, {"n_episodes": 0, "fiscal_years": set()}
                )
                rec["n_episodes"] += int(n)
                rec["fiscal_years"].add(int(fy))

    rows = []
    for (name, code), rec in counts.items():
        if not name and not code:
            continue
        years = sorted(rec["fiscal_years"])
        rows.append(
            {
                "facility_name": name,
                "facility_code": code,
                "n_episodes": rec["n_episodes"],
                "n_fiscal_years": len(years),
                "first_fy": years[0] if years else "",
                "last_fy": years[-1] if years else "",
            }
        )
    out = pd.DataFrame(rows).sort_values(
        ["n_episodes"], ascending=False
    ).reset_index(drop=True)
    log.info("found %d unique facility keys", len(out))
    return out


def build_crosswalk(
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
                f"No FIPS reference CSV found under {refs_dir}. "
                f"Place the file there as 'fips_state_county.csv' or pass --fips-csv."
            )
        fips_csv = candidates[0]
    if overrides_csv is None:
        overrides_csv = refs_dir / OVERRIDES_FILENAME

    fips_df, _ = _load_state_lookup(fips_csv)
    overrides = _load_overrides(overrides_csv)

    facilities = _unique_facilities(interim_dir)

    guesses = facilities.apply(
        lambda r: guess_state(r["facility_name"], r["facility_code"]), axis=1
    )
    facilities["state_abbr_auto"] = guesses.map(lambda g: g.state_abbr)
    facilities["state_source_auto"] = guesses.map(lambda g: g.source)

    flags = facilities.apply(
        lambda r: classify_unusual(r["facility_name"], r["facility_code"]),
        axis=1,
        result_type="expand",
    )
    facilities[["unusual_flag_auto", "unusual_type_auto"]] = flags

    auto_hits = facilities.apply(
        lambda r: resolve_facility(r["facility_name"], r["facility_code"]), axis=1
    )
    facilities["state_auto_kf"] = auto_hits.map(
        lambda h: h.state_abbr if h is not None else ""
    )
    facilities["county_name_auto_kf"] = auto_hits.map(
        lambda h: h.county_name if h is not None else ""
    )
    facilities["county_source_auto_kf"] = auto_hits.map(
        lambda h: h.source if h is not None else ""
    )
    facilities["state_abbr_auto"] = facilities.apply(
        lambda r: r["state_abbr_auto"] if r["state_abbr_auto"] else r["state_auto_kf"],
        axis=1,
    )

    if not overrides.empty:
        facilities = facilities.merge(
            overrides,
            on=["facility_name", "facility_code"],
            how="left",
            suffixes=("", "_override"),
        )

    for col in OVERRIDE_COLUMNS:
        if col in ("facility_name", "facility_code"):
            continue
        if col not in facilities.columns:
            facilities[col] = ""
        else:
            facilities[col] = facilities[col].fillna("").astype(str).str.strip()

    facilities["state_abbr"] = facilities.apply(
        lambda r: r["state_abbr"] if r["state_abbr"] else r["state_abbr_auto"],
        axis=1,
    )
    facilities["unusual_flag"] = facilities.apply(
        lambda r: (r["unusual_flag"].lower() in {"true", "1", "yes"})
        or bool(r["unusual_flag_auto"]),
        axis=1,
    )
    facilities["unusual_type"] = facilities.apply(
        lambda r: r["unusual_type"] if r["unusual_type"] else r["unusual_type_auto"],
        axis=1,
    )
    facilities["county_fips"] = facilities["county_fips"].str.zfill(5).where(
        facilities["county_fips"] != "", ""
    )

    # Remembered before resolution overwrites the columns.
    facilities["_origin_override_county"] = (
        (facilities["county_fips"] != "")
        | (facilities["county_name"].astype(str).str.strip() != "")
    )

    fips_lookup = fips_df[["county_fips", "county_name", "state_name", "state_abbr"]].copy()
    fips_lookup["county_name_lc"] = fips_lookup["county_name"].str.lower()
    fips_lookup["county_name_norm"] = fips_lookup["county_name"].apply(norm_county)
    fips_lookup["county_name_compact"] = fips_lookup["county_name"].apply(norm_compact)

    def _lookup_fips(state: str, county: str) -> pd.Series | None:
        if not (state and county):
            return None
        sa = state.upper()
        cn = norm_county(county)
        cnc = norm_compact(county)
        same_state = fips_lookup[fips_lookup["state_abbr"] == sa]
        if same_state.empty:
            return None
        match = same_state[same_state["county_name_norm"] == cn]
        if match.empty:
            match = same_state[same_state["county_name_compact"] == cnc]
        if match.empty:
            match = same_state[
                same_state["county_name_norm"].apply(
                    lambda c: cn.startswith(c) and len(c) >= 5
                )
            ]
        if match.empty:
            match = same_state[
                same_state["county_name_compact"].apply(
                    lambda c: cnc.startswith(c) and len(c) >= 5
                )
            ]
        if not match.empty:
            m = match.iloc[0]
            return pd.Series(
                [m["county_fips"], m["county_name"], m["state_name"], m["state_abbr"]]
            )
        return None

    def _resolve_county(row):
        cf = row["county_fips"]
        if cf:
            cf = cf.zfill(5)
            match = fips_lookup[fips_lookup["county_fips"] == cf]
            if not match.empty:
                m = match.iloc[0]
                return pd.Series(
                    [cf, m["county_name"], m["state_name"], m["state_abbr"]]
                )
        result = _lookup_fips(row["state_abbr"], row["county_name"])
        if result is not None:
            return result
        result = _lookup_fips(row["state_auto_kf"], row["county_name_auto_kf"])
        if result is not None:
            return result
        sa = (row["state_abbr"] or row["state_auto_kf"]).upper()
        if sa:
            sn = fips_lookup.loc[fips_lookup["state_abbr"] == sa, "state_name"]
            if not sn.empty:
                return pd.Series(["", "", sn.iloc[0], sa])
        return pd.Series(["", "", "", sa])

    resolved = facilities.apply(_resolve_county, axis=1)
    resolved.columns = ["county_fips", "county_name", "state_name", "state_abbr"]
    facilities[["county_fips", "county_name", "state_name", "state_abbr"]] = resolved

    def _source(row):
        if row["county_fips"]:
            if row["_origin_override_county"]:
                return "override"
            if row["county_source_auto_kf"]:
                return f"auto:{row['county_source_auto_kf']}"
            return "auto"
        sa = row["state_abbr"]
        if sa:
            if row["state_abbr_auto"] and row["state_abbr_auto"] == sa:
                src = row["state_source_auto"] or "auto"
                return f"auto:{src}"
            return "override"
        return "unknown"

    facilities["state_abbr"] = facilities["state_abbr"].fillna("").astype(str)
    facilities["state_abbr_auto"] = facilities["state_abbr_auto"].fillna("").astype(str)
    facilities["state_source_auto"] = facilities["state_source_auto"].fillna("").astype(str)
    facilities["county_fips"] = facilities["county_fips"].fillna("").astype(str)
    facilities["resolution_source"] = facilities.apply(_source, axis=1)

    crosswalk_cols = [
        "facility_name", "facility_code",
        "state_abbr", "state_name",
        "county_fips", "county_name",
        "unusual_flag", "unusual_type",
        "n_episodes", "n_fiscal_years", "first_fy", "last_fy",
        "state_abbr_auto", "state_source_auto",
        "unusual_type_auto",
        "resolution_source", "notes",
    ]
    cw = facilities[crosswalk_cols].copy()
    cw = cw.sort_values(["n_episodes"], ascending=False).reset_index(drop=True)

    out_dir.mkdir(parents=True, exist_ok=True)
    cw_path = out_dir / CROSSWALK_FILENAME
    cw.to_csv(cw_path, index=False)
    log.info("wrote %s (%d rows)", cw_path.name, len(cw))

    needs_review = cw[
        (cw["county_fips"].astype(str).str.strip() == "")
        | (cw["unusual_flag"] == True)  # noqa: E712
        | (cw["resolution_source"] == "unknown")
    ].copy()
    review_path = out_dir / REVIEW_FILENAME
    needs_review.to_csv(review_path, index=False)
    log.info("wrote %s (%d rows need review)", review_path.name, len(needs_review))

    template_path = refs_dir / OVERRIDES_TEMPLATE_FILENAME
    template = facilities[["facility_name", "facility_code"]].copy()
    template["state_abbr"] = facilities["state_abbr_auto"]
    template["county_fips"] = ""
    template["county_name"] = ""
    template["unusual_flag"] = facilities["unusual_flag_auto"].map(
        lambda v: "TRUE" if v else ""
    )
    template["unusual_type"] = facilities["unusual_type_auto"]
    template["notes"] = ""
    template = template.sort_values(["facility_name", "facility_code"]).reset_index(
        drop=True
    )
    template.to_csv(template_path, index=False)
    log.info("wrote %s (%d rows)", template_path.name, len(template))

    return {
        "n_facilities": len(cw),
        "n_with_county": int((cw["county_fips"].astype(str).str.len() > 0).sum()),
        "n_unusual": int(cw["unusual_flag"].sum()),
        "n_needs_review": len(needs_review),
        "crosswalk_path": str(cw_path),
        "review_path": str(review_path),
        "template_path": str(template_path),
    }
