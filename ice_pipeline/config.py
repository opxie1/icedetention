"""Project paths and FOIA workbook column layout."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
INTERIM_DIR = DATA_DIR / "interim"
PROCESSED_DIR = DATA_DIR / "processed"
REFERENCES_DIR = ROOT / "references"

HEADER_ROW = 6
FIRST_DATA_ROW = 7

COL_DETENTION_BOOK_IN = 5
COL_DETENTION_FACILITY = 6
COL_DETENTION_FAC_CODE = 7
COL_DETENTION_BOOK_OUT = 8
COL_ANON_ID = 33

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

EXTRACT_COLUMNS = [
    "fiscal_year",
    "facility_name",
    "facility_code",
    "book_in_date",
    "book_out_date",
    "person_id",
]

# Supports both 2-digit ("_FY15_") and 4-digit ("_FY2024_") forms.
INPUT_FILENAME_RE = r"_FY(\d{2}|\d{4})_"
SHEET_NAME_RE = r"^FY\d{4}$"


ENCOUNTERS_HEADER_ROW = 7
ENCOUNTERS_FIRST_DATA_ROW = 8

ENC_COL_EVENT_DATE = 1
ENC_COL_RESPONSIBLE_AOR = 2
ENC_COL_RESPONSIBLE_SITE = 3
ENC_COL_LEAD_EVENT_TYPE = 4
ENC_COL_EVENT_TYPE = 6
ENC_COL_FINAL_PROGRAM = 7
ENC_COL_FINAL_PROGRAM_GROUP = 8
ENC_COL_PROCESSING_DISP = 10
ENC_COL_UNIQUE_ID = 25

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

ENCOUNTERS_FILENAME_GLOB = "*ERO Encounters*.xlsx"
ENCOUNTERS_SHEET_PREFIX = "Encounters "
