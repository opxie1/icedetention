# ICE detention and encounters county-level panels — methodology

Prepared for Prof. Catalina Amuedo-Dorantes and Prof. Eduardo Polo-Muro
by Ethan Xie (xief@udel.edu).

This folder contains seven panel files and four supporting crosswalk
files. They are built from three independent FOIA / public-data sources.
Each file's source, unit of analysis, and time coverage are documented
below. **The two detention panels are NOT additive across the FY2023
boundary** — read the "How to combine" section before splicing.

---

## Files at a glance

| File | Unit | Time | Source |
|---|---|---|---|
| `county_year_panel.csv` | detention episode (book-in event) | FY2012 – FY2023 | 12 ICE FOIA detention workbooks (`2023-ICFO-42034_..._FY12..FY23`) |
| `county_month_panel.csv` | detention episode | FY2012 – FY2023 (year-month) | same |
| `county_year_encounters_panel.csv` | ERO encounter event | Sept 2023 – Jul 2025 | ERO Encounters workbook (`2025-ICLI-00019_2024-ICFO-39357_ERO Encounters`) |
| `county_month_encounters_panel.csv` | encounter event | Sept 2023 – Jul 2025 (year-month) | same |
| `county_year_stays_panel.csv` | **stay** (custody journey) | Dec 2023 – Mar 2026 | Deportation Data Project stays parquet |
| `county_month_stays_panel.csv` | stay | Dec 2023 – Mar 2026 (year-month) | same |
| `unmapped_stays.csv` | stay | Dec 2023 – Mar 2026 | same; stays for which DDP did not provide a county |

Supporting crosswalk files (in this folder):

| File | Description |
|---|---|
| `facility_crosswalk.csv` | every detention facility from the FOIA data with the county we assigned |
| `facility_crosswalk_review.csv` | the subset of the above that was unresolved or flagged "unusual" — sent for review |
| `site_crosswalk.csv` | every encounter "Responsible Site" with its assigned county |
| `site_crosswalk_review.csv` | subset of the above that was unresolved or flagged "unusual" |
| `unmapped_facilities.csv` | detention facilities our pipeline could not place in a county (`for review` folder has a friendlier version) |
| `unmapped_sites.csv` | encounter sites our pipeline could not place in a county (`for review` folder has a friendlier version) |

---

## 1. Detention panels (FY2012 – FY2023)

**Source.** Twelve ICE FOIA workbooks from `2023-ICFO-42034`, one per
fiscal year FY12 through FY23.

**Unit of analysis.** A detention *episode* is one row in the FOIA
workbooks — i.e. one book-in event for one person at one facility. A
single person can have multiple episodes; a single stay can span
multiple episodes if they were transferred. We count book-ins, not
people.

**Time coverage.** Book-in dates range from Oct 2011 through Sept 2023.
The `year` column is **calendar year of book-in**.

**Facility → county assignment.** Built in this order:
1. **Deportation Data Project** authoritative facility list
   (`https://ice-detention-facilities.apps.deportationdata.org/`) —
   covers 501 of our facilities. Used as the primary source per
   Prof. Amuedo-Dorantes' suggestion.
2. **Hardcoded mappings** for ICE facility codes not in DDP (mostly
   small hold rooms, hotels, and territory facilities).
3. **Deterministic county-name lookup** — if a facility name contains
   `"{X} COUNTY"` and `X` appears in exactly one state in the FIPS
   reference, we use that. Zero guessing.
4. **City keyword** lookup from a curated table of major ICE cities.
5. **State-only fallback** if nothing else works.

**Override.** Per Prof. Amuedo-Dorantes' instruction ("you can assign
the San Juan airport to San Juan"), both ICE facilities at the San Juan
airport — "San Juan Airport Hold Room" (`SJUHOLD`) and "Airport Hotel,
SAJ." (`AIRHOPR`) — are attributed to **San Juan Municipio (72127)**
rather than Carolina Municipio where the airport physically sits.

**Coverage.** 1,099 of 1,141 distinct facility codes resolved (96.3%);
8,455,175 of 8,458,563 episodes (99.96%). The 42 unresolved facilities
are listed in `facilities_need_county.csv` in the `for review` folder.

**Columns.**
- `county_fips` — 5-digit county FIPS
- `county_name`, `state_abbr`, `state_name`
- `fiscal_year` — federal fiscal year (the FOIA file the row came from)
- `year` or `year_month` — calendar year (or year-month) of book-in
- `n_episodes` — number of book-in events
- `n_unique_persons` — approximate unique persons (computed per chunk;
  see note below)
- `detention_days` — sum of (book-out − book-in) days for episodes that
  have both dates
- `n_unusual_episodes` — episodes flagged as occurring at "unusual"
  facilities (hold rooms, hotels, hospitals, staging facilities,
  juvenile facilities, etc. — see `facility_crosswalk.csv` for the
  `unusual_type` column)

**Note on `n_unique_persons`.** Computed within 200k-row chunks and
summed. If a person appears in more than one chunk or fiscal year they
are counted more than once. Use `n_episodes` for an exact book-in count.

---

## 2. Encounters panels (Sept 2023 – Jul 2025)

**Source.** ERO Encounters FOIA workbook
`2025-ICLI-00019_2024-ICFO-39357_ERO Encounters_LESA-STU_FINAL_Redacted_raw.xlsx`.

**Unit of analysis.** A *encounter event* — one row in the source file.
Encounters include detainers, prosecutorial-discretion events, program
events, and book-ins. **They are NOT the same thing as detention
episodes.** Filter on `event_type` / `final_program` / `final_program_group`
in the interim CSV if you want a strict detention-equivalent subset.

**Time coverage.** Event dates span Sept 2023 through Jul 2025. One
typo'd row reads `2115-01-21` and shows up in some date summaries; we
have not modified the source data.

**Site → county assignment.** Site strings of the form
`"CITY, STATE, SUFFIX"` are auto-parsed; other formats fall through to
the city / county-name / state-only fallbacks. 306 of 413 sites
resolved (74%); 984,451 of 1,360,318 events (72.4%). The single largest
unresolved site is `"ERO - PACIFIC ENFORCEMENT RESPONSE CENTER"`
(~336k events) — a national virtual processing center with no physical
county. It is excluded by design.

**Columns.** Same shape as the detention panels but `n_events` instead
of `n_episodes`, and `n_unusual_events` instead of
`n_unusual_episodes`. `period_tag` distinguishes the two source sheets
(`pre_20241001` vs `from_20241001`).

---

## 3. Stays panels (Dec 2023 – Mar 2026)

**Source.** Deportation Data Project detention-stays parquet
(`https://ice-detention-stays.apps.deportationdata.org/`), retrieved
2026-05-28. DDP processes the same underlying ICE FOIA stream into
"stays" rather than per-event episodes.

**Unit of analysis.** A *stay* is a complete custody journey, possibly
spanning multiple facilities (`n_stints` counts the number of distinct
facility bookings within a stay). On average **1.07 stays per person**
across the dataset; **a stay is NOT the same unit as an episode**.

**Time coverage.** We filter the raw parquet to stays where
`book_in_date_time_first >= 2023-12-01`. This **eliminates overlap with
the FOIA detention panels** so the two sources can be spliced cleanly
at the Dec 1, 2023 boundary. (The FY23 FOIA workbook actually contains
book-ins through Nov 2023, despite the "FY23" label — so the FY-based
cutoff is one month later than the federal-fiscal-year boundary.)

If you need stays from before Dec 2023, re-run with
`--cutoff-book-in ""` to include everything.

**County assignment.** Two-stage:

1. **DDP-provided geography.** DDP supplies pre-resolved
   `state_longest` and `county_longest` for each stay (the state and
   county where the person spent the most time during the stay). We
   look up the 5-digit FIPS by joining `(state, county_longest)`
   against the Census 2020 national county reference.
2. **Facility-code rescue.** For stays where DDP left `county_longest`
   blank (~44k stays after the Dec 2023 cutoff), we look up the stay's
   `detention_facility_code_longest` against the FOIA detention
   facility crosswalk built in step 1 of the detention panel. This
   recovers ~96.9% of the DDP-blank stays (≈42.8k) by reusing the
   county we already resolved for that facility through the FOIA
   pipeline (DDP → hardcoded → deterministic county-name → city
   keyword chain).

Final coverage: **749,142 of 750,531 stays mapped (99.82%)**. The
remaining 1,389 stays are listed in `unmapped_stays.csv`; they fall
into three buckets — (a) Guantanamo Bay (Cuba — `CU`, 101 stays, no
US county applies), (b) hold rooms with no resolvable facility county
(e.g. `SMAHOLD`, `NEWHOLD` — DDP blank, FOIA pipeline could not place
them either), and (c) a handful of state-only DDP rows with no
facility code we could match.

**Columns.**
- `county_fips`, `county_name`, `state_abbr`, `state_name`
- `year` or `year_month` of `book_in_date_time_first`
- `n_stays` — number of stays
- `n_unique_persons` — distinct `unique_identifier`s in that
  county-period
- `n_stints_total` — sum of `n_stints` across stays (≈ number of
  facility-level book-ins)
- `total_days` — sum of (`book_out_date_time_last` −
  `book_in_date_time_first`) in days, clipped at zero

---

## 4. How to combine the detention panel and the stays panel

There is **no double counting**:

- Detention panel covers book-ins through **Nov 30, 2023**
- Stays panel covers book-ins from **Dec 1, 2023** onward

You can splice them by stacking the two `county_year` (or
`county_month`) panels. The splice point is between calendar months
2023-11 (FOIA) and 2023-12 (DDP stays). When you splice the
`county_year` panel, the 2023 row in `county_year_panel.csv` contains
Jan–Nov 2023 book-ins, and the 2023 row in `county_year_stays_panel.csv`
contains Dec 2023 book-ins.

**Caveat.** The unit of analysis changes at the splice point. A row in
the FY12–FY23 portion is an episode count; a row in the FY24+ portion
is a stay count. Roughly: `n_stints_total` in the stays panel is the
closest equivalent to `n_episodes` in the FOIA panel, since both
approximate the number of facility-level book-in events. `n_stays`
counts complete custody journeys.

If you want a single self-consistent metric across the entire
2012-2026 window, options:
1. Use `n_stints_total` for FY24+ and `n_episodes` for FY12–23
   (closest semantically).
2. Use `n_unique_persons` everywhere (approximate but
   methodologically consistent).
3. Re-extract the FY12–23 FOIA workbooks into stays using DDP's
   methodology to get a single unit across all years. We have not
   done this — it would require running DDP's published pipeline.

---

## 5. What is NOT in here

- **Average daily population (ADP).** Not computed. We have
  `detention_days` / `total_days`; ADP = days / days-in-period.
  Straightforward to add downstream.
- **Per-facility breakdowns.** All panels are county-level. Use the
  `facility_crosswalk.csv` / `site_crosswalk.csv` to roll back up to
  the facility if needed.
- **Demographic breakdowns** (sex, age, country of origin, etc.).
  Available in the interim per-FY CSVs but not folded into the
  county-level panels. Easy to add.

---

## 6. Files for review

In the `for review/` folder there are two simplified spreadsheets for
manual county fill-in:

- `facilities_need_county.csv` — 43 detention facilities the pipeline
  could not place in a county
- `sites_need_county.csv` — 107 encounter sites the pipeline could not
  place in a county

Fill in the `county` column for any row you recognize; leave the rest
blank. Anything blank stays excluded from the panels.

---

## Code

All code, reference files, and this methodology note are in
<https://github.com/opxie1/icedetention>.
