"""Rebuild references/fips_state_county.csv from Census 2020 authoritative file.

Source: https://www2.census.gov/geo/docs/reference/codes2020/national_county2020.txt
(Census Bureau, downloaded fresh; canonical 5-digit FIPS + full county names.)

Preserves the existing CSV schema (fips, county_name, state_name) so the rest
of the pipeline keeps working. Fixes the truncated names we found
(Matanuska-Susitn, Aleutians East B, etc.) and ensures all US states +
territories (PR/GU/VI/MP/AS) are included.
"""
from __future__ import annotations

import csv
from pathlib import Path

SRC = Path("references/_census_national_county2020.txt")
DST = Path("references/fips_state_county.csv")

STATE_NAMES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut",
    "DE": "Delaware", "DC": "District of Columbia", "FL": "Florida",
    "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho", "IL": "Illinois",
    "IN": "Indiana", "IA": "Iowa", "KS": "Kansas", "KY": "Kentucky",
    "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota",
    "MS": "Mississippi", "MO": "Missouri", "MT": "Montana",
    "NE": "Nebraska", "NV": "Nevada", "NH": "New Hampshire",
    "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio",
    "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania",
    "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota",
    "TN": "Tennessee", "TX": "Texas", "UT": "Utah", "VT": "Vermont",
    "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming",
    "PR": "Puerto Rico", "GU": "Guam",
    "VI": "U.S. Virgin Islands", "MP": "Northern Mariana Islands",
    "AS": "American Samoa",
}


def main() -> None:
    rows = []
    with SRC.open(encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="|")
        for r in reader:
            state_abbr = r["STATE"]
            state_fp = r["STATEFP"]
            county_fp = r["COUNTYFP"]
            name = r["COUNTYNAME"]
            fips = f"{state_fp}{county_fp}"
            if len(fips) != 5:
                continue
            state_name = STATE_NAMES.get(state_abbr, state_abbr)
            rows.append((fips, name, state_name))

    rows.sort()
    with DST.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["fips", "county_name", "state_name"])
        w.writerows(rows)
    print(f"wrote {DST} ({len(rows)} rows)")

    keys = {
        "02170": "Matanuska-Susitna",
        "02020": "Anchorage",
        "01077": "Lauderdale",
        "51550": "Chesapeake",
        "72127": "San Juan",
        "72031": "Carolina",
        "72061": "Guaynabo",
        "66010": "Guam",
        "78030": "St. Thomas",
        "69110": "Saipan",
    }
    by_fips = {r[0]: r[1] for r in rows}
    for f, expect in keys.items():
        actual = by_fips.get(f, "MISSING")
        ok = expect.lower() in actual.lower()
        flag = "OK" if ok else "MISS"
        print(f"  [{flag}] {f}: {actual!r} (expected to contain {expect!r})")


if __name__ == "__main__":
    main()
