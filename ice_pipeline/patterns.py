"""Regex flags + state heuristics for facility names."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

_UNUSUAL_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "hold_room",
        re.compile(
            r"\bHOLD(?:ING)?\s*(?:ROOM|RM)\b"
            r"|\bHOLDROOM\b"
            r"|\bHLDRM\b"
            r"|\bHOLD\s*$"
            r"|\b[A-Z]{2,}HOLD\b"
            r"|\bCPC\s+HOLDING\b"
            r"|\bCUSTODY\s+(CASE|HOLD|CENTER|CTR)\b"
            r"|\bCUST\s+CASE\b"
        ),
    ),
    (
        "hospital",
        re.compile(
            r"\bHOSPITAL\b"
            r"|\bHOSP\b"
            r"|\bMED\.?\s*(?:CTR|CENTER|CEN)\b"
            r"|\bMEDICAL\b"
            r"|\bINFIRMARY\b"
            r"|\bCLINIC\b"
            r"|\bHEALTHCARE\b"
            r"|\bHEALTH\b"
            r"|\bMHOS[A-Z]*\b"
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
            r"|\bCASA\s+(DE|DO)\b"
        ),
    ),
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
    haystack = (name or "").upper()
    if code:
        haystack = haystack + " " + code.upper()
    for label, pat in _UNUSUAL_PATTERNS:
        if pat.search(haystack):
            return True, label
    return False, ""


USPS_STATE_ABBR = {
    "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "DC", "FL", "GA", "HI",
    "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN",
    "MS", "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH",
    "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA",
    "WV", "WI", "WY", "PR", "GU", "VI", "AS", "MP",
}

_CITY_STATE_HINTS: dict[str, str] = {
    "HOUSTON": "TX", "EL PASO": "TX", "LAREDO": "TX", "HARLINGEN": "TX",
    "PORT ISABEL": "TX", "PEARSALL": "TX", "CONROE": "TX", "DALLAS": "TX",
    "SAN ANTONIO": "TX", "ELOY": "AZ", "FLORENCE": "AZ", "PHOENIX": "AZ",
    "TUCSON": "AZ", "MIAMI": "FL", "BROWARD": "FL", "KROME": "FL",
    "ATLANTA": "GA", "STEWART": "GA", "FOLKSTON": "GA", "NEW ORLEANS": "LA",
    "OAKDALE": "LA", "JENA": "LA", "WINN": "LA", "RICHWOOD": "LA",
    "ADAMS": "MS", "ADELANTO": "CA", "OTAY MESA": "CA", "MESA VERDE": "CA",
    "BAKERSFIELD": "CA", "AURORA": "CO", "DENVER": "CO", "BATAVIA": "NY",
    "BUFFALO": "NY", "ELIZABETH": "NJ", "BERGEN": "NJ", "ESSEX": "NJ",
    "HUDSON": "NJ", "YORK": "PA", "PHILADELPHIA": "PA", "CHICAGO": "IL",
    "BROADVIEW": "IL", "DETROIT": "MI", "BOSTON": "MA", "TACOMA": "WA",
    "SEATTLE": "WA", "PORTLAND": "OR", "SAN FRANCISCO": "CA",
    "LOS ANGELES": "CA", "ALBUQUERQUE": "NM", "SAN DIEGO": "CA",
    "BALTIMORE": "MD", "CIBOLA": "NM", "OTERO": "NM", "TORRANCE": "NM",
    "POLK": "TX", "JOE CORLEY": "TX", "LASALLE": "LA", "SOUTH TEXAS": "TX",
    "ETOWAH": "AL", "PINE PRAIRIE": "LA", "HONOLULU": "HI",
    "ANCHORAGE": "AK", "GLADES": "FL",
}


@dataclass
class StateGuess:
    state_abbr: str
    source: str


def guess_state(name: str, code: str | None) -> StateGuess:
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


def normalize_facility_key(name: str | None, code: str | None) -> tuple[str, str]:
    n = (name or "").strip().upper()
    c = (code or "").strip().upper()
    n = re.sub(r"\s+", " ", n)
    return n, c


def is_blank(value) -> bool:
    return value is None or (isinstance(value, str) and not value.strip())


def filter_unusual_categories(categories: Iterable[str]) -> set[str]:
    keep = {"hold_room", "hospital", "hotel_motel"}
    return {c for c in categories if c in keep}
