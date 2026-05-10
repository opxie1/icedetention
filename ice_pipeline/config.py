"""Project paths, constants, and known column layout.

The 14 ICE FOIA detention files (FY12-FY25) all share a fixed layout: a
title block in rows 1-5 of a single sheet named FY<YYYY>, a header row in
row 6, and data rows starting at row 7. We hardcode the expected layout
here so the pipeline fails loudly if a future file deviates.
"""

from __future__ import annotations

from pathlib import Path

# --- Filesystem layout -------------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
INTERIM_DIR = DATA_DIR / "interim"
PROCESSED_DIR = DATA_DIR / "processed"
REFERENCES_DIR = ROOT / "references"

# --- Sheet layout ------------------------------------------------------------

HEADER_ROW = 6  # 1-indexed; row 6 contains the column titles
FIRST_DATA_ROW = 7

# Column letters of interest (1-indexed positions in the sheet).
COL_DETENTION_BOOK_IN = 5    # E "Detention Book In Date"
COL_DETENTION_FACILITY = 6   # F "Detention Facility"
COL_DETENTION_FAC_CODE = 7   # G "Detention Facility Code"
COL_DETENTION_BOOK_OUT = 8   # H "Detention Book Out Date"
COL_ANON_ID = 33             # AG "Anonymized Identifier"

# Full expected header order (used to validate the file structure).
EXPECTED_HEADERS = [
    "Detention ID",
    "Case ID",
    "Subject ID",
    "Stay Book In Date",
    "Detention Book In Date",
    "Detention Facility",
    "Detention Facility Code",
    "Detention Book Out Date",
    "Detention Release Reason",
    "Stay Book Out Date",
    "Stay Release Reason",
    "Religion",
    "Marital",
    "Gender",
    "Birth Date",
    "Ethnicity",
    "Alien File Number",
    "Birth Year",
    "Entry Status",
    "Bond Posted Date",
    "Bond Posted Amount",
    "Initial Bond Set Amount",
    "Case Status",
    "Case Category",
    "Final Order Yes No",
    "Final Order Date",
    "Departed Date",
    "Departure Country",
    "Case Threat Level",
    "Charge",
    "Charge Code",
    "Charge Section Code",
    "Anonymized Identifier",
]

# Output column names for the per-FY extracted CSVs.
EXTRACT_COLUMNS = [
    "fiscal_year",
    "facility_name",
    "facility_code",
    "book_in_date",
    "book_out_date",
    "person_id",
]

# Filename patterns -----------------------------------------------------------

# Pulls the FY out of the FOIA filename. Supports both two-digit and
# four-digit fiscal-year forms in case the agency changes naming style:
#   2023-ICFO_42034_Detentions_FY15_LESA-STU_FINAL-Redacted_raw.xlsx -> 15
#   <something>_FY2024_<more>.xlsx -> 24
INPUT_FILENAME_RE = r"_FY(\d{2}|\d{4})_"

# Sheet name convention used inside each workbook ("FY2015", "FY2012", ...).
SHEET_NAME_RE = r"^FY\d{4}$"


# --- ERO Encounters workbook layout -----------------------------------------
#
# The "ERO Encounters" FOIA file (e.g. 2025-ICLI-00019_2024-ICFO-39357...)
# uses a completely different schema from the detention workbooks:
#
#   * Two sheets: "Encounters <10012024" and "Encounters >=10012024".
#   * 25 columns instead of 33, with a header row at row 7 (not 6).
#   * The geographic field is "Responsible Site" (col 3), e.g.
#     "CHICAGO, IL, DOCKET CONTROL OFFICE", already containing state.
#   * Unit of analysis is *encounters* (which include detainers, program
#     events, prosecutorial discretion, etc.), not strictly detentions.

ENCOUNTERS_HEADER_ROW = 7
ENCOUNTERS_FIRST_DATA_ROW = 8

# Column letters of interest in the Encounters sheets (1-indexed).
ENC_COL_EVENT_DATE = 1            # A "Event Date"
ENC_COL_RESPONSIBLE_AOR = 2       # B "Responsible AOR"
ENC_COL_RESPONSIBLE_SITE = 3      # C "Responsible Site"
ENC_COL_LEAD_EVENT_TYPE = 4       # D "Lead Event Type"
ENC_COL_EVENT_TYPE = 6            # F "Event Type"
ENC_COL_FINAL_PROGRAM = 7         # G "Final Program"
ENC_COL_FINAL_PROGRAM_GROUP = 8   # H "Final Program Group"
ENC_COL_PROCESSING_DISP = 10      # J "Processing Disposition"
ENC_COL_UNIQUE_ID = 25            # Y "Unique Identifier"

ENCOUNTERS_EXPECTED_HEADERS = [
    "Event Date",
    "Responsible AOR",
    "Responsible Site",
    "Lead Event Type",
    "Lead Source",
    "Event Type",
    "Final Program",
    "Final Program Group",
    "Encounter Criminality",
    "Processing Disposition",
    "Case Status",
    "Case Category",
    "Departed Date",
    "Departure Country",
    "Final Order Yes No",
    "Final Order Date",
    "Birth Date",
    "Birth Year",
    "Citizenship Country",
    "Gender",
    "Event Landmark",
    "Alien File Number",
    "EID Case ID",
    "EID Subject ID",
    "Unique Identifier",
]

# Output columns for the encounters interim CSV.
ENCOUNTERS_EXTRACT_COLUMNS = [
    "period_tag",
    "event_date",
    "responsible_aor",
    "responsible_site",
    "lead_event_type",
    "event_type",
    "final_program",
    "final_program_group",
    "processing_disposition",
    "person_id",
]

# Filename matching for the encounters workbook.
ENCOUNTERS_FILENAME_GLOB = "*ERO Encounters*.xlsx"
ENCOUNTERS_SHEET_PREFIX = "Encounters "  # both sheets start with this
