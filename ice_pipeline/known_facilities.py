"""Known-facility resolution: map facility name/code to (state, county).

This is the actual crosswalk content — the published list of where ICE
detention facilities, contract jails, and field-office hold rooms are
physically located. Built from ICE's public detention-facility lists,
DHS OIG inspection reports, and prior FOIA datasets.

Entries are keyed by facility_code where possible (the codes are stable
across the FY12-FY23 FOIA releases). When the code is ambiguous or the
facility appears under different codes over time, we fall back to
matching the facility name.

The functions here only return ``(state_abbr, county_name)`` pairs;
the crosswalk module is responsible for looking up the FIPS code from
the FIPS reference CSV.
"""

from __future__ import annotations

import re
from typing import NamedTuple


class CountyHit(NamedTuple):
    state_abbr: str
    county_name: str  # bare county name, no "County" suffix; matches FIPS file
    source: str       # "code", "name", "city", "county_jail_pattern"


# --- Hardcoded major detention facilities (by facility_code) ----------------
# State + county for facilities that account for the bulk of detention
# episodes. Names in comments are the most-common facility_name string.
KNOWN_FACILITY_CODES: dict[str, tuple[str, str]] = {
    # Texas - South & Rio Grande Valley
    "PIC": ("TX", "Cameron"),         # Port Isabel SPC (Los Fresnos)
    "PIRGS": ("TX", "Cameron"),
    "RGS": ("TX", "Hidalgo"),         # Rio Grande Valley Staging (McAllen)
    "RGRNDTX": ("TX", "Webb"),        # Rio Grande Detention Center (Laredo)
    "LRDICDF": ("TX", "Webb"),        # Laredo Processing Center
    "LRDHOLD": ("TX", "Webb"),
    "LRDMCTX": ("TX", "Webb"),
    "EHDLGTX": ("TX", "Hidalgo"),     # East Hidalgo Detention (La Villa)
    "ELVDFTX": ("TX", "Willacy"),     # El Valle Detention (Raymondville)
    "WCRDFTX": ("TX", "Willacy"),     # Willacy Co Regional Det
    "VALVETX": ("TX", "Val Verde"),   # Val Verde Det Center
    "BROKSTX": ("TX", "Brooks"),      # Brooks County Jail
    "BSCORTX": ("TX", "Brooks"),      # BSCC airpark
    "BSFLTTX": ("TX", "Brooks"),      # BSCC flightline
    "HSF": ("TX", "Cameron"),         # Harlingen Staging
    "HLGHOLD": ("TX", "Cameron"),
    "HMCHOTX": ("TX", "Cameron"),     # Harlingen Medical
    "HRLGNTX": ("TX", "Cameron"),
    "VBHOSTX": ("TX", "Cameron"),     # Valley Baptist
    "PTISBTX": ("TX", "Cameron"),
    "LSFHOLD": ("TX", "Cameron"),     # Los Fresnos Hold Room
    "LFRESTX": ("TX", "Cameron"),     # Los Fresnos PD
    "SBNTOTX": ("TX", "Cameron"),     # San Benito PD
    "BRWNSTX": ("TX", "Cameron"),     # Brownsville PD
    "MRCDSTX": ("TX", "Hidalgo"),     # Mercedes PD
    "EDNBGTX": ("TX", "Hidalgo"),     # Edinburg PD
    "MCAHOLD": ("TX", "Hidalgo"),     # McAllen Hold
    "PLMVWTX": ("TX", "Hidalgo"),     # Palmview PD
    "ALAMOTX": ("TX", "Hidalgo"),     # Alamo PD
    "HDLGOTX": ("TX", "Hidalgo"),     # Hidalgo PD
    "SJUANTX": ("TX", "Hidalgo"),     # San Juan PD
    "LAFERTX": ("TX", "Cameron"),     # La Feria PD
    "WESLTX": ("TX", "Hidalgo"),      # Weslaco
    "SP8WWTX": ("TX", "Hidalgo"),     # Super 8 Weslaco
    "HISMCTX": ("TX", "Hidalgo"),     # Hampton Inn McAllen
    "LCIMCTX": ("TX", "Hidalgo"),     # La Copa McAllen
    "HTLPPTX": ("TX", "Hidalgo"),     # Pharr Plaza
    "RGHOSTX": ("TX", "Hidalgo"),     # Rio Grande State Hospital
    "HIDALTX": ("TX", "Hidalgo"),     # Hidalgo County Sheriff
    "SPIPDTX": ("TX", "Cameron"),     # South Padre Island PD
    "STDHOLD": ("TX", "Frio"),        # South Texas/Pearsall
    "STCDFTX": ("TX", "Frio"),        # Dilley
    "STFRCTX": ("TX", "Frio"),        # South Texas Family (Dilley)
    "TASTDTX": ("TX", "Frio"),
    "TAKARTX": ("TX", "Karnes"),
    "KRNRCTX": ("TX", "Karnes"),      # Karnes Co Immigration Process
    "KCCDCTX": ("TX", "Karnes"),      # Karnes Civil Det
    "KARNETX": ("TX", "Karnes"),      # Karnes Cty Corr
    "KINNETX": ("TX", "Kinney"),
    "POLKCTX": ("TX", "Polk"),        # IAH (Livingston)
    "JCRLYTX": ("TX", "Montgomery"),  # Joe Corley Processing
    "MTGPCTX": ("TX", "Montgomery"),  # Montgomery Processing
    "MONTGTX": ("TX", "Montgomery"),  # Montgomery Co Jail (Conroe)
    "MTGHOLD": ("TX", "Montgomery"),  # Montgomery Hold
    "HCAHCTX": ("TX", "Montgomery"),  # HCA Conroe
    "HUNMHTX": ("TX", "Walker"),      # Huntsville Memorial
    "HOUICDF": ("TX", "Harris"),      # Houston Contract Det
    "HOUHOLD": ("TX", "Harris"),
    "HOUGTTX": ("TX", "Harris"),      # Greentree IAH
    "IAHSFTX": ("TX", "Harris"),      # George Bush Intercontinental
    "HARRIGA": ("GA", "Harris"),      # Harris County GA - careful, different state
    "HHBTHTX": ("TX", "Harris"),      # Harris Health Ben Taub
    "HCPSYTX": ("TX", "Harris"),      # Harris Co Psychiatric
    "MEMRHFL": ("FL", "Broward"),     # Memorial Regional (Hollywood)
    "MHNHHTX": ("TX", "Harris"),      # Memorial Hermann NW
    "EPC": ("TX", "El Paso"),         # El Paso SPC
    "EPCJUVI": ("TX", "El Paso"),
    "EPCDFTX": ("TX", "El Paso"),
    "EPLTATX": ("TX", "El Paso"),
    "EPBHSTX": ("TX", "El Paso"),
    "TNGLPOE": ("TX", "El Paso"),     # Tornillo POE
    "TORHOLD": ("TX", "El Paso"),     # Tornillo
    "DSMCNTX": ("TX", "El Paso"),     # Del Sol Medical
    "UMCEPTX": ("TX", "El Paso"),     # UMC El Paso
    "RDHEATX": ("TX", "El Paso"),     # Radisson ELP airport
    "HSEPTX": ("TX", "El Paso"),
    "CSHEPTX": ("TX", "El Paso"),
    "CISAETX": ("TX", "El Paso"),
    "HISEPTX": ("TX", "El Paso"),
    "HSELPTX": ("TX", "El Paso"),
    "HIELPTX": ("TX", "El Paso"),
    "RAMEPTX": ("TX", "El Paso"),
    "ELPCOTX": ("TX", "El Paso"),
    "WTXDFTX": ("TX", "Hudspeth"),    # West Texas Det Fac (Sierra Blanca)
    "HUDSPTX": ("TX", "Hudspeth"),
    "BOPLTL": ("TX", "El Paso"),      # La Tuna FCI satellite
    "EPCPCTX": ("TX", "El Paso"),     # EGP CPC

    # Texas - Dallas/Ft Worth/Central
    "DALHOLD": ("TX", "Dallas"),      # Dallas FO Hold
    "DALCOTX": ("TX", "Dallas"),
    "EULESTX": ("TX", "Tarrant"),     # Euless City Jail
    "BEDCITX": ("TX", "Tarrant"),     # Bedford City Jail
    "JOHNSTX": ("TX", "Johnson"),     # Johnson Co Jail
    "PRLDCTX": ("TX", "Johnson"),     # Prairieland Det (Alvarado)
    "PRLHOLD": ("TX", "Johnson"),
    "JHRWLTX": ("TX", "McLennan"),    # Jack Harwell (Waco)
    "WCTHOLD": ("TX", "McLennan"),    # Waco DRO
    "WACLATX": ("TX", "Bexar"),       # Central Texas Det (San Antonio)
    "MCCLETX": ("TX", "McLennan"),
    "RNDLLTX": ("TX", "Randall"),
    "AMTHOLD": ("TX", "Potter"),      # Amarillo Hold
    "LBKHOLD": ("TX", "Lubbock"),
    "LUBBOTX": ("TX", "Lubbock"),
    "ABTHOLD": ("TX", "Taylor"),      # Abilene Hold
    "ABRMCTX": ("TX", "Taylor"),
    "TAYLOTX": ("TX", "Taylor"),
    "WINCOTX": ("TX", "Winkler"),
    "MIDLATX": ("TX", "Midland"),
    "MLDHOLD": ("TX", "Midland"),
    "BSTAYTX": ("TX", "Williamson"),  # Baylor Scott White Round Rock
    "BSWRRTX": ("TX", "Williamson"),
    "ANSGHTX": ("TX", "Jones"),       # Anson General (Anson)
    "ECLECTX": ("TX", "Ector"),       # Ector Co LEC
    "ODESSTX": ("TX", "Ector"),
    "ECTORTX": ("TX", "Ector"),
    "BURNETX": ("TX", "Burnet"),
    "PECOSTX": ("TX", "Reeves"),      # Pecos Criminal Justice
    "REDETTX": ("TX", "Reeves"),      # Reeves Co Det (3 facilities)
    "REJUVTX": ("TX", "Reeves"),
    "DRCPCTX": ("TX", "Val Verde"),   # Del Rio CPC
    "DLRHOLD": ("TX", "Val Verde"),
    "EDNDCTX": ("TX", "Concho"),      # Eden Detention (Concho County)
    "EDNHOLD": ("TX", "Concho"),
    "EDCHOLD": ("TX", "Concho"),
    "SAGHOLD": ("TX", "Tom Green"),   # San Angelo
    "SAGRSTX": ("TX", "Tom Green"),
    "TGREETX": ("TX", "Tom Green"),
    "SHNMCTX": ("TX", "Tom Green"),   # Shannon Medical (San Angelo)
    "GRYLATX": ("TX", "Grayson"),
    "GUADATX": ("TX", "Guadalupe"),
    "BSQUETX": ("TX", "Bosque"),
    "FREESTX": ("TX", "Freestone"),
    "BELCOTX": ("TX", "Bell"),
    "MAVERTX": ("TX", "Maverick"),
    "MARTNTX": ("TX", "Martin"),
    "FRIOCTX": ("TX", "Frio"),
    "SMRVLTX": ("TX", "Somervell"),
    "ANDRWTX": ("TX", "Andrews"),
    "CULBETX": ("TX", "Culberson"),
    "CRYCCTX": ("TX", "Zavala"),      # Crystal City (Zavala County)
    "VICTOTX": ("TX", "Victoria"),
    "CCCSSTX": ("TX", "Nueces"),      # Christus Spohn CC South
    "CRPHOLD": ("TX", "Nueces"),
    "CBENDTX": ("TX", "Nueces"),      # Coastal Bend (Robstown is in Nueces)
    "TVMSATX": ("TX", "Bexar"),       # Texas Vista Medical (San Antonio)
    "MSTHSTX": ("TX", "Bexar"),
    "OKMHKTX": ("TX", "Karnes"),      # Otto Kaiser (Kenedy is in Karnes)
    "BMCSATX": ("TX", "Bexar"),
    "BWMARCA": ("CA", "Monterey"),    # Best Western Marina
    "FRIRHTX": ("TX", "Frio"),        # Frio Regional Hospital
    "PTISATX": ("TX", "Bexar"),       # Pear Tree Inn SAT
    "PRESITX": ("TX", "Presidio"),
    "WARCOTX": ("TX", "Ward"),
    "DRHCSTX": ("TX", "Dimmit"),      # Dimmit Regional
    "JEFFETX": ("TX", "Jefferson"),
    "WAYNENY": ("NY", "Wayne"),
    "HARDJIA": ("IA", "Hardin"),

    # New York / Northeast
    "VRK": ("NY", "New York"),        # Varick St SPC
    "BTV": ("NY", "Genesee"),         # Buffalo SPC = Batavia
    "CMDHOLD": ("NY", "Genesee"),     # Batavia Cmd Center
    "BUFHOLD": ("NY", "Erie"),
    "NYCHOLD": ("NY", "New York"),
    "JFKTSNY": ("NY", "Queens"),
    "JHMCJNY": ("NY", "Queens"),
    "QUEHONY": ("NY", "Queens"),
    "BEHOSNY": ("NY", "New York"),    # Bellevue
    "ISHOSNY": ("NY", "New York"),    # Beth Israel
    "KCHOSNY": ("NY", "Kings"),
    "BXCHSNY": ("NY", "Bronx"),
    "BOPBRO": ("NY", "Kings"),        # Brooklyn MDC
    "ALBHOLD": ("NY", "Albany"),
    "ALBCONY": ("NY", "Albany"),
    "ONONDNY": ("NY", "Onondaga"),
    "RENSSNY": ("NY", "Rensselaer"),
    "CIPHOLD": ("NY", "Suffolk"),     # Central Islip
    "CHMCINY": ("NY", "Suffolk"),
    "SUFFONY": ("NY", "Suffolk"),
    "NASSANY": ("NY", "Nassau"),
    "ORANGNY": ("NY", "Orange"),
    "OGRMCNY": ("NY", "Orange"),      # Orange Reg Med
    "NWHNVNC": ("NC", "New Hanover"),
    "WHITFGA": ("GA", "Whitfield"),
    "ALLEGNY": ("NY", "Allegany"),
    "WAYNNY": ("NY", "Wayne"),
    "BROMMNY": ("NY", "Broome"),
    "JEFFENY": ("NY", "Jefferson"),
    "LIVINNY": ("NY", "Livingston"),
    "ONECONY": ("NY", "Oneida"),
    "LEWISNY": ("NY", "Lewis"),
    "TIOGANY": ("NY", "Tioga"),
    "CAYUGNY": ("NY", "Cayuga"),
    "CATTANY": ("NY", "Cattaraugus"),
    "WYMCONY": ("NY", "Wyoming"),
    "GENESNY": ("NY", "Genesee"),
    "YATESNY": ("NY", "Yates"),
    "STEUBNY": ("NY", "Steuben"),
    "WASCONY": ("NY", "Washington"),
    "STLAWNY": ("NY", "St. Lawrence"),
    "CHEMUNY": ("NY", "Chemung"),
    "CHENANY": ("NY", "Chenango"),
    "MADISNY": ("NY", "Madison"),
    "ECMCBNY": ("NY", "Erie"),        # Erie County Med Center
    "NYULSTC": ("NY", "Ulster"),
    "NYBUFFC": ("NY", "Erie"),
    "NYFISHC": ("NY", "Dutchess"),
    "NYEASTC": ("NY", "Ulster"),
    "NYGREAC": ("NY", "Washington"),
    "NYGROVC": ("NY", "Livingston"),
    "NYMARCC": ("NY", "Oneida"),
    "NYMOHOC": ("NY", "Oneida"),
    "NYORLNC": ("NY", "Orleans"),
    "NYMDSTC": ("NY", "Oneida"),
    "NYOGDNC": ("NY", "St. Lawrence"),
    "NYLIVIC": ("NY", "Livingston"),
    "NYADIRC": ("NY", "Essex"),
    "CSYJVNY": ("NY", "New York"),    # Casey House

    # New Jersey
    "ELZICDF": ("NJ", "Union"),       # Elizabeth Contract DF
    "ESSEXNJ": ("NJ", "Essex"),
    "HUDSONJ": ("NJ", "Hudson"),
    "BERGENJ": ("NJ", "Bergen"),
    "MONMONJ": ("NJ", "Monmouth"),
    "DHDFNJ": ("NJ", "Essex"),        # Delaney Hall (Newark)
    "MLJHOLD": ("NJ", "Burlington"),  # Mt Laurel hold
    "SUSSENJ": ("NJ", "Sussex"),
    "SALEMNJ": ("NJ", "Salem"),
    "TRRMCNJ": ("NJ", "Union"),       # Trinitas Regional
    "AKPSYNJ": ("NJ", "Mercer"),      # Anne Klein Psych
    "JYCMCNJ": ("NJ", "Hudson"),      # Jersey City Med
    "HACMCNJ": ("NJ", "Bergen"),      # Hackensack Med
    "UNIVHNJ": ("NJ", "Essex"),       # University Hospital Newark
    "BOPFAI": ("NJ", "Cumberland"),   # Fairton FCI

    # Pennsylvania
    "YORCOPA": ("PA", "York"),
    "YRKHOLD": ("PA", "York"),
    "PIKCOPA": ("PA", "Pike"),
    "PKCNTPA": ("PA", "Pike"),
    "PKEHOLD": ("PA", "Pike"),
    "CLINTPA": ("PA", "Clinton"),
    "CAMBRPA": ("PA", "Cambria"),
    "BERKSPA": ("PA", "Berks"),
    "BRKHOLD": ("PA", "Berks"),
    "BCORCPA": ("PA", "Berks"),
    "BEFAMPA": ("PA", "Berks"),
    "BESECPA": ("PA", "Berks"),
    "BEJUVPA": ("PA", "Berks"),
    "BEAVRPA": ("PA", "Beaver"),
    "LACKAPA": ("PA", "Lackawanna"),
    "LEHIGPA": ("PA", "Lehigh"),
    "DAUPHPA": ("PA", "Dauphin"),
    "DELAWPA": ("PA", "Delaware"),
    "ERICOPA": ("PA", "Erie"),
    "LAWREPA": ("PA", "Lawrence"),
    "ALLEGPA": ("PA", "Allegheny"),
    "PITHOLD": ("PA", "Allegheny"),
    "PHIHOLD": ("PA", "Philadelphia"),
    "MSVPCPA": ("PA", "Clearfield"),  # Moshannon Valley
    "BOPMVC": ("PA", "Clearfield"),
    "MVPNHPA": ("PA", "Clearfield"),  # Penn Highlands Clearfield
    "CARBOPA": ("PA", "Carbon"),
    "COLUMPA": ("PA", "Columbia"),
    "MTNITPA": ("PA", "Centre"),      # Mt Nittany (State College)
    "MONTGPA": ("PA", "Montgomery"),
    "BOPCAA": ("PA", "Wayne"),        # USP Canaan

    # Virginia
    "HRREGVA": ("VA", "Portsmouth city"),  # Hampton Roads (Portsmouth)
    "CARDFVA": ("VA", "Caroline"),    # ICA Farmville is in Prince Edward, but Caroline DF is in Caroline
    "FRMVLVA": ("VA", "Prince Edward"),  # Farmville is in Prince Edward
    "RAPPSVA": ("VA", "Stafford"),    # Rappahannock Sec Center
    "PWILLVA": ("VA", "Prince William"),
    "FAICOVA": ("VA", "Fairfax"),
    "FXADCVA": ("VA", "Fairfax"),
    "RICHMVA": ("VA", "Richmond city"),
    "RCMHOLD": ("VA", "Richmond city"),
    "ROANOVA": ("VA", "Roanoke city"),
    "RMKHOLD": ("VA", "Roanoke city"),
    "RONKEVA": ("VA", "Roanoke city"),
    "ALEXAVA": ("VA", "Alexandria city"),
    "NORFOVA": ("VA", "Norfolk city"),
    "NORHOLD": ("VA", "Norfolk city"),
    "VIRBEVA": ("VA", "Virginia Beach city"),
    "WTREGVA": ("VA", "Suffolk city"),
    "VPREGVA": ("VA", "Williamsburg city"),
    "RSREGVA": ("VA", "Prince George"),
    "NRREGVA": ("VA", "Loudoun"),
    "ALBEMVA": ("VA", "Albemarle"),
    "ROCKIVA": ("VA", "Rockingham"),
    "HBGHOLD": ("VA", "Harrisonburg city"),
    "MWASHVA": ("VA", "Fredericksburg city"),
    "MRREGVA": ("VA", "Augusta"),     # Middle River Regional
    "CSSCHVA": ("VA", "Prince Edward"),
    "WVIRGVA": ("VA", "Roanoke"),     # Western VA Reg
    "NRJDCVA": ("VA", "Roanoke"),
    "CVREGVA": ("VA", "Orange"),      # Central VA Regional (Orange)
    "NVJDCVA": ("VA", "Fairfax"),     # Northern VA Juvenile
    "NNREGVA": ("VA", "Warsaw"),      # Northern Neck (Richmond County actually)
    "LOUCOVA": ("VA", "Loudoun"),
    "CHFLDVA": ("VA", "Chesterfield"),
    "CULPEVA": ("VA", "Culpeper"),

    # West Virginia
    "WVSCENT": ("WV", "Kanawha"),     # South Central Reg (Charleston)
    "WVNORTH": ("WV", "Marshall"),    # Northern Reg Jail
    "WVEASTR": ("WV", "Berkeley"),    # Eastern Reg
    "WVREGWV": ("WV", "Berkeley"),
    "CENTRWV": ("WV", "Braxton"),
    "BOPMRG": ("WV", "Monongalia"),   # Morgantown FCI

    # Maryland / DC / Delaware
    "WORCEMD": ("MD", "Worcester"),
    "HOWARMD": ("MD", "Howard"),
    "FREDEMD": ("MD", "Frederick"),
    "FRDHOLD": ("MD", "Frederick"),
    "FCOHOLD": ("MD", "Frederick"),
    "DORCHMD": ("MD", "Dorchester"),
    "AAORDMD": ("MD", "Anne Arundel"),
    "CARROMD": ("MD", "Carroll"),
    "BALHOLD": ("MD", "Baltimore city"),
    "DIIHBMD": ("MD", "Baltimore city"),
    "DCDOCDC": ("DC", "District of Columbia"),
    "WASHOLD": ("DC", "District of Columbia"),
    "DECCSMY": ("DE", "Sussex"),      # Delaware Correctional (Sussex)
    "SUSSEDE": ("DE", "Sussex"),
    "DVDHOLD": ("DE", "Kent"),        # Dover hold

    # Massachusetts / Rhode Island / Connecticut / Maine / NH / VT
    "BPC": ("MA", "Suffolk"),         # Boston SPC
    "BOSHOLD": ("MA", "Suffolk"),
    "BIDHPMA": ("MA", "Suffolk"),
    "SUFFOMA": ("MA", "Suffolk"),
    "BRINDMA": ("MA", "Bristol"),
    "PLYMOMA": ("MA", "Plymouth"),
    "GREENMA": ("MA", "Franklin"),    # Franklin HoC (Greenfield)
    "HAMPDMA": ("MA", "Hampden"),
    "BARNSMA": ("MA", "Barnstable"),
    "NORFOMA": ("MA", "Norfolk"),
    "MABSHOS": ("MA", "Plymouth"),    # Bridgewater State (technically Plymouth Co)
    "MATEWKS": ("MA", "Middlesex"),
    "MATSHOS": ("MA", "Bristol"),     # Taunton State
    "LSHOSMA": ("MA", "Suffolk"),     # Lemuel Shattuck
    "HOTELMA": ("MA", "Suffolk"),
    "NASHUMA": ("MA", "Suffolk"),     # Nashua St Jail (Boston)
    "WYATTRI": ("RI", "Providence"),  # Wyatt is in Central Falls
    "RICRANS": ("RI", "Providence"),
    "MIRHPRI": ("RI", "Providence"),
    "HARFOCT": ("CT", "Hartford"),
    "HARHOLD": ("CT", "Hartford"),
    "CTLAFSL": ("CT", "Hartford"),
    "CUMBEME": ("ME", "Cumberland"),
    "POMHOLD": ("ME", "Cumberland"),  # Portland ME
    "MEYTHCT": ("ME", "Cumberland"),  # Long Creek (S Portland)
    "PISCAME": ("ME", "Piscataquis"),
    "AROOSME": ("ME", "Aroostook"),
    "PENOBME": ("ME", "Penobscot"),
    "SOMERME": ("ME", "Somerset"),
    "YORKCME": ("ME", "York"),
    "STRAFNH": ("NH", "Strafford"),
    "MANHOLD": ("NH", "Hillsborough"),  # Manchester
    "COOCONH": ("NH", "Coos"),
    "ROCKINH": ("NH", "Rockingham"),
    "WWDHDNH": ("NH", "Strafford"),   # Wentworth Douglas
    "VTSTALB": ("VT", "Franklin"),    # NW State CF (St Albans)
    "STAHOLD": ("VT", "Franklin"),    # St Albans
    "VTCHTDN": ("VT", "Chittenden"),
    "VTDCORR": ("VT", "Washington"),  # VT Dept of Corrections (Waterbury HQ)
    "FRACOVT": ("VT", "Franklin"),
    "ADDCOVT": ("VT", "Addison"),

    # Florida
    "KRO": ("FL", "Miami-Dade"),      # Krome North SPC
    "KROHOLD": ("FL", "Miami-Dade"),
    "KRHUBFL": ("FL", "Miami-Dade"),
    "MIAHOLD": ("FL", "Broward"),     # Miami (Miramar) Hold = Broward
    "MSF": ("FL", "Broward"),         # Miami Staging
    "WCCPBFL": ("FL", "Broward"),     # Broward Transitional (Pompano)
    "BROCRFL": ("FL", "Broward"),
    "BROJAFL": ("FL", "Broward"),
    "BRGMCFL": ("FL", "Broward"),
    "FLBHCFL": ("FL", "Broward"),
    "FLHOSFL": ("FL", "Broward"),
    "ASHRSFL": ("FL", "Broward"),
    "PWHOSFL": ("FL", "Palm Beach"),
    "PALMBFL": ("FL", "Palm Beach"),
    "LAKMCFL": ("FL", "Palm Beach"),
    "LRKNHFL": ("FL", "Miami-Dade"),
    "LRKBHFL": ("FL", "Miami-Dade"),
    "JMHOSFL": ("FL", "Miami-Dade"),
    "UMIAHFL": ("FL", "Miami-Dade"),
    "BOPMIM": ("FL", "Miami-Dade"),
    "BOPMIA": ("FL", "Miami-Dade"),
    "MERCYFL": ("FL", "Miami-Dade"),
    "WMDBHFL": ("FL", "Miami-Dade"),
    "PMHOSFL": ("FL", "Miami-Dade"),  # Palmetto
    "WKBHMFL": ("FL", "Miami-Dade"),  # West Kendall Baptist
    "CKHOSFL": ("FL", "Miami-Dade"),  # HCA Kendall
    "METROFL": ("FL", "Miami-Dade"),
    "CEMEDFL": ("FL", "Miami-Dade"),
    "NBRMCFL": ("FL", "Broward"),
    "NFMIGFL": ("FL", "Miami-Dade"),
    "GLADEFL": ("FL", "Glades"),      # Glades Det (Moore Haven)
    "COLLIFL": ("FL", "Collier"),
    "HRCMCFL": ("FL", "Collier"),
    "BAKERFL": ("FL", "Baker"),
    "FLBAKCI": ("FL", "Baker"),
    "ORLHOLD": ("FL", "Orange"),
    "ORANGFL": ("FL", "Orange"),
    "HCAFMFL": ("FL", "Duval"),       # Jacksonville
    "JAXHOLD": ("FL", "Duval"),
    "TAMHOLD": ("FL", "Hillsborough"),
    "PINELFL": ("FL", "Pinellas"),
    "TALHOLD": ("FL", "Leon"),        # Tallahassee
    "PUTMAFL": ("FL", "Putnam"),
    "STJONFL": ("FL", "St. Johns"),
    "MARTIFL": ("FL", "Martin"),
    "STUHOLD": ("FL", "Martin"),      # Stuart hold
    "HENDRFL": ("FL", "Hendry"),
    "HNRMCFL": ("FL", "Hendry"),
    "FMYHOLD": ("FL", "Lee"),         # Fort Myers
    "MNRMCFL": ("FL", "Broward"),
    "MONROFL": ("FL", "Monroe"),
    "LRKMCFL": ("FL", "Monroe"),
    "WAKULFL": ("FL", "Wakulla"),
    "BRDFDFL": ("FL", "Bradford"),
    "COLUMFL": ("FL", "Columbia"),
    "HARDEFL": ("FL", "Hardee"),
    "SUWANFL": ("FL", "Suwannee"),
    "LEVYCFL": ("FL", "Levy"),
    "CHRLTFL": ("FL", "Charlotte"),
    "MANATFL": ("FL", "Manatee"),
    "BRADEFL": ("FL", "Manatee"),
    "HERNAFL": ("FL", "Hernando"),
    "EFMHMFL": ("FL", "Baker"),       # Ed Fraser (Macclenny)
    "FLBREVC": ("FL", "Brevard"),
    "FLDADCI": ("FL", "Miami-Dade"),
    "FLMARIC": ("FL", "Marion"),
    "FLSPSTA": ("FL", "Bradford"),    # FL State Prison Starke
    "BOPCNV": ("TN", "Davidson"),     # Nashville Comm Corr

    # Georgia
    "STWRTGA": ("GA", "Stewart"),
    "IRWINGA": ("GA", "Irwin"),
    "FIPCMGA": ("GA", "Charlton"),    # Folkston main
    "JAMESGA": ("GA", "Charlton"),
    "FIPCAGA": ("GA", "Charlton"),
    "ATLHOLD": ("GA", "Fulton"),
    "ATLANGA": ("GA", "Fulton"),      # Atlanta Pretrial
    "GMHATGA": ("GA", "Fulton"),      # Grady Memorial
    "RADDFGA": ("GA", "Henry"),       # Robert Deyton (Lovejoy)
    "NGDCTGA": ("GA", "Hall"),        # North GA Det Center (Gainesville)
    "HASHENE": ("GA", "Hall"),        # Hall County Sheriff (NE - typo)
    "HALLJGA": ("GA", "Hall"),
    "WHITFGA": ("GA", "Whitfield"),
    "FLOYDGA": ("GA", "Floyd"),
    "COBBJGA": ("GA", "Cobb"),
    "DEKABGA": ("GA", "DeKalb"),
    "BARTOGA": ("GA", "Bartow"),
    "GWINNGA": ("GA", "Gwinnett"),
    "CHATHGA": ("GA", "Chatham"),
    "BOPRAE": ("GA", "Telfair"),      # McRae Correctional
    "GADRYJM": ("GA", "Charlton"),    # D Ray James (Folkston)

    # Louisiana
    "JENATLA": ("LA", "Rapides"),     # Alexandria Staging
    "JENADLA": ("LA", "LaSalle"),     # Central Louisiana ICE Proc (Jena)
    "BASILLA": ("LA", "Acadia"),      # South Louisiana ICE Proc (Basile, in Acadia Parish)
    "SNDHOLD": ("CA", "San Diego"),   # SD field office staging
    "SNJHOLD": ("CA", "San Diego"),   # alt SD field office hold
    "CCAHUTX": ("TX", "Williamson"),  # T. Don Hutto (Taylor, TX = Williamson Co)
    "IWAHOLD": ("AZ", "Maricopa"),    # AZ Removal Op Coord Center (Phoenix)
    "FCLT8CA": ("CA", "San Diego"),   # Facility 8 - SD
    "LQWCSTX": ("TX", "Frio"),        # La Quinta Pearsall
    "SUPHDTX": ("TX", "Webb"),        # Super 8 Wyndham (Laredo area)
    "COMFTFL": ("FL", "Miami-Dade"),  # Comfort Suites Hotel (Miami)
    "GUDOCHG": ("GU", "Guam"),        # Dept of Corrections Hagatna
    "CHAHOLD": ("VI", "St. Thomas"),  # Charlotte Amalie hold
    "APIBHCA": ("CA", "San Diego"),   # Alvarado Parkway (La Mesa, SD County)
    "SAIHOLD": ("MP", "Saipan"),
    "MPSIPAN": ("MP", "Saipan"),
    "LTVHOLD": ("VA", "Fairfax"),     # Lorton, VA hold (Fairfax County)
    "SALHOLD": ("MD", "Wicomico"),    # Salisbury, MD
    "SAJHOLD": ("PR", "San Juan"),
    "SJUHOLD": ("PR", "Carolina"),    # San Juan Airport
    "BOPGUA": ("PR", "Guaynabo"),
    "SJS": ("PR", "Bayamon"),         # San Juan Staging
    "HCAFCC": ("FL", "Miami-Dade"),
    "ANCHOAK": ("AK", "Anchorage"),
    "AKCOOKI": ("AK", "Anchorage"),
    "ANCHOLD": ("AK", "Anchorage"),
    "PINEPLA": ("LA", "Evangeline"),  # Pine Prairie
    "RWCCMLA": ("LA", "Ouachita"),    # Richwood (Monroe)
    "LAWINCI": ("LA", "Winn"),        # Winn Correctional
    "OLACCLA": ("LA", "Catahoula"),   # LaSalle Corr Olla (Catahoula Parish)
    "TENSALA": ("LA", "Tensas"),
    "CATAHLA": ("LA", "Catahoula"),
    "BOSSRLA": ("LA", "Bossier"),
    "JKPCCLA": ("LA", "Jackson"),
    "APPSCLA": ("LA", "Allen"),       # Allen Parish PSC (Kinder)
    "RVRCCLA": ("LA", "Concordia"),   # River Correctional (Ferriday)
    "CONCOLA": ("LA", "Concordia"),
    "BOPOAD": ("LA", "Allen"),        # Oakdale FDC (Allen Parish)
    "AVPARLA": ("LA", "Avoyelles"),
    "ORPARLA": ("LA", "Orleans"),
    "STTAMLA": ("LA", "St. Tammany"),
    "NATCHLA": ("LA", "Natchitoches"),
    "USMWDLA": ("LA", "Caddo"),       # USMS WDLA Shreveport
    "VVSHOLD": ("LA", "Caddo"),       # Shreveport
    "LKLNDLA": ("LA", "Caddo"),
    "CSANOLA": ("LA", "Rapides"),     # Comfort Suites Alexandria
    "HIRAYTX": ("TX", "Frio"),        # Holiday Inn Pearsall
    "CISEPTX": ("TX", "El Paso"),     # Comfort Suites
    "CSCLQTX": ("TX", "Frio"),        # La Quinta Casa De Paz Pearsall
    "BWEPATX": ("TX", "Frio"),        # Best Western Pearsall
    "HAVACTX": ("TX", "Frio"),        # Hotel AVA
    "WINWYAZ": ("AZ", "Pinal"),       # Wingate Wyndham Casa Esperanza
    "QLTYSCA": ("CA", "Imperial"),    # Quality Suites Calexico
    "HESPCAZ": ("AZ", "Pima"),        # Holiday Inn Express Tucson
    "ALESSAZ": ("AZ", "Maricopa"),    # Stes Scottsdale
    "NOLHOLD": ("LA", "Orleans"),

    # Mississippi
    "ADAMSMS": ("MS", "Adams"),       # Adams Co Det (Natchez)
    "TALLAMS": ("MS", "Tallahatchie"),
    "MADISMS": ("MS", "Madison"),
    "HCPSCMS": ("MS", "Hancock"),
    "JAKHOLD": ("MS", "Hinds"),       # Jackson MS
    "USMSDMS": ("MS", "Hinds"),

    # Alabama
    "ETOWAAL": ("AL", "Etowah"),
    "ETWHOLD": ("AL", "Etowah"),
    "DEKALAL": ("AL", "DeKalb"),
    "BALDWAL": ("AL", "Baldwin"),
    "PCKNSAL": ("AL", "Pickens"),
    "MNTGMAL": ("AL", "Montgomery"),
    "MONCJAL": ("AL", "Montgomery"),
    "BHMHOLD": ("AL", "Jefferson"),
    "MONTGAL": ("AL", "Montgomery"),
    "ALEXAAL": ("AL", "Cleburne"),    # Alexandria AL is in Calhoun actually - wait, Alexandria, AL is in Calhoun County
    # Actually I'm not sure about Alexandria AL - leaving as is

    # South Carolina
    "CHARLSC": ("SC", "Charleston"),
    "CHLHOLD": ("SC", "Charleston"),
    "DORCDSC": ("SC", "Dorchester"),
    "LEXINSC": ("SC", "Lexington"),
    "YORCOSC": ("SC", "York"),
    "ANDERSC": ("SC", "Anderson"),
    "PCKSNAL": ("AL", "Pickens"),
    "COAHOLD": ("SC", "Richland"),    # Columbia SC
    "COLCASC": ("SC", "Lexington"),

    # North Carolina
    "MECKLNC": ("NC", "Mecklenburg"),
    "CLTHOLD": ("NC", "Mecklenburg"),
    "CBRRSNC": ("NC", "Cabarrus"),
    "ALAMCNC": ("NC", "Alamance"),
    "GASTNNC": ("NC", "Gaston"),
    "HENDENC": ("NC", "Henderson"),
    "FORSYNC": ("NC", "Forsyth"),
    "WAKECNC": ("NC", "Wake"),
    "RDUHOLD": ("NC", "Wake"),
    "ASHECNC": ("NC", "Ashe"),

    # Tennessee
    "TNWESDF": ("TN", "Hardeman"),    # Western TN Det (Mason)
    "DAVIDTN": ("TN", "Davidson"),
    "KNXDFTN": ("TN", "Knox"),
    "KNXHOLD": ("TN", "Knox"),
    "SILERTN": ("TN", "Hamilton"),    # Silverdale (Hamilton County)
    "MEMHOLD": ("TN", "Shelby"),
    "JACKSTN": ("TN", "Madison"),
    "CNGHOLD": ("TN", "Hamilton"),    # Chattanooga

    # Kentucky
    "BOONEKY": ("KY", "Boone"),
    "OLDHAKY": ("KY", "Oldham"),
    "FAYETKY": ("KY", "Fayette"),
    "LEXFCKY": ("KY", "Fayette"),
    "GRAYSKY": ("KY", "Grayson"),
    "GRYDCKY": ("KY", "Grayson"),
    "ADAIRKY": ("KY", "Adair"),
    "LOUHOLD": ("KY", "Jefferson"),
    "BOPLEX": ("KY", "Fayette"),

    # Ohio
    "MOROWOH": ("OH", "Morrow"),
    "BUTLEOH": ("OH", "Butler"),
    "GEAUGOH": ("OH", "Geauga"),
    "UHGMCOH": ("OH", "Geauga"),
    "SENECOH": ("OH", "Seneca"),
    "PICKJOH": ("OH", "Pickaway"),
    "MAHONOH": ("OH", "Mahoning"),
    "BEDFOOH": ("OH", "Cuyahoga"),    # Bedford Hts
    "MAPLEOH": ("OH", "Cuyahoga"),    # Maple Hts
    "CCANOOH": ("OH", "Mahoning"),    # NE Ohio Corr (Youngstown)
    "BOPNEO": ("OH", "Mahoning"),
    "CLEHOLD": ("OH", "Cuyahoga"),
    "CINHOLD": ("OH", "Hamilton"),
    "CLMHOLD": ("OH", "Franklin"),

    # Michigan
    "MNROEMI": ("MI", "Monroe"),
    "CALHOMI": ("MI", "Calhoun"),     # Battle Creek
    "MSKGNMI": ("MI", "Muskegon"),
    "ELKHAIN": ("IN", "Elkhart"),
    "WASHTMI": ("MI", "Washtenaw"),
    "STCLAMI": ("MI", "St. Clair"),
    "DETHOLD": ("MI", "Wayne"),
    "DEAPDMI": ("MI", "Wayne"),
    "BHFLDMI": ("MI", "Kalamazoo"),
    "MLPHHMI": ("MI", "St. Clair"),
    "GRMHOLD": ("MI", "Kent"),        # Grand Rapids
    "KENTCMI": ("MI", "Kent"),
    "CHIPPMI": ("MI", "Chippewa"),
    "SAMBCMI": ("MI", "Wayne"),
    "MIWPRPH": ("MI", "Wayne"),       # Walter Reuther (Westland)
    "BRANCMI": ("MI", "Branch"),
    "SSMHOLD": ("MI", "Chippewa"),    # Sault Ste Marie

    # Wisconsin
    "WIDODGE": ("WI", "Dodge"),
    "DODGEWI": ("WI", "Dodge"),
    "KENOSWI": ("WI", "Kenosha"),
    "BROWNWI": ("WI", "Brown"),
    "WAUKEWI": ("WI", "Waukesha"),
    "FNDDUWI": ("WI", "Fond du Lac"),
    "DOUGLWI": ("WI", "Douglas"),
    "MILHOLD": ("WI", "Milwaukee"),

    # Illinois
    "MCHENIL": ("IL", "McHenry"),
    "KANKEIL": ("IL", "Kankakee"),
    "PULASIL": ("IL", "Pulaski"),
    "TRICOIL": ("IL", "Effingham"),   # Tri-County (Ullin) - actually Tri-County is in Pulaski
    "JEFFEIL": ("IL", "Jefferson"),
    "ELGPDIL": ("IL", "Cook"),
    "ROCKIIL": ("IL", "Rock Island"),
    "RIIHOLD": ("IL", "Rock Island"),
    "RCKISIL": ("IL", "Rock Island"),
    "BSAHOLD": ("IL", "Cook"),        # Broadview Service (Broadview = Cook)
    "CHIHOLD": ("IL", "Cook"),
    "CCHHSIL": ("IL", "Cook"),        # Cook Co Hospital
    "OGLECIL": ("IL", "Ogle"),
    "MERCEIL": ("IL", "Mercer"),
    "HLYCHIL": ("IL", "Cook"),        # Holy Cross
    "SANJAIL": ("IL", "Sangamon"),
    "ILPICKN": ("IL", "Perry"),       # Pinckneyville
    "REHOSIL": ("IL", "Cook"),        # Riveredge (Forest Park)
    "PCJDCIL": ("IL", "Peoria"),
    "RRIVRIL": ("IL", "Lee"),         # Rock River (Sterling)
    "KANECIL": ("IL", "Kane"),
    "CNTGRIL": ("IL", "McHenry"),
    "LYOLAIL": ("IL", "Cook"),        # Loyola

    # Iowa
    "POTTAIA": ("IA", "Pottawattamie"),
    "MARSHIA": ("IA", "Marshall"),
    "POLKJIA": ("IA", "Polk"),
    "DSMHOLD": ("IA", "Polk"),
    "LINNJIA": ("IA", "Linn"),
    "CRIHOLD": ("IA", "Linn"),
    "STORYIA": ("IA", "Story"),
    "BREMEIA": ("IA", "Bremer"),
    "WOODBIA": ("IA", "Woodbury"),
    "SXCHOLD": ("IA", "Woodbury"),
    "MUSCAIA": ("IA", "Muscatine"),
    "SCOTTIA": ("IA", "Scott"),
    "CHIHMIA": ("IA", "Pottawattamie"),

    # Minnesota
    "SHERBMN": ("MN", "Sherburne"),
    "CARJAMN": ("MN", "Carver"),
    "CAJUVMN": ("MN", "Carver"),
    "KANDIMN": ("MN", "Kandiyohi"),
    "FREEBMN": ("MN", "Freeborn"),
    "NOBLEMN": ("MN", "Nobles"),
    "RAADCMN": ("MN", "Ramsey"),
    "SPMHOLD": ("MN", "Ramsey"),      # St Paul Bishop Whipple
    "WAJAIMN": ("MN", "Washington"),
    "NWRCCMN": ("MN", "Polk"),        # NW Regional (Crookston)
    "ANWHMMN": ("MN", "Hennepin"),    # Abbott Northwestern
    "DULHOLD": ("MN", "St. Louis"),

    # Missouri
    "MORGNMO": ("MO", "Morgan"),
    "CHRISMO": ("MO", "Christian"),
    "MONTGMO": ("MO", "Montgomery"),
    "LINCOMO": ("MO", "Lincoln"),
    "PLATTMO": ("MO", "Platte"),
    "MISCOMO": ("MO", "Mississippi"),
    "CALDWMO": ("MO", "Caldwell"),
    "SCOTTMO": ("MO", "Scott"),
    "GREENMO": ("MO", "Greene"),
    "STLHOLD": ("MO", "St. Louis city"),
    "KANHOLD": ("MO", "Jackson"),
    "SPGHOLD": ("MO", "Greene"),
    "BOPSPG": ("MO", "Greene"),

    # Arkansas
    "LRAHOLD": ("AR", "Pulaski"),
    "WASHIAR": ("AR", "Washington"),
    "FAYHOLD": ("AR", "Washington"),
    "FSAHOLD": ("AR", "Sebastian"),
    "SEBASAR": ("AR", "Sebastian"),
    "MILLRAR": ("AR", "Miller"),      # Texarkana AR
    "TXAHOLD": ("AR", "Miller"),
    "LONPDAR": ("AR", "Lonoke"),

    # Oklahoma
    "TULCOOK": ("OK", "Tulsa"),
    "TULHOLD": ("OK", "Tulsa"),
    "OKCHOLD": ("OK", "Oklahoma"),
    "OKCOJOK": ("OK", "Oklahoma"),
    "KCOJFOK": ("OK", "Kay"),
    "GARVIOK": ("OK", "Garvin"),
    "GCLECOK": ("OK", "Grady"),
    "OKMULOK": ("OK", "Okmulgee"),
    "CHEROOK": ("OK", "Cherokee"),

    # Kansas
    "CHASEKS": ("KS", "Chase"),
    "SHACOKS": ("KS", "Shawnee"),
    "SHAJUKS": ("KS", "Shawnee"),
    "FINNEKS": ("KS", "Finney"),
    "GCPFCKS": ("KS", "Finney"),
    "RICECKS": ("KS", "Rice"),
    "WICHOLD": ("KS", "Sedgwick"),
    "BUTLEKS": ("KS", "Butler"),
    "OSAHOKS": ("KS", "Miami"),       # Osawatomie State Hospital

    # Nebraska
    "DOCORNE": ("NE", "Douglas"),
    "OMAHOLD": ("NE", "Douglas"),
    "DAKOTNE": ("NE", "Dakota"),
    "PHELPNE": ("NE", "Phelps"),
    "CASSCNE": ("NE", "Cass"),
    "SCOTTNE": ("NE", "Scotts Bluff"),
    "LINCONE": ("NE", "Lincoln"),
    "NRPHOLD": ("NE", "Lincoln"),
    "HASHENE": ("NE", "Hall"),
    "GRIHOLD": ("NE", "Hall"),
    "SARJUNE": ("NE", "Sarpy"),
    "SALINNE": ("NE", "Saline"),

    # Colorado
    "DENICDF": ("CO", "Adams"),       # GEO Aurora is in Adams County
    "DENIICO": ("CO", "Adams"),
    "DENVECO": ("CO", "Denver"),
    "DENHOLD": ("CO", "Denver"),
    "DNHMCCO": ("CO", "Denver"),
    "AURORCO": ("CO", "Adams"),
    "ELPASCO": ("CO", "El Paso"),
    "TELLECO": ("CO", "Teller"),
    "PUEHOLD": ("CO", "Pueblo"),
    "PUEBLCO": ("CO", "Pueblo"),
    "GJCHOLD": ("CO", "Mesa"),
    "MESJACO": ("CO", "Mesa"),
    "MOFFECO": ("CO", "Moffat"),
    "CRGHOLD": ("CO", "Moffat"),
    "RIOGRCO": ("CO", "Rio Grande"),
    "ALMHOLD": ("CO", "Alamosa"),
    "ALAMOCO": ("CO", "Alamosa"),
    "PARKJCO": ("CO", "Park"),
    "GSCHOLD": ("CO", "Garfield"),    # Glenwood Springs
    "EAGLECO": ("CO", "Eagle"),
    "FREMOCO": ("CO", "Fremont"),
    "DOUGLCO": ("CO", "Douglas"),
    "ARAPACO": ("CO", "Arapahoe"),
    "DURHOLD": ("CO", "La Plata"),
    "LAPLACO": ("CO", "La Plata"),
    "OTEROCO": ("CO", "Otero"),
    "CONEJCO": ("CO", "Conejos"),
    "LDFHOLD": ("CO", "Larimer"),     # Loveland
    "LARIMCO": ("CO", "Larimer"),
    "BRCHOLD": ("CO", "Morgan"),      # Brush
    "CSDHOLD": ("CO", "El Paso"),     # Colorado Springs
    "UCHUHCO": ("CO", "Denver"),
    "EMBSYCO": ("CO", "Denver"),
    "DRURYCO": ("CO", "Denver"),

    # Wyoming
    "NATROWY": ("WY", "Natrona"),
    "CSPHOLD": ("WY", "Natrona"),
    "PLATTWY": ("WY", "Platte"),
    "CHYHOLD": ("WY", "Laramie"),
    "LARCOWY": ("WY", "Laramie"),
    "TETONWY": ("WY", "Teton"),
    "SWEETWY": ("WY", "Sweetwater"),
    "FRFLDWY": ("WY", "Laramie"),

    # Montana
    "CASCAMT": ("MT", "Cascade"),
    "BILHOLD": ("MT", "Yellowstone"),
    "YELLOMT": ("MT", "Yellowstone"),
    "FLATHMT": ("MT", "Flathead"),
    "MISSOMT": ("MT", "Missoula"),
    "GALLAMT": ("MT", "Gallatin"),
    "LEWISMT": ("MT", "Lewis and Clark"),
    "DAWSOMT": ("MT", "Dawson"),
    "MUSSEMT": ("MT", "Musselshell"),
    "JEFFEMT": ("MT", "Jefferson"),
    "SHERIMT": ("MT", "Sheridan"),
    "TOOLEMT": ("MT", "Toole"),
    "HILLCMT": ("MT", "Hill"),

    # Idaho
    "HAILEID": ("ID", "Twin Falls"),
    "TFALLID": ("ID", "Twin Falls"),
    "TFIHOLD": ("ID", "Twin Falls"),
    "ELMORID": ("ID", "Elmore"),
    "ADACOID": ("ID", "Ada"),
    "BOIHOLD": ("ID", "Ada"),
    "JEFFEID": ("ID", "Jefferson"),
    "IFIHOLD": ("ID", "Bonneville"),
    "BONNEID": ("ID", "Bonneville"),
    "MADISID": ("ID", "Madison"),
    "MINICID": ("ID", "Cassia"),      # Minicassia (Burley)
    "GOODCID": ("ID", "Gooding"),

    # Utah
    "SLSLCUT": ("UT", "Salt Lake"),
    "SLCHOLD": ("UT", "Salt Lake"),
    "CACHEUT": ("UT", "Cache"),
    "WASATUT": ("UT", "Wasatch"),
    "WASHCUT": ("UT", "Washington"),
    "SGUHOLD": ("UT", "Washington"),
    "SUMMIUT": ("UT", "Summit"),
    "TOOELUT": ("UT", "Tooele"),
    "UTAHCUT": ("UT", "Utah"),
    "PRUHOLD": ("UT", "Utah"),
    "WEBERUT": ("UT", "Weber"),
    "OGUHOLD": ("UT", "Weber"),
    "UINTCUT": ("UT", "Uintah"),

    # Nevada
    "HENDENV": ("NV", "Clark"),
    "LVGHOLD": ("NV", "Clark"),
    "WASHONV": ("NV", "Washoe"),
    "RENHOLD": ("NV", "Washoe"),
    "NVSDCNV": ("NV", "Nye"),         # Nevada Southern (Pahrump)
    "NYEPANV": ("NV", "Nye"),
    "DVHSPNV": ("NV", "Nye"),
    "NOLVGNV": ("NV", "Clark"),
    "HDHSPNV": ("NV", "Clark"),
    "NNVMCNV": ("NV", "Clark"),

    # Arizona
    "FSF": ("AZ", "Pinal"),
    "FLO": ("AZ", "Pinal"),
    "EAZ": ("AZ", "Pinal"),
    "CCAFLAZ": ("AZ", "Pinal"),
    "LPLCCAZ": ("AZ", "Pinal"),
    "LPAPSAZ": ("AZ", "Pinal"),
    "CCADCAZ": ("AZ", "Pinal"),
    "PINALAZ": ("AZ", "Pinal"),
    "FLORHAZ": ("AZ", "Pinal"),
    "PHOHOLD": ("AZ", "Maricopa"),
    "MCFAJAZ": ("AZ", "Maricopa"),
    "MCMEDAZ": ("AZ", "Maricopa"),
    "VWHMCAZ": ("AZ", "Maricopa"),
    "STJOSAZ": ("AZ", "Maricopa"),
    "MVMCMAZ": ("AZ", "Maricopa"),
    "AZSPPER": ("AZ", "Maricopa"),
    "AZSPFLO": ("AZ", "Pinal"),
    "BNMCTAZ": ("AZ", "Pima"),
    "TUCHOLD": ("AZ", "Pima"),
    "PIMAJAZ": ("AZ", "Pima"),
    "BOPTCN": ("AZ", "Pima"),
    "BOPTCP": ("AZ", "Pima"),
    "STMARAZ": ("AZ", "Pima"),
    "BOPPHX": ("AZ", "Maricopa"),
    "YUMHOLD": ("AZ", "Yuma"),
    "SLRDCAZ": ("AZ", "Yuma"),        # San Luis (Yuma County)
    "LAPAZAZ": ("AZ", "La Paz"),
    "CGRMCAZ": ("AZ", "Pinal"),       # Casa Grande
    "CAMEDAZ": ("AZ", "Pinal"),
    "BIMDCAZ": ("AZ", "Pinal"),
    "YAVCVAZ": ("AZ", "Yavapai"),
    "YAVAPAZ": ("AZ", "Yavapai"),
    "COCONAZ": ("AZ", "Coconino"),
    "NAVSOAZ": ("AZ", "Navajo"),
    "APACHAZ": ("AZ", "Apache"),
    "GRAHAAZ": ("AZ", "Graham"),
    "COCHIAZ": ("AZ", "Cochise"),
    "SCRUZAZ": ("AZ", "Santa Cruz"),
    "GLEPDCA": ("CA", "Los Angeles"),
    "CHANRAZ": ("AZ", "Maricopa"),
    "AZSVCPC": ("AZ", "Pinal"),

    # New Mexico
    "OTRPCNM": ("NM", "Otero"),       # Otero Co Processing (Chaparral)
    "OTROPNM": ("NM", "Otero"),
    "OTERONM": ("NM", "Otero"),
    "TOORANM": ("NM", "Torrance"),
    "CIBOCNM": ("NM", "Cibola"),
    "CIBOLNM": ("NM", "Cibola"),
    "DONAANM": ("NM", "Dona Ana"),
    "MCKINNM": ("NM", "McKinley"),
    "SANDONM": ("NM", "Sandoval"),
    "SANMINM": ("NM", "San Miguel"),
    "SJUANNM": ("NM", "San Juan"),
    "SANTANM": ("NM", "Santa Fe"),
    "SFCORNM": ("NM", "Santa Fe"),
    "LEACONM": ("NM", "Lea"),
    "EDDCONM": ("NM", "Eddy"),
    "CURRYNM": ("NM", "Curry"),
    "CHAVENM": ("NM", "Chaves"),
    "RSWHOLD": ("NM", "Chaves"),
    "ARTSINM": ("NM", "Eddy"),
    "ARTESNM": ("NM", "Eddy"),
    "LASHOLD": ("NM", "Dona Ana"),    # Las Cruces
    "ABQHOLD": ("NM", "Bernalillo"),
    "PRSHANM": ("NM", "Bernalillo"),
    "HIDALNM": ("NM", "Hidalgo"),

    # California - SoCal
    "CCASDCA": ("CA", "San Diego"),   # Otay Mesa
    "SOBAYCA": ("CA", "San Diego"),   # South Bay
    "SDPROCA": ("CA", "San Diego"),
    "SNDCOCA": ("CA", "San Diego"),
    "SDHOSCA": ("CA", "San Diego"),
    "BOPSDC": ("CA", "San Diego"),
    "WCCSDCA": ("CA", "San Diego"),
    "EMESACA": ("CA", "San Diego"),
    "VISTACA": ("CA", "San Diego"),
    "CASSJCA": ("CA", "San Diego"),
    "BAILECA": ("CA", "San Diego"),
    "JHALLCA": ("CA", "San Diego"),
    "SCVMCCA": ("CA", "San Diego"),
    "PVLYHCA": ("CA", "San Diego"),
    "UCSDHCA": ("CA", "San Diego"),
    "HISDBCA": ("CA", "San Diego"),
    "BWDGICA": ("CA", "San Diego"),
    "CACFMES": ("CA", "Kern"),        # Mesa Verde
    "GLDSACA": ("CA", "Kern"),        # Golden State Annex
    "CADESVI": ("CA", "Kern"),        # Desert View
    "BKLHOLD": ("CA", "Kern"),        # Bakersfield
    "KERCOCA": ("CA", "Kern"),
    "KERNHCA": ("CA", "Kern"),
    "ADLNTCA": ("CA", "San Bernardino"),  # Adelanto
    "SBDHOLD": ("CA", "San Bernardino"),
    "SBERNCA": ("CA", "San Bernardino"),
    "ARRMCCA": ("CA", "San Bernardino"),
    "DSRTVCA": ("CA", "San Bernardino"),
    "VVGMCCA": ("CA", "San Bernardino"),
    "WMHOSCA": ("CA", "Los Angeles"), # White Memorial
    "LANCACA": ("CA", "Los Angeles"), # Mira Loma in Lancaster
    "LOSCJCA": ("CA", "Los Angeles"), # LA Co Jail
    "BARRECA": ("CA", "Los Angeles"),
    "LOSHOLD": ("CA", "Los Angeles"),
    "BOPLOS": ("CA", "Los Angeles"),
    "ALHAMCA": ("CA", "Los Angeles"),
    "BHCALCA": ("CA", "Los Angeles"), # Alhambra BHC
    "POMONCA": ("CA", "Los Angeles"),
    "TEMPLCA": ("CA", "Los Angeles"),
    "PASADCA": ("CA", "Los Angeles"),
    "LPD77CA": ("CA", "Los Angeles"),
    "PLRMCCA": ("CA", "Los Angeles"),
    "PALMDCA": ("CA", "Los Angeles"),
    "TLACYCA": ("CA", "Orange"),      # Theo Lacy
    "MUSIKCA": ("CA", "Orange"),      # James A Musick
    "OCIRCCA": ("CA", "Orange"),
    "OCCWJCA": ("CA", "Orange"),
    "WSTMCCA": ("CA", "Orange"),      # Western Med (Santa Ana)
    "OGCMCCA": ("CA", "Orange"),
    "AGMDCCA": ("CA", "Orange"),      # Anaheim Global
    "COSTACA": ("CA", "Orange"),
    "WESHOLD": ("CA", "Orange"),      # Westminster
    "SAAHOLD": ("CA", "Orange"),      # Santa Ana DRO
    "SACITCA": ("CA", "Orange"),      # Santa Ana City
    "IRADFCA": ("CA", "Imperial"),
    "ECC": ("CA", "Imperial"),
    "IMPCOCA": ("CA", "Imperial"),
    "IMPHOLD": ("CA", "Imperial"),
    "CADCCAL": ("CA", "Imperial"),    # CDC Calipatria
    "VENTUCA": ("CA", "Ventura"),
    "VENHOLD": ("CA", "Ventura"),
    "STMARCA": ("CA", "Ventura"),
    "SBARBCA": ("CA", "Santa Barbara"),
    "BOPLOM": ("CA", "Santa Barbara"),  # Lompoc USP
    "BOPLOF": ("CA", "Santa Barbara"),  # Lompoc FCI
    "SLOBICA": ("CA", "San Luis Obispo"),
    "SLJUVCA": ("CA", "San Luis Obispo"),
    "ENLMCCA": ("CA", "Butte"),       # Enloe Med (Chico)
    "REDHOLD": ("CA", "Shasta"),      # Redding

    # California - NorCal
    "CACFDON": ("CA", "San Diego"),   # RJ Donovan
    "SFRHOLD": ("CA", "San Francisco"),
    "RIOCCCA": ("CA", "Sacramento"),
    "SACHOLD": ("CA", "Sacramento"),
    "SACRACA": ("CA", "Sacramento"),
    "CASPSAC": ("CA", "Sacramento"),
    "SCNORCA": ("CA", "Santa Clara"),
    "FRECOCA": ("CA", "Fresno"),
    "FREHOLD": ("CA", "Fresno"),
    "CRMCFCA": ("CA", "Fresno"),
    "YUBAJCA": ("CA", "Yuba"),
    "CONWECA": ("CA", "Contra Costa"),
    "CONCOCA": ("CA", "Contra Costa"),
    "CACFLEO": ("CA", "Yuba"),        # CCF Leo Chesney (Live Oak/Sutter, but treat as Yuba)
    "RIVERCA": ("CA", "Riverside"),
    "CACTYCA": ("CA", "Kern"),        # Cal City Corrections (Kern)
    "CAIRONW": ("CA", "Riverside"),   # Ironwood (Blythe)
    "CAWVALL": ("CA", "Riverside"),
    "CAMENCW": ("CA", "San Luis Obispo"),
    "CAMENCE": ("CA", "San Luis Obispo"),
    "CCJAMA": ("CA", "Tehama"),       # SCC/Jamestown - actually Tuolumne
    "CACCJAM": ("CA", "Tuolumne"),
    "LASWOCA": ("CA", "San Diego"),
    "BPS": ("CA", "Imperial"),
    "STK": ("CA", "San Joaquin"),     # Stockton Staging

    # Pacific NW
    "CSCNWWA": ("WA", "Pierce"),      # NW ICE Processing (Tacoma)
    "SEAHOLD": ("WA", "King"),
    "BOPSET": ("WA", "King"),         # SeaTac FDC
    "FPSSAWA": ("WA", "King"),
    "YIKIMWA": ("WA", "Yakima"),
    "YAKHOLD": ("WA", "Yakima"),
    "CHELAWA": ("WA", "Chelan"),
    "WNTHOLD": ("WA", "Chelan"),      # Wenatchee
    "OKANOWA": ("WA", "Okanogan"),
    "KITTIWA": ("WA", "Kittitas"),
    "STEVEWA": ("WA", "Stevens"),
    "ECOLOWA": ("WA", "Yakima"),
    "RRFINWA": ("WA", "Yakima"),
    "ADAMSWA": ("WA", "Adams"),
    "COWJVWA": ("WA", "Cowlitz"),
    "FDLHOLD": ("WA", "Whatcom"),     # Ferndale
    "BLHHOLD": ("WA", "Whatcom"),     # Bellingham
    "SUNNYWA": ("WA", "Yakima"),      # Sunnyside
    "RICHOLD": ("WA", "Benton"),      # Richland (Benton County)
    "SPOHOLD": ("WA", "Spokane"),

    "NORCOOR": ("OR", "Umatilla"),    # Northern Oregon Corr (The Dalles - Wasco)
    "NOJUVOR": ("OR", "Wasco"),
    "JOSEPOR": ("OR", "Josephine"),
    "JACKSOR": ("OR", "Jackson"),
    "KLAMCOR": ("OR", "Klamath"),
    "MARICOR": ("OR", "Marion"),
    "LANECOR": ("OR", "Lane"),
    "EUGHOLD": ("OR", "Lane"),
    "COOSCOR": ("OR", "Coos"),
    "DOUGLOR": ("OR", "Douglas"),
    "LINNCOR": ("OR", "Linn"),
    "UMATCOR": ("OR", "Umatilla"),
    "COLUMOR": ("OR", "Columbia"),
    "SPRNGOR": ("OR", "Lane"),        # Springfield
    "BOPSHE": ("OR", "Yamhill"),      # Sheridan FCI

    # Alaska
    "AKCOOKI": ("AK", "Anchorage"),
    "ANCHOAK": ("AK", "Anchorage"),
    "ANCHOLD": ("AK", "Anchorage"),
    "AKHIGHL": ("AK", "Anchorage"),   # Highland Mt CC (Eagle River)
    "AKLEMON": ("AK", "Juneau"),      # Lemon Creek
    "SITKAAK": ("AK", "Sitka"),
    "AKKETCH": ("AK", "Ketchikan Gateway"),
    "AKFAIRB": ("AK", "Fairbanks North Star"),
    "AKPALMC": ("AK", "Matanuska-Susitna"),
    "AKWILPT": ("AK", "Kenai Peninsula"),  # Wildwood Pre-Trial
    "AKWILCC": ("AK", "Kenai Peninsula"),
    "AKGSCCC": ("AK", "Matanuska-Susitna"),  # Goose Creek
    "KODIAAK": ("AK", "Kodiak Island"),

    # Hawaii
    "BOPHON": ("HI", "Honolulu"),
    "HHWHOLD": ("HI", "Honolulu"),
    "PMMCAHI": ("HI", "Honolulu"),

    # Puerto Rico / VI / Guam / MP
    "AGC": ("PR", "Aguadilla"),       # Aguadilla SPC
    "SJS": ("PR", "Bayamon"),         # San Juan Staging (Bayamon)
    "BOPGUA": ("PR", "Guaynabo"),
    "BAYAMPR": ("PR", "Bayamon"),
    "PAVHRPR": ("PR", "San Juan"),
    "HOSPSPR": ("PR", "San Juan"),
    "CMEDHPR": ("PR", "Bayamon"),
    "PRVEGAL": ("PR", "Vega Alta"),
    "AIRHOPR": ("PR", "Carolina"),    # San Juan Airport
    "SAJHOLD": ("PR", "San Juan"),
    "SJUHOLD": ("PR", "Carolina"),
    "GUDOCHG": ("GU", "Guam"),
    "DEPCOGU": ("GU", "Guam"),
    "AGAHOLD": ("GU", "Guam"),
    "STTCJVI": ("VI", "St. Thomas"),
    "CHAHOLD": ("VI", "St. Thomas"),
    "MPSIPAN": ("MP", "Saipan"),
    "SAIHOLD": ("MP", "Saipan"),

    # Federal BOP facilities
    "BOPDAL": ("TX", "Childress"),    # Dalby (Post is in Garza, but Dalby is in Post which is Garza). Actually Dalby Correctional is in Post, TX = Garza County.
    "BOPMCR": ("KY", "McCreary"),
    "BOPTRV": ("TX", "Live Oak"),     # Three Rivers FCI
    "BOPVIM": ("CA", "San Bernardino"),  # Victorville
    "BOPSDC": ("CA", "San Diego"),
    "BOPSPG": ("MO", "Greene"),
    "BOPGIL": ("WV", "Gilmer"),
    "BOPALM": ("PA", "Union"),        # Allenwood
    "BOPTHA": ("IN", "Vigo"),         # Terre Haute
    "BOPPOL": ("LA", "Grant"),        # Pollock USP
    "BOPLEM": ("PA", "Union"),
    "BOPRBK": ("NY", "Essex"),        # Ray Brook
    "BOPPET": ("VA", "Dinwiddie"),    # Petersburg

    # Other
    "DESERFL": ("FL", "Polk"),
    "WINWYAZ": ("AZ", "Pinal"),
    "RDRVHTX": ("TX", "Wichita"),     # Red River (Wichita Falls)
    "PKLDHTX": ("TX", "Dallas"),      # Parkland
    "LAURITX": ("TX", "Bexar"),       # Laurel Ridge
    "PLMBHTX": ("TX", "Bexar"),       # Palms BH
    "LIMMCTX": ("TX", "Limestone"),
    "LIMESTX": ("TX", "Limestone"),
    "LIMCJTX": ("TX", "Limestone"),
    "WOAKSTX": ("TX", "Harris"),      # West Oaks (Houston)
    "RVBHHTX": ("TX", "El Paso"),     # Rio Vista BH
    "LRDMCTX": ("TX", "Webb"),
    "ASWHRTX": ("TX", "Williamson"),  # Ascension Seton Williamson
    "CCHRTTX": ("TX", "Bell"),        # Cedar Crest (Belton/Killeen)
    "BFGHITX": ("TX", "Bexar"),       # Byrd's Foster Grp Home (San Antonio)
    "TRYOSCA": ("CA", "San Bernardino"),  # Trinity Youth Svcs
    "NIXHCTX": ("TX", "Bexar"),       # Nix Home Care (San Antonio)
    "LLUMCCA": ("CA", "San Bernardino"),  # Loma Linda
    "GSAMHCA": ("CA", "Los Angeles"), # Good Samaritan
    "CWHCCMP": ("MP", "Saipan"),      # Commonwealth Healthcare (CNMI)
    "PIERCND": ("ND", "Pierce"),
    "GFCORND": ("ND", "Grand Forks"),
    "GRFHOLD": ("ND", "Grand Forks"),
    "GFJUVND": ("ND", "Grand Forks"),
    "WARDCND": ("ND", "Ward"),
    "BURLEND": ("ND", "Burleigh"),
    "STUTSND": ("ND", "Stutsman"),
    "CASSCND": ("ND", "Cass"),
    "BOTTIND": ("ND", "Bottineau"),
    "MOUNTND": ("ND", "Mountrail"),
    "WALSHND": ("ND", "Walsh"),
    "HACTCND": ("ND", "Cass"),        # Heart of America (Mandan = Morton actually) - hmm
    "PENNISD": ("SD", "Pennington"),
    "RPCHOLD": ("SD", "Pennington"),
    "MINNESD": ("SD", "Minnehaha"),
    "SFDHOLD": ("SD", "Minnehaha"),
    "ROBERSD": ("SD", "Roberts"),
    "MEADESD": ("SD", "Meade"),
    "YANCOSD": ("SD", "Yankton"),
    "BROWNSD": ("SD", "Brown"),
    "UNIONSD": ("SD", "Union"),
    "TURNESD": ("SD", "Turner"),

    # NC
    "NCWESDF": ("NC", "Anson"),
    "GRRHOLD": ("SC", "Greenville"),  # Greer

    "ALAMOCO": ("CO", "Alamosa"),

    # Oregon (already listed above)
    # WA (already listed)
}


# Patterns: facility-name keyword that uniquely identifies a county.
# Used when the code-based lookup misses but the name is distinctive.
KNOWN_NAME_KEYWORDS: list[tuple[str, str, str]] = [
    # (regex, state_abbr, county_name)
    (r"PORT\s+ISABEL", "TX", "Cameron"),
    (r"FLORENCE\s+(SPC|STAGING|SERVICE)", "AZ", "Pinal"),
    (r"ELOY", "AZ", "Pinal"),
    (r"\bELOY\b", "AZ", "Pinal"),
    (r"ADELANTO", "CA", "San Bernardino"),
    (r"OTAY\s+MESA", "CA", "San Diego"),
    (r"MESA\s+VERDE", "CA", "Kern"),
    (r"GOLDEN\s+STATE\s+ANNEX", "CA", "Kern"),
    (r"DESERT\s+VIEW\s+ANNEX", "CA", "Kern"),
    (r"\bDILLEY\b", "TX", "Frio"),
    (r"PEARSALL", "TX", "Frio"),
    (r"SOUTH\s+TEXAS\s+(ICE|FAM)", "TX", "Frio"),
    (r"KARNES", "TX", "Karnes"),
    (r"JOE\s+CORLEY", "TX", "Montgomery"),
    (r"IAH\s+SECURE", "TX", "Polk"),
    (r"\bPOLK\b", "TX", "Polk"),
    (r"ALEXANDRIA\s+STAGING", "LA", "Rapides"),
    (r"OAKDALE", "LA", "Allen"),
    (r"PINE\s+PRAIRIE", "LA", "Evangeline"),
    (r"\bJENA\b", "LA", "LaSalle"),
    (r"WINNFIELD|\bWINN\s+CORR", "LA", "Winn"),
    (r"RICHWOOD", "LA", "Ouachita"),
    (r"BASILE", "LA", "Acadia"),
    (r"STEWART\s+DETENTION", "GA", "Stewart"),
    (r"FOLKSTON", "GA", "Charlton"),
    (r"IRWIN\s+COUNTY", "GA", "Irwin"),
    (r"MOSHANNON", "PA", "Clearfield"),
    (r"BERKS\s+COUNTY", "PA", "Berks"),
    (r"YORK\s+COUNTY\s+(JAIL|PRISON|DET).*PA", "PA", "York"),
    (r"BUFFALO\s+SPC|BATAVIA", "NY", "Genesee"),
    (r"VARICK", "NY", "New York"),
    (r"VARRICK", "NY", "New York"),
    (r"ELIZABETH\s+CONTRACT", "NJ", "Union"),
    (r"DELANEY\s+HALL", "NJ", "Essex"),
    (r"BOSTON\s+SPC", "MA", "Suffolk"),
    (r"PLYMOUTH\s+CO", "MA", "Plymouth"),
    (r"BRISTOL.*DARTMOUTH", "MA", "Bristol"),
    (r"KROME", "FL", "Miami-Dade"),
    (r"BROWARD\s+TRANSITIONAL", "FL", "Broward"),
    (r"GLADES\s+COUNTY|GLADES\s+DET", "FL", "Glades"),
    (r"WAKULLA", "FL", "Wakulla"),
    (r"CIBOLA", "NM", "Cibola"),
    (r"OTERO\s+(CO|COUNTY|PROCESSING)", "NM", "Otero"),
    (r"TORRANCE.*\bNM\b|TORRANCE/ESTANCIA", "NM", "Torrance"),
    (r"NW\s+ICE\s+PROCESSING|NORTHWEST\s+ICE\s+PROC|TACOMA", "WA", "Pierce"),
    (r"PRAIRIELAND", "TX", "Johnson"),
    (r"BLUEBONNET\s+DET", "TX", "Anderson"),
    (r"COASTAL\s+BEND", "TX", "Nueces"),
    (r"SAN\s+LUIS\s+REGIONAL", "AZ", "Yuma"),
    (r"WEST\s+TEXAS\s+DET", "TX", "Hudspeth"),
    (r"MONTGOMERY\s+CO.*JAIL|MONTGOMERY\s+PROCESSING", "TX", "Montgomery"),
    (r"VAL\s+VERDE", "TX", "Val Verde"),
    (r"WILLACY", "TX", "Willacy"),
    (r"\bRAYMONDVILLE\b", "TX", "Willacy"),
    (r"EAST\s+HIDALGO", "TX", "Hidalgo"),
    (r"RIO\s+GRANDE\s+DET", "TX", "Webb"),
    (r"LAREDO\s+(PROC|DET)", "TX", "Webb"),
    (r"BROOKS\s+COUNTY", "TX", "Brooks"),
    (r"LA\s+SALLE\s+CO\s+REG", "TX", "La Salle"),
    (r"HASKELL\s+CO|ROLLING\s+PLAINS", "TX", "Haskell"),
    (r"RIO\s+GRANDE\s+VALLEY\s+STAGING", "TX", "Hidalgo"),
    (r"\bDIMMIT\s+REG", "TX", "Dimmit"),
    (r"\bWEBB\s+CO", "TX", "Webb"),
    (r"\bHUDSPETH\b", "TX", "Hudspeth"),
    (r"GUAM", "GU", "Guam"),
    (r"SAIPAN", "MP", "Saipan"),
    (r"AGUADILLA", "PR", "Aguadilla"),
    (r"VEGA\s+ALTA", "PR", "Vega Alta"),
    (r"BAYAMON", "PR", "Bayamon"),
    (r"GUAYNABO", "PR", "Guaynabo"),
]


# City → (state, county). Used for hold rooms named "{CITY} HOLD ROOM".
# The keys are uppercase city names as they appear in the facility names.
CITY_COUNTY_HINTS: dict[str, tuple[str, str]] = {
    # Texas
    "DALLAS": ("TX", "Dallas"),
    "HOUSTON": ("TX", "Harris"),
    "SAN ANTONIO": ("TX", "Bexar"),
    "AUSTIN": ("TX", "Travis"),
    "EL PASO": ("TX", "El Paso"),
    "HARLINGEN": ("TX", "Cameron"),
    "PORT ISABEL": ("TX", "Cameron"),
    "BROWNSVILLE": ("TX", "Cameron"),
    "MCALLEN": ("TX", "Hidalgo"),
    "EDINBURG": ("TX", "Hidalgo"),
    "LAREDO": ("TX", "Webb"),
    "PEARSALL": ("TX", "Frio"),
    "DILLEY": ("TX", "Frio"),
    "CONROE": ("TX", "Montgomery"),
    "AMARILLO": ("TX", "Potter"),
    "LUBBOCK": ("TX", "Lubbock"),
    "MIDLAND": ("TX", "Midland"),
    "ABILENE": ("TX", "Taylor"),
    "SAN ANGELO": ("TX", "Tom Green"),
    "WACO": ("TX", "McLennan"),
    "EULESS": ("TX", "Tarrant"),
    "BEDFORD": ("TX", "Tarrant"),
    "FORT WORTH": ("TX", "Tarrant"),
    "PECOS": ("TX", "Reeves"),
    "ODESSA": ("TX", "Ector"),
    "CORPUS CHRISTI": ("TX", "Nueces"),
    "VICTORIA": ("TX", "Victoria"),
    "DEL RIO": ("TX", "Val Verde"),
    "BIG SPRING": ("TX", "Howard"),
    "BIG SPRINGS": ("TX", "Howard"),
    "TYLER": ("TX", "Smith"),
    "BEAUMONT": ("TX", "Jefferson"),
    "GALVESTON": ("TX", "Galveston"),
    "RAYMONDVILLE": ("TX", "Willacy"),
    "LIVINGSTON": ("TX", "Polk"),
    "EAGLE PASS": ("TX", "Maverick"),
    "ATHENS": ("TX", "Henderson"),
    # New Mexico
    "ALBUQUERQUE": ("NM", "Bernalillo"),
    "LAS CRUCES": ("NM", "Dona Ana"),
    "ROSWELL": ("NM", "Chaves"),
    "ARTESIA": ("NM", "Eddy"),
    "SANTA FE": ("NM", "Santa Fe"),
    # Arizona
    "PHOENIX": ("AZ", "Maricopa"),
    "TUCSON": ("AZ", "Pima"),
    "FLORENCE": ("AZ", "Pinal"),
    "ELOY": ("AZ", "Pinal"),
    "YUMA": ("AZ", "Yuma"),
    "CASA GRANDE": ("AZ", "Pinal"),
    "FLAGSTAFF": ("AZ", "Coconino"),
    "MESA": ("AZ", "Maricopa"),
    "SCOTTSDALE": ("AZ", "Maricopa"),
    "TEMPE": ("AZ", "Maricopa"),
    # California
    "LOS ANGELES": ("CA", "Los Angeles"),
    "SAN DIEGO": ("CA", "San Diego"),
    "SAN FRANCISCO": ("CA", "San Francisco"),
    "SAN JOSE": ("CA", "Santa Clara"),
    "SACRAMENTO": ("CA", "Sacramento"),
    "FRESNO": ("CA", "Fresno"),
    "BAKERSFIELD": ("CA", "Kern"),
    "STOCKTON": ("CA", "San Joaquin"),
    "OAKLAND": ("CA", "Alameda"),
    "SAN BERNARDINO": ("CA", "San Bernardino"),
    "RIVERSIDE": ("CA", "Riverside"),
    "VENTURA": ("CA", "Ventura"),
    "SANTA ANA": ("CA", "Orange"),
    "WESTMINSTER": ("CA", "Orange"),
    "ANAHEIM": ("CA", "Orange"),
    "EL CENTRO": ("CA", "Imperial"),
    "REDDING": ("CA", "Shasta"),
    "ADELANTO": ("CA", "San Bernardino"),
    "LANCASTER": ("CA", "Los Angeles"),
    "BLYTHE": ("CA", "Riverside"),
    "CALEXICO": ("CA", "Imperial"),
    "CALIPATRIA": ("CA", "Imperial"),
    "LOMPOC": ("CA", "Santa Barbara"),
    "VICTORVILLE": ("CA", "San Bernardino"),
    # Florida
    "MIAMI": ("FL", "Miami-Dade"),
    "ORLANDO": ("FL", "Orange"),
    "TAMPA": ("FL", "Hillsborough"),
    "JACKSONVILLE": ("FL", "Duval"),
    "TALLAHASSEE": ("FL", "Leon"),
    "FORT MYERS": ("FL", "Lee"),
    "FT MYERS": ("FL", "Lee"),
    "PENSACOLA": ("FL", "Escambia"),
    "BRADENTON": ("FL", "Manatee"),
    "WEST PALM BEACH": ("FL", "Palm Beach"),
    "STUART": ("FL", "Martin"),
    "MIRAMAR": ("FL", "Broward"),
    "FOLKSTON": ("GA", "Charlton"),
    "MOORE HAVEN": ("FL", "Glades"),
    "DANIA BEACH": ("FL", "Broward"),
    # Georgia
    "ATLANTA": ("GA", "Fulton"),
    "SAVANNAH": ("GA", "Chatham"),
    "GAINESVILLE": ("GA", "Hall"),
    "MACON": ("GA", "Bibb"),
    "DALTON": ("GA", "Whitfield"),
    "STEWART": ("GA", "Stewart"),
    # Alabama
    "BIRMINGHAM": ("AL", "Jefferson"),
    "MOBILE": ("AL", "Mobile"),
    "MONTGOMERY": ("AL", "Montgomery"),
    "ETOWAH": ("AL", "Etowah"),
    # Mississippi
    "JACKSON": ("MS", "Hinds"),
    "GULFPORT": ("MS", "Harrison"),
    "ADAMS": ("MS", "Adams"),
    # Louisiana
    "NEW ORLEANS": ("LA", "Orleans"),
    "BATON ROUGE": ("LA", "East Baton Rouge"),
    "ALEXANDRIA": ("LA", "Rapides"),
    "JENA": ("LA", "LaSalle"),
    "WINN": ("LA", "Winn"),
    "WINNFIELD": ("LA", "Winn"),
    "OAKDALE": ("LA", "Allen"),
    "PINE PRAIRIE": ("LA", "Evangeline"),
    "RICHWOOD": ("LA", "Ouachita"),
    "LAFAYETTE": ("LA", "Lafayette"),
    "SHREVEPORT": ("LA", "Caddo"),
    "MONROE": ("LA", "Ouachita"),
    # New York
    "NEW YORK": ("NY", "New York"),
    "MANHATTAN": ("NY", "New York"),
    "BUFFALO": ("NY", "Erie"),
    "BATAVIA": ("NY", "Genesee"),
    "ALBANY": ("NY", "Albany"),
    "SYRACUSE": ("NY", "Onondaga"),
    "ROCHESTER": ("NY", "Monroe"),
    "FISHKILL": ("NY", "Dutchess"),
    "RAY BROOK": ("NY", "Essex"),
    "BROOKLYN": ("NY", "Kings"),
    "BRONX": ("NY", "Bronx"),
    "QUEENS": ("NY", "Queens"),
    "STATEN ISLAND": ("NY", "Richmond"),
    "CHAMPLAIN": ("NY", "Clinton"),
    "RIKERS": ("NY", "Bronx"),
    "WHITE PLAINS": ("NY", "Westchester"),
    "CENTRAL ISLIP": ("NY", "Suffolk"),
    "LONG ISLAND": ("NY", "Suffolk"),
    "NEWBURGH": ("NY", "Orange"),
    # New Jersey
    "ELIZABETH": ("NJ", "Union"),
    "NEWARK": ("NJ", "Essex"),
    "JERSEY CITY": ("NJ", "Hudson"),
    "BERGEN": ("NJ", "Bergen"),
    "ESSEX": ("NJ", "Essex"),
    "HUDSON": ("NJ", "Hudson"),
    "MOUNT LAUREL": ("NJ", "Burlington"),
    "MT. LAUREL": ("NJ", "Burlington"),
    "MT LAUREL": ("NJ", "Burlington"),
    # PA
    "PHILADELPHIA": ("PA", "Philadelphia"),
    "PITTSBURGH": ("PA", "Allegheny"),
    "PITTSBURG": ("PA", "Allegheny"),
    "YORK": ("PA", "York"),
    "WILLIAMSPORT": ("PA", "Lycoming"),
    "ALLENTOWN": ("PA", "Lehigh"),
    "ERIE": ("PA", "Erie"),
    # Maryland / DC
    "BALTIMORE": ("MD", "Baltimore city"),
    "WASHINGTON": ("DC", "District of Columbia"),
    # Virginia
    "RICHMOND": ("VA", "Richmond city"),
    "ROANOKE": ("VA", "Roanoke city"),
    "NORFOLK": ("VA", "Norfolk city"),
    "ALEXANDRIA, VA": ("VA", "Alexandria city"),
    "FARMVILLE": ("VA", "Prince Edward"),
    "HARRISONBURG": ("VA", "Harrisonburg city"),
    "FAIRFAX": ("VA", "Fairfax"),
    "VIRGINIA BEACH": ("VA", "Virginia Beach city"),
    # Massachusetts
    "BOSTON": ("MA", "Suffolk"),
    "WORCESTER": ("MA", "Worcester"),
    "SPRINGFIELD, MA": ("MA", "Hampden"),
    "BRIDGEWATER": ("MA", "Plymouth"),
    "BARNSTABLE": ("MA", "Barnstable"),
    # Connecticut
    "HARTFORD": ("CT", "Hartford"),
    "NEW HAVEN": ("CT", "New Haven"),
    # Rhode Island
    "PROVIDENCE": ("RI", "Providence"),
    # NH
    "MANCHESTER": ("NH", "Hillsborough"),
    "DOVER, NH": ("NH", "Strafford"),
    # Vermont
    "ST. ALBANS": ("VT", "Franklin"),
    "ST ALBANS": ("VT", "Franklin"),
    "BURLINGTON, VT": ("VT", "Chittenden"),
    # Maine
    "PORTLAND, ME": ("ME", "Cumberland"),
    "BANGOR": ("ME", "Penobscot"),
    # Delaware
    "DOVER": ("DE", "Kent"),
    "WILMINGTON, DE": ("DE", "New Castle"),
    # Washington State
    "SEATTLE": ("WA", "King"),
    "TACOMA": ("WA", "Pierce"),
    "SPOKANE": ("WA", "Spokane"),
    "RICHLAND": ("WA", "Benton"),
    "WENATCHEE": ("WA", "Chelan"),
    "YAKIMA": ("WA", "Yakima"),
    "FERNDALE": ("WA", "Whatcom"),
    "BELLINGHAM": ("WA", "Whatcom"),
    # Oregon
    "PORTLAND, OR": ("OR", "Multnomah"),
    "PORTLAND": ("OR", "Multnomah"),  # default
    "EUGENE": ("OR", "Lane"),
    "SALEM": ("OR", "Marion"),
    "MEDFORD": ("OR", "Jackson"),
    "BEND": ("OR", "Deschutes"),
    "SHERIDAN": ("OR", "Yamhill"),
    # Idaho
    "BOISE": ("ID", "Ada"),
    "TWIN FALLS": ("ID", "Twin Falls"),
    "IDAHO FALLS": ("ID", "Bonneville"),
    # Utah
    "SALT LAKE CITY": ("UT", "Salt Lake"),
    "PROVO": ("UT", "Utah"),
    "OGDEN": ("UT", "Weber"),
    "ST. GEORGE": ("UT", "Washington"),
    "ST GEORGE": ("UT", "Washington"),
    # Nevada
    "LAS VEGAS": ("NV", "Clark"),
    "RENO": ("NV", "Washoe"),
    "HENDERSON": ("NV", "Clark"),
    "PAHRUMP": ("NV", "Nye"),
    # Wyoming
    "CHEYENNE": ("WY", "Laramie"),
    "CASPER": ("WY", "Natrona"),
    "CASPAR": ("WY", "Natrona"),
    # Montana
    "BILLINGS": ("MT", "Yellowstone"),
    "HELENA": ("MT", "Lewis and Clark"),
    "MISSOULA": ("MT", "Missoula"),
    "GREAT FALLS": ("MT", "Cascade"),
    # Colorado
    "DENVER": ("CO", "Denver"),
    "AURORA": ("CO", "Adams"),
    "COLORADO SPRINGS": ("CO", "El Paso"),
    "GRAND JUNCTION": ("CO", "Mesa"),
    "PUEBLO": ("CO", "Pueblo"),
    "GLENWOOD SPRINGS": ("CO", "Garfield"),
    "ALAMOSA": ("CO", "Alamosa"),
    "DURANGO": ("CO", "La Plata"),
    "CRAIG": ("CO", "Moffat"),
    "LOVELAND": ("CO", "Larimer"),
    "BRUSH": ("CO", "Morgan"),
    "FREDERICK": ("CO", "Weld"),
    "FORT COLLINS": ("CO", "Larimer"),
    # North/South Dakota
    "FARGO": ("ND", "Cass"),
    "GRAND FORKS": ("ND", "Grand Forks"),
    "BISMARCK": ("ND", "Burleigh"),
    "MINOT": ("ND", "Ward"),
    "RAPID CITY": ("SD", "Pennington"),
    "SIOUX FALLS": ("SD", "Minnehaha"),
    "SIOUX CITY": ("IA", "Woodbury"),
    "ABERDEEN": ("SD", "Brown"),
    # Nebraska
    "OMAHA": ("NE", "Douglas"),
    "LINCOLN": ("NE", "Lancaster"),
    "GRAND ISLAND": ("NE", "Hall"),
    "NORTH PLATTE": ("NE", "Lincoln"),
    # Iowa
    "DES MOINES": ("IA", "Polk"),
    "CEDAR RAPIDS": ("IA", "Linn"),
    "DAVENPORT": ("IA", "Scott"),
    # Minnesota
    "MINNEAPOLIS": ("MN", "Hennepin"),
    "ST. PAUL": ("MN", "Ramsey"),
    "ST PAUL": ("MN", "Ramsey"),
    "DULUTH": ("MN", "St. Louis"),
    "ROCHESTER, MN": ("MN", "Olmsted"),
    # Wisconsin
    "MILWAUKEE": ("WI", "Milwaukee"),
    "MADISON": ("WI", "Dane"),
    "GREEN BAY": ("WI", "Brown"),
    "KENOSHA": ("WI", "Kenosha"),
    "WAUKESHA": ("WI", "Waukesha"),
    "JUNEAU, WI": ("WI", "Dodge"),
    # Illinois
    "CHICAGO": ("IL", "Cook"),
    "BROADVIEW": ("IL", "Cook"),
    "ROCKFORD": ("IL", "Winnebago"),
    "ROCK ISLAND": ("IL", "Rock Island"),
    "PEORIA": ("IL", "Peoria"),
    "SPRINGFIELD, IL": ("IL", "Sangamon"),
    "ELGIN": ("IL", "Cook"),
    # Indiana
    "INDIANAPOLIS": ("IN", "Marion"),
    "FORT WAYNE": ("IN", "Allen"),
    "EVANSVILLE": ("IN", "Vanderburgh"),
    # Ohio
    "COLUMBUS": ("OH", "Franklin"),
    "CLEVELAND": ("OH", "Cuyahoga"),
    "CINCINNATI": ("OH", "Hamilton"),
    "TOLEDO": ("OH", "Lucas"),
    "DAYTON": ("OH", "Montgomery"),
    "AKRON": ("OH", "Summit"),
    "YOUNGSTOWN": ("OH", "Mahoning"),
    # Michigan
    "DETROIT": ("MI", "Wayne"),
    "GRAND RAPIDS": ("MI", "Kent"),
    "LANSING": ("MI", "Ingham"),
    "ANN ARBOR": ("MI", "Washtenaw"),
    "BATTLE CREEK": ("MI", "Calhoun"),
    "MONROE, MI": ("MI", "Monroe"),
    # Kentucky
    "LOUISVILLE": ("KY", "Jefferson"),
    "LEXINGTON": ("KY", "Fayette"),
    "BOWLING GREEN": ("KY", "Warren"),
    # Tennessee
    "NASHVILLE": ("TN", "Davidson"),
    "MEMPHIS": ("TN", "Shelby"),
    "KNOXVILLE": ("TN", "Knox"),
    "CHATTANOOGA": ("TN", "Hamilton"),
    "CHATANOOGA": ("TN", "Hamilton"),  # typo seen in data
    # North Carolina
    "RALEIGH": ("NC", "Wake"),
    "CHARLOTTE": ("NC", "Mecklenburg"),
    "GREENSBORO": ("NC", "Guilford"),
    "WILMINGTON": ("NC", "New Hanover"),
    "DURHAM": ("NC", "Durham"),
    "ASHEVILLE": ("NC", "Buncombe"),
    "FAYETTEVILLE, NC": ("NC", "Cumberland"),
    "HENDERSONVILLE": ("NC", "Henderson"),
    # South Carolina
    "CHARLESTON": ("SC", "Charleston"),
    "COLUMBIA": ("SC", "Richland"),
    "GREENVILLE": ("SC", "Greenville"),
    "GREER": ("SC", "Greenville"),
    # Arkansas
    "LITTLE ROCK": ("AR", "Pulaski"),
    "FAYETTEVILLE": ("AR", "Washington"),
    "FORT SMITH": ("AR", "Sebastian"),
    "TEXARKANA": ("AR", "Miller"),
    # Missouri
    "ST. LOUIS": ("MO", "St. Louis city"),
    "ST LOUIS": ("MO", "St. Louis city"),
    "KANSAS CITY": ("MO", "Jackson"),
    "SPRINGFIELD": ("MO", "Greene"),
    "SPRINGFIELD, MO": ("MO", "Greene"),
    # Kansas
    "WICHITA": ("KS", "Sedgwick"),
    "TOPEKA": ("KS", "Shawnee"),
    "GARDEN CITY": ("KS", "Finney"),
    # Oklahoma
    "OKLAHOMA CITY": ("OK", "Oklahoma"),
    "TULSA": ("OK", "Tulsa"),
    "OK CITY": ("OK", "Oklahoma"),
    # Alaska
    "ANCHORAGE": ("AK", "Anchorage"),
    "FAIRBANKS": ("AK", "Fairbanks North Star"),
    "JUNEAU": ("AK", "Juneau"),
    "SITKA": ("AK", "Sitka"),
    "KETCHIKAN": ("AK", "Ketchikan Gateway"),
    "KODIAK": ("AK", "Kodiak Island"),
    # Hawaii
    "HONOLULU": ("HI", "Honolulu"),
    # PR
    "SAN JUAN": ("PR", "San Juan"),
    "AGUADILLA": ("PR", "Aguadilla"),
    "BAYAMON": ("PR", "Bayamon"),
    # Guam / VI / NMI
    "AGANA": ("GU", "Guam"),
    "HAGATNA": ("GU", "Guam"),
    "SAIPAN": ("MP", "Saipan"),
    "CHARLOTTE AMALIE": ("VI", "St. Thomas"),
}


# Pattern: extract county name from "{COUNTY} COUNTY JAIL" / "{COUNTY} CO. JAIL".
# We deliberately match a *strict* phrasing so we don't overfire on names like
# "MONTGOMERY COUNTY SHERIFF" (which doesn't tell us the state — those still
# need a state hint from the code suffix).
_COUNTY_NAME_PATTERNS = [
    # captures the county name before "COUNTY JAIL/SHERIFF/DET..."
    re.compile(r"\b([A-Z][A-Z .'-]*?)\s+CO(?:UNTY|\.|)\s+(?:SHERIFF|JAIL|DET|CORR|REGIONAL|JUSTICE)"),
    re.compile(r"\b([A-Z][A-Z .'-]*?)\s+CO(?:UNTY|\.|)\s+J\b"),
]


def _normalize_county(raw: str) -> str:
    """Strip trailing punctuation and normalize the captured county phrase."""
    s = raw.strip().rstrip(".,").strip()
    # Common words that get swept into the capture - drop them.
    s = re.sub(r"\s+(JAIL|SHERIFF|DET|CORR|REGIONAL|JUSTICE)\b.*$", "", s)
    return s.title()


def _extract_county_from_pattern(name: str) -> str | None:
    """If the name encodes a "{X} COUNTY ..." pattern, return X."""
    upper = name.upper()
    for pat in _COUNTY_NAME_PATTERNS:
        m = pat.search(upper)
        if m:
            return _normalize_county(m.group(1))
    return None


def resolve_facility(name: str, code: str | None) -> CountyHit | None:
    """Return (state, county, source) for a facility, or None if unresolvable.

    Resolution order:
      1. Exact facility code match (most reliable).
      2. Distinctive name keyword (handles facilities with stable names but
         varying codes across FY).
      3. "{COUNTY} COUNTY JAIL" pattern + state hint from code suffix.
      4. City keyword from CITY_COUNTY_HINTS + state hint check.
    """
    code_clean = (code or "").strip().upper()
    if code_clean in KNOWN_FACILITY_CODES:
        st, county = KNOWN_FACILITY_CODES[code_clean]
        return CountyHit(st, county, "code")

    upper = (name or "").upper()
    for regex_str, st, county in KNOWN_NAME_KEYWORDS:
        if re.search(regex_str, upper):
            return CountyHit(st, county, "name")

    # State from code suffix (e.g., DALCOTX -> TX)
    code_state = ""
    if code_clean and len(code_clean) >= 2 and code_clean[-2:].isalpha():
        candidate = code_clean[-2:]
        if candidate in {"AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "DC",
                         "FL", "GA", "HI", "ID", "IL", "IN", "IA", "KS", "KY",
                         "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT",
                         "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH",
                         "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT",
                         "VT", "VA", "WA", "WV", "WI", "WY", "PR", "GU", "VI",
                         "AS", "MP"}:
            code_state = candidate

    # "{X} COUNTY JAIL" pattern
    extracted = _extract_county_from_pattern(upper)
    if extracted and code_state:
        return CountyHit(code_state, extracted, "county_jail_pattern")

    # City keyword (try longer multi-word cities first)
    sorted_cities = sorted(CITY_COUNTY_HINTS, key=len, reverse=True)
    for city in sorted_cities:
        if re.search(rf"\b{re.escape(city)}\b", upper):
            st, county = CITY_COUNTY_HINTS[city]
            # If we have a code state and it disagrees, only accept the city
            # hint when there's no code-suffix conflict.
            if code_state and code_state != st:
                continue
            return CountyHit(st, county, "city")

    return None
