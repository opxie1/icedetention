# ICE Detention and Encounters Data Pipeline

This repository holds the data pipeline I built as a research assistant for
Professor Catalina Amuedo-Dorantes (UC Merced) and Professor Eduardo
Polo-Muro (San Diego State University). Their project studies immigration
courts and case outcomes. My job is to turn raw ICE records into
county-level datasets: I map each detention facility to its state and
county, flag unusual sites such as hotels, hospitals, and hold rooms, and
aggregate counts by county over time.

I am Ethan Xie (The Charter School of Wilmington, Delaware),
xief@udel.edu.

## The data

The pipeline handles three sources and combines two of them.

**Detentions (FOIA).** Twelve workbooks
(`2023-ICFO_42034_Detentions_FY12..FY23_*.xlsx`), one per fiscal year,
each with the same 33-column layout. Book-ins run January 2012 through
November 2023. One row is one booking into a facility.

**Encounters (FOIA).** One workbook
(`2025-ICLI-00019_2024-ICFO-39357_ERO Encounters_*.xlsx`) covering
September 2023 through July 2025. One row is one enforcement event
(detainers, program events, and similar actions), located by a
"Responsible Site" field rather than a facility.

**Stays (Deportation Data Project).** A parquet file of custody stays,
used from December 2023 through March 2026. One row is one person's whole
custody period, which can span several facilities. This picks up where
the FOIA detention data ends, with no overlapping months.

**Combined panels.** `county_year_detention_combined.csv` and
`county_month_detention_combined.csv` stack the FOIA and stays data into
one series, 2012 through 2026. A `source` column marks which rows come
from which source, and `n_detained` gives one usable count across the
whole period.

**Population.** `scripts/build_population.py` pulls county population
(Census Population Estimates), Hispanic population (ACS table B03002),
and non-citizen population (ACS table B05001) for 2012 through 2026, and
merges them onto the detention panels with a per-100,000-residents rate.
A Census API key is required (stored in
`references/census_api_key.txt`, which git ignores).

## Repository layout

```
ice_pipeline/
  config.py            paths and the fixed FOIA column layouts
  patterns.py          unusual-facility regex and state-from-code rules
  extract.py           streams the xlsx files to slim CSVs
  crosswalk.py         facility -> state/county lookup builder
  aggregate.py         county x time roll-up for detentions
  encounters.py        site crosswalk and roll-up for encounters
  stays.py             county x time roll-up for the DDP stays parquet
  known_facilities.py  curated facility-to-county mappings
  cli.py               `python -m ice_pipeline.cli ...` entry point
references/
  fips_state_county.csv   Census 2020 county reference (full names)
  ddp_facilities.csv      Deportation Data Project facility list
  facility_overrides.csv  optional hand overrides (template auto-generated)
data/
  interim/     one slim CSV per source workbook
  processed/   crosswalks, panels, combined files, population files
scripts/
  build_combined.py     builds the 2012-2026 combined panels
  build_population.py   builds and merges the Census population data
  sync_dropbox.py       mirrors deliverables into the shared Dropbox folder
  master_check.py       48 assertions covering every professor request
  thorough_verify.py    older end-to-end check, still runs
analysis/task1_spikes/  spike maps task: input, adapted R script, figures
```

## Setup

Python 3.11 or newer. From the project root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

`setup.ps1` runs those steps for you. Start every later session with the
`Activate.ps1` line.

## Running the pipeline

Each track has extract, crosswalk, and aggregate steps, plus a shortcut
that chains them.

```powershell
python -m ice_pipeline.cli all --input-dir "<folder with the FOIA xlsx files>"
python -m ice_pipeline.cli all-encounters --input-dir "<same folder>"
python -m ice_pipeline.cli aggregate-stays --parquet "<detention-stays parquet>"
python -m ice_pipeline.cli everything --input-dir "<folder>"
```

Then the combined and population builds:

```powershell
python scripts/build_combined.py
python scripts/build_population.py
```

Already-extracted workbooks are skipped on rerun unless you pass
`--force`. Use `--only 2015 2016` to limit an extract run.

### Filling in counties by hand

The crosswalk step writes `references/facility_overrides_template.csv`.
Save a copy as `facility_overrides.csv`, fill in `county_fips` (or
`state_abbr` plus `county_name`) for any facility you recognize, and
rerun the crosswalk. Override values beat the automatic ones. The
encounters track works the same way through `site_overrides.csv`.

### How counties get assigned

The crosswalk tries, in order: hand overrides, the Deportation Data
Project facility list, the curated mappings in `known_facilities.py`, a
county name found inside the facility name, a city keyword, and last a
state-only guess. Per Professor Amuedo-Dorantes, the two facilities at
the San Juan airport go to San Juan rather than Carolina.

## Limits worth knowing

`n_unique_persons` is approximate in the FOIA panels because aggregation
runs in 200,000-row chunks; a person spanning chunks counts more than
once. Use `n_episodes` for exact counts.

The pipeline does not geocode addresses. Facilities the rules cannot
place stay blank and appear in the review files for the team to fill in.

Average daily population is not computed. The panels carry total
detention days per period, and ADP is that number divided by days in the
period.

November 2023 is a partial month in the FOIA data, and the FOIA-to-stays
handoff in December 2023 changes the unit of count from bookings to
stays. Both facts are documented in the Dropbox README and flagged to
the professors.

## Latest full run (July 2026)

Detentions: 1,099 of 1,141 facilities resolved (96.3 percent), covering
99.96 percent of 8,458,563 episodes. County-year panel 4,065 rows,
county-month 37,302, unmapped facilities 42.

Stays: 749,142 of 750,531 stays mapped (99.8 percent). County-year
panel 1,078 rows, county-month 6,042.

Encounters: 306 of 413 sites resolved, 984,451 of 1,360,318 events.
County-year panel 747 rows, county-month 4,128, unmapped sites 107.

Combined: 4,974 county-year rows and 43,344 county-month rows, January
2012 through March 2026, no duplicate county-period keys.

Population: 48,465 county-year rows; 99.12 percent of detention rows
matched, the rest being island territories with no annual Census
population source.

`python scripts/master_check.py` reruns the 48-assertion verification
behind these numbers.
