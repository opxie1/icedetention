"""Append authoritative U.S. Census Bureau territory FIPS rows.

Source: U.S. Census Bureau, 2020 FIPS/ANSI county-equivalent code files
  https://www2.census.gov/geo/docs/reference/codes2020/cou/st72_pr_cou2020.txt
  https://www2.census.gov/geo/docs/reference/codes2020/cou/st66_gu_cou2020.txt
  https://www2.census.gov/geo/docs/reference/codes2020/cou/st78_vi_cou2020.txt
  https://www2.census.gov/geo/docs/reference/codes2020/cou/st69_mp_cou2020.txt
Retrieved 2026-05-17. Only the county-equivalents that appear in the FOIA
data are added.
"""

import pathlib

ROWS = [
    "72005,Aguadilla Municipio,Puerto Rico",
    "72021,Bayamon Municipio,Puerto Rico",
    "72031,Carolina Municipio,Puerto Rico",
    "72061,Guaynabo Municipio,Puerto Rico",
    "72127,San Juan Municipio,Puerto Rico",
    "66010,Guam,Guam",
    "78030,St. Thomas Island,U.S. Virgin Islands",
    "69110,Saipan Municipality,Northern Mariana Islands",
]

p = pathlib.Path("references/fips_state_county.csv")
txt = p.read_text(encoding="utf-8")
existing = {ln.split(",")[0] for ln in txt.splitlines()[1:] if ln.strip()}
add = [r for r in ROWS if r.split(",")[0] not in existing]
if txt and not txt.endswith("\n"):
    txt += "\n"
txt += "\n".join(add) + ("\n" if add else "")
p.write_text(txt, encoding="utf-8")
total = len([ln for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()])
print(f"appended {len(add)} rows; file now has {total} non-empty lines")
