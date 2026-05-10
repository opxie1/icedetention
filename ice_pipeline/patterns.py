"""Heuristics for flagging ambiguous facility types and inferring state.

The professor specifically asked us to flag sites like hotels, hold rooms,
and similar non-standard locations. The patterns below run against the
uppercased facility name and code; matches set ``unusual_flag`` and a
human-readable ``unusual_type`` on the crosswalk row.

State inference is best-effort: codes ending in two letters that match a
USPS state abbreviation are a strong signal, and a few obvious city/state
keywords in the facility name fill in the rest. Anything we cannot infer
is left blank for the academics to fill in by hand.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

# --- Unusual / ambiguous facility patterns -----------------------------------

# Order matters: the first matching category wins. Patterns operate on the
# uppercased facility name + code joined by a space.
_UNUSUAL_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    # Hold room variants: "HOLD ROOM", "HOLD RM", "HOLDING ROOM", "HOLDROOM",
    # "HLDRM", trailing "HOLD" at end of name (e.g. "DALLAS F.O. HOLD"), and
    # codes ending in HOLD (e.g. DALHOLD, MTGHOLD, HLGHOLD).
    (
        "hold_room",
        re.compile(
            r"\bHOLD(?:ING)?\s*(?:ROOM|RM)\b"
            r"|\bHOLDROOM\b"
            r"|\bHLDRM\b"
            r"|\bHOLD\s*$"
            r"|\b[A-Z]{2,}HOLD\b"
            # "EGP CPC HOLDING" / "DRT CPC HOLDING" — CBP CPC = Centralized
            # Processing Center holding cells.
            r"|\bCPC\s+HOLDING\b"
            r"|\bCUSTODY\s+(CASE|HOLD|CENTER|CTR)\b"
            r"|\bCUST\s+CASE\b"
        ),
    ),
    (
        "hospital",
        re.compile(
            r"\bHOSPITAL\b"
            r"|\bHOSP\b"                              # truncated "hospital"
            r"|\bMED\.?\s*(?:CTR|CENTER|CEN)\b"        # "Med. Center" / "Med Ctr"
            r"|\bMEDICAL\b"                            # "Maricopa Medical"
            r"|\bINFIRMARY\b"
            r"|\bCLINIC\b"
            r"|\bHEALTHCARE\b"
            r"|\bHEALTH\b"                             # "Adventist Health", "Bronxcare Health System"
            r"|\bMHOS[A-Z]*\b"                         # codes ending -MHOS- (med hospital)
        ),
    ),
    (
        "hotel_motel",
        re.compile(
            r"\bHOTEL\b|\bMOTEL\b|\bINN\b(?!ER)|\bSUITES?\b|\bSTES?\b|\bLODGE\b"
            r"|\bRESIDENCE\s+INN\b"
            r"|\bWYNDHAM\b|\bRAMADA\b|\bSUPER\s*8\b|\bLA\s+QUINTA\b"
            r"|\bHILTON\b|\bMARRIOTT\b|\bHOLIDAY\s+INN\b|\bHAMPTON\b"
            r"|\bCOMFORT\s+(?:STES|SUITES|INN)\b|\bBEST\s+WEST\b|\bDRURY\b"
            r"|\bECONOLODGE\b|\bSTAYBRIDGE\b|\bRED\s+ROOF\b|\bCROWNE\s+PLAZA\b"
            r"|\bCASA\s+(DE|DO)\b"                    # "Casa de la Luz", "Casa Do Sonho"
        ),
    ),
    # Only "Staging" facilities count as unusual — they're hold-only, not
    # full detention centers. ICE-named "Processing Centers" (e.g. Adelanto
    # ICE Processing Center, Otero County Processing Center) are full
    # detention facilities and are NOT flagged.
    ("staging_processing", re.compile(r"\bSTAGING\b|\bSTAGE\s*AREA\b|\bMCAT\b")),
    ("airport", re.compile(r"\bAIRPORT\b|\bAIR\s*OPS?\b|\bINT'?L\s*AIRPORT\b|\bATL\s*AIR\b")),
    ("field_office", re.compile(r"\bFIELD\s*OFFICE\b|\bSUB(\s|-)*OFFICE\b|\bERO\s*OFFICE\b|\bICE\s*OFFICE\b")),
    ("border_station", re.compile(r"\bBORDER\s*PATROL\b|\bUSBP\b|\bBP\s*STATION\b|\bSECTOR\s*HQ\b")),
    ("transport", re.compile(r"\bTRANSPORT\b|\bESCORT\b|\bIN\s*TRANSIT\b|\bENROUTE\b")),
    ("courthouse", re.compile(r"\bCOURT(HOUSE)?\b|\bIMM(IGRATION)?\s*COURT\b|\bEOIR\b")),
    ("mental_health", re.compile(r"\bMENTAL\s*HEALTH\b|\bPSYCH(IATRIC)?\b|\bBEHAVIORAL\b")),
    ("morgue", re.compile(r"\bMORGUE\b|\bDECEASED\b|\bFUNERAL\b")),
    ("residence", re.compile(r"\bRESIDENCE\b|\bHOME\b\s*ADDRESS|\bHOUSE\s*ARREST\b")),
    ("juvenile_family", re.compile(r"\bJUVENILE\b|\bUAC\b|\bORR\b\s*SHELTER")),
]


def classify_unusual(name: str, code: str | None = None) -> tuple[bool, str]:
    """Return (unusual_flag, unusual_type).

    ``unusual_type`` is the empty string when no pattern matched.
    """
    haystack = (name or "").upper()
    if code:
        haystack = haystack + " " + code.upper()
    for label, pat in _UNUSUAL_PATTERNS:
        if pat.search(haystack):
            return True, label
    return False, ""


# --- State inference ---------------------------------------------------------

USPS_STATE_ABBR = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "DC", "FL", "GA", "HI",
    "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN",
    "MS", "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH",
    "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA",
    "WV", "WI", "WY", "PR", "GU", "VI", "AS", "MP",
}

# Cities whose name in the facility string is a near-unambiguous state hint.
# Kept short — used only as a fallback when the code suffix doesn't resolve.
_CITY_STATE_HINTS: dict[str, str] = {
    "HOUSTON": "TX",
    "EL PASO": "TX",
    "LAREDO": "TX",
    "HARLINGEN": "TX",
    "PORT ISABEL": "TX",
    "PEARSALL": "TX",
    "CONROE": "TX",
    "DALLAS": "TX",
    "SAN ANTONIO": "TX",
    "ELOY": "AZ",
    "FLORENCE": "AZ",
    "PHOENIX": "AZ",
    "TUCSON": "AZ",
    "MIAMI": "FL",
    "BROWARD": "FL",
    "KROME": "FL",
    "ATLANTA": "GA",
    "STEWART": "GA",
    "FOLKSTON": "GA",
    "NEW ORLEANS": "LA",
    "OAKDALE": "LA",
    "JENA": "LA",
    "WINN": "LA",
    "RICHWOOD": "LA",
    "ADAMS": "MS",
    "ADELANTO": "CA",
    "OTAY MESA": "CA",
    "MESA VERDE": "CA",
    "BAKERSFIELD": "CA",
    "AURORA": "CO",
    "DENVER": "CO",
    "BATAVIA": "NY",
    "BUFFALO": "NY",
    "ELIZABETH": "NJ",
    "BERGEN": "NJ",
    "ESSEX": "NJ",
    "HUDSON": "NJ",
    "YORK": "PA",
    "PHILADELPHIA": "PA",
    "CHICAGO": "IL",
    "BROADVIEW": "IL",
    "DETROIT": "MI",
    "BOSTON": "MA",
    "TACOMA": "WA",
    "SEATTLE": "WA",
    "PORTLAND": "OR",
    "SAN FRANCISCO": "CA",
    "LOS ANGELES": "CA",
    "ALBUQUERQUE": "NM",
    "SAN DIEGO": "CA",
    "BALTIMORE": "MD",
    "CIBOLA": "NM",
    "OTERO": "NM",
    "TORRANCE": "NM",
    "POLK": "TX",
    "JOE CORLEY": "TX",
    "LASALLE": "LA",
    "SOUTH TEXAS": "TX",
    "ETOWAH": "AL",
    "PINE PRAIRIE": "LA",
    "HONOLULU": "HI",
    "ANCHORAGE": "AK",
    "GLADES": "FL",
}


@dataclass
class StateGuess:
    state_abbr: str  # "" when we couldn't infer
    source: str      # "code_suffix" | "city_hint" | ""


def guess_state(name: str, code: str | None) -> StateGuess:
    """Best-effort USPS state abbreviation for a facility.

    Returns an empty StateGuess when nothing matches; the academic team
    fills these in via the overrides CSV.
    """
    if code:
        code_clean = re.sub(r"[^A-Z]", "", code.upper())
        if len(code_clean) >= 2:
            tail = code_clean[-2:]
            if tail in USPS_STATE_ABBR:
                return StateGuess(tail, "code_suffix")
    if name:
        upper = name.upper()
        for city, st in _CITY_STATE_HINTS.items():
            if re.search(rf"\b{re.escape(city)}\b", upper):
                return StateGuess(st, "city_hint")
    return StateGuess("", "")


# --- Convenience helpers -----------------------------------------------------

def normalize_facility_key(name: str | None, code: str | None) -> tuple[str, str]:
    """Trim/upcase the facility name + code so the same site collapses to one key."""
    n = (name or "").strip().upper()
    c = (code or "").strip().upper()
    n = re.sub(r"\s+", " ", n)
    return n, c


def is_blank(value) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def filter_unusual_categories(categories: Iterable[str]) -> set[str]:
    """Return only categories the email explicitly highlighted (hotels, hold rooms, etc.)."""
    keep = {"hold_room", "hospital", "hotel_motel"}
    return {c for c in categories if c in keep}
