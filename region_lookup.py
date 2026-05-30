"""Free-text → GSP region lookup. Two-stage:
  1. Postcode prefix match (e.g. "CF10 1AA", "BS", "EH1") via 2-letter then 1-letter prefix.
  2. Location name match (city/town/county) — exact, then substring.

Returns the GSP region letter (one of the 14 in ALL_REGIONS) or None.

Where postcode areas span multiple regions (e.g. "PE" Peterborough vs Wisbech, or "FK" partly N/P)
we map to the dominant DNO area. Refine the table over time as users hit edge cases.
"""
import re

POSTCODE_PREFIX_TO_REGION = {
    # London (UK Power Networks London)
    "E": "C", "EC": "C", "N": "C", "NW": "C", "SE": "C", "SW": "C",
    "W": "C", "WC": "C", "BR": "C", "CR": "C", "DA": "C", "EN": "C",
    "HA": "C", "IG": "C", "KT": "C", "RM": "C", "SM": "C", "TW": "C",
    "UB": "C", "WD": "C",
    # Eastern (UK Power Networks Eastern)
    "AL": "A", "CB": "A", "CM": "A", "CO": "A", "IP": "A", "LU": "A",
    "NR": "A", "PE": "A", "SG": "A", "SS": "A",
    # East Midlands (National Grid Electricity Distribution)
    "DE": "B", "LE": "B", "LN": "B", "NG": "B", "NN": "B",
    # West Midlands
    "B": "E", "CV": "E", "DY": "E", "HR": "E", "ST": "E", "TF": "E",
    "WR": "E", "WS": "E", "WV": "E",
    # NE England (Northern Powergrid)
    "DH": "F", "DL": "F", "NE": "F", "SR": "F", "TS": "F",
    # NW England (Electricity North West)
    "BB": "G", "BL": "G", "CA": "G", "FY": "G", "LA": "G", "M": "G",
    "OL": "G", "PR": "G", "SK": "G", "WA": "G", "WN": "G",
    # Southern (SSEN Southern)
    "BH": "H", "GU": "H", "HP": "H", "MK": "H", "OX": "H", "PO": "H",
    "RG": "H", "SL": "H", "SN": "H", "SO": "H", "SP": "H",
    # South East (UK Power Networks SE)
    "BN": "J", "CT": "J", "ME": "J", "RH": "J", "TN": "J",
    # Merseyside / N Wales (SP Manweb)
    "CH": "D", "CW": "D", "L": "D", "LL": "D", "SY": "D",
    # South Wales (NGED South Wales)
    "CF": "K", "LD": "K", "NP": "K", "SA": "K",
    # SW England (NGED South West)
    "BA": "L", "BS": "L", "DT": "L", "EX": "L", "GL": "L", "PL": "L",
    "TA": "L", "TQ": "L", "TR": "L",
    # Yorkshire (Northern Powergrid Yorkshire)
    "BD": "M", "DN": "M", "HD": "M", "HG": "M", "HU": "M", "HX": "M",
    "LS": "M", "S": "M", "WF": "M", "YO": "M",
    # Southern Scotland (SP Distribution)
    "DG": "N", "EH": "N", "G": "N", "KA": "N", "KY": "N", "ML": "N",
    "PA": "N", "TD": "N",
    # Northern Scotland (SSEN North)
    "AB": "P", "DD": "P", "FK": "P", "HS": "P", "IV": "P", "KW": "P",
    "PH": "P", "ZE": "P",
}

LOCATION_TO_REGION = {
    # Major cities
    "london": "C", "city of london": "C", "westminster": "C", "camden": "C",
    "birmingham": "E", "wolverhampton": "E", "coventry": "E", "stoke-on-trent": "E",
    "stoke": "E", "walsall": "E", "dudley": "E", "telford": "E", "worcester": "E",
    "hereford": "E",
    "manchester": "G", "salford": "G", "bolton": "G", "preston": "G",
    "blackpool": "G", "blackburn": "G", "carlisle": "G", "lancaster": "G",
    "warrington": "G", "wigan": "G", "oldham": "G", "rochdale": "G",
    "liverpool": "D", "chester": "D", "wrexham": "D", "crewe": "D",
    "shrewsbury": "D", "ellesmere port": "D",
    "leeds": "M", "sheffield": "M", "bradford": "M", "huddersfield": "M",
    "halifax": "M", "york": "M", "hull": "M", "doncaster": "M",
    "wakefield": "M", "harrogate": "M", "rotherham": "M", "barnsley": "M",
    "newcastle": "F", "newcastle upon tyne": "F", "sunderland": "F",
    "durham": "F", "darlington": "F", "middlesbrough": "F", "gateshead": "F",
    "nottingham": "B", "derby": "B", "leicester": "B", "lincoln": "B",
    "northampton": "B", "mansfield": "B", "loughborough": "B",
    "peterborough": "A", "norwich": "A", "ipswich": "A", "cambridge": "A",
    "colchester": "A", "chelmsford": "A", "luton": "A", "southend": "A",
    "southend-on-sea": "A", "harlow": "A", "stevenage": "A",
    "bristol": "L", "bath": "L", "exeter": "L", "plymouth": "L",
    "torquay": "L", "truro": "L", "gloucester": "L", "taunton": "L",
    "cheltenham": "L", "weston-super-mare": "L", "swindon": "H",
    "bournemouth": "H", "southampton": "H", "portsmouth": "H", "reading": "H",
    "oxford": "H", "milton keynes": "H", "guildford": "H", "salisbury": "H",
    "slough": "H", "winchester": "H", "basingstoke": "H", "isle of wight": "H",
    "brighton": "J", "canterbury": "J", "tonbridge": "J", "dover": "J",
    "redhill": "J", "maidstone": "J", "tunbridge wells": "J", "ashford": "J",
    "cardiff": "K", "swansea": "K", "newport": "K", "merthyr": "K",
    "merthyr tydfil": "K", "bridgend": "K", "neath": "K", "carmarthen": "K",
    "edinburgh": "N", "glasgow": "N", "stirling": "N", "kirkcaldy": "N",
    "dumfries": "N", "ayr": "N", "kilmarnock": "N", "motherwell": "N",
    "paisley": "N", "falkirk": "N", "livingston": "N",
    "aberdeen": "P", "inverness": "P", "dundee": "P", "perth": "P",
    "elgin": "P", "fort william": "P", "stornoway": "P", "kirkwall": "P",
    "lerwick": "P", "thurso": "P", "wick": "P",
    # Counties / informal regions
    "yorkshire": "M", "south yorkshire": "M", "west yorkshire": "M",
    "north yorkshire": "M", "east yorkshire": "M",
    "south wales": "K", "north wales": "D", "mid wales": "K",
    "cornwall": "L", "devon": "L", "somerset": "L", "dorset": "L",
    "kent": "J", "surrey": "J", "sussex": "J", "east sussex": "J",
    "west sussex": "J",
    "essex": "A", "norfolk": "A", "suffolk": "A", "hertfordshire": "A",
    "cambridgeshire": "A",
    "highlands": "P", "orkney": "P", "shetland": "P", "outer hebrides": "P",
    "lothian": "N", "borders": "N", "ayrshire": "N",
    "northumberland": "F", "tyne and wear": "F", "county durham": "F",
    "cumbria": "G", "lancashire": "G", "greater manchester": "G",
    "merseyside": "D", "cheshire": "D",
    "west midlands": "E", "warwickshire": "E", "staffordshire": "E",
    "shropshire": "D",
    "leicestershire": "B", "nottinghamshire": "B", "lincolnshire": "B",
    "derbyshire": "B", "northamptonshire": "B",
    "hampshire": "H", "berkshire": "H", "oxfordshire": "H", "wiltshire": "H",
    "buckinghamshire": "H",
    "gloucestershire": "L", "bristol": "L", "avon": "L",
}


def _lookup_postcode(q):
    """q is uppercased, no spaces. Returns region letter or None."""
    if len(q) < 2:
        return None
    # Need pattern like "CF10" or "B1" — alpha then digit (or alpha-alpha-digit)
    m = re.match(r"^([A-Z]{1,2})(\d.*)?$", q)
    if not m:
        return None
    prefix = m.group(1)
    has_digit_after = bool(m.group(2))
    # Try 2-letter first
    if len(prefix) == 2 and prefix in POSTCODE_PREFIX_TO_REGION:
        return POSTCODE_PREFIX_TO_REGION[prefix]
    # Fall back to 1-letter, but only if followed by a digit (otherwise it's a city name)
    if len(prefix) == 1 and has_digit_after and prefix in POSTCODE_PREFIX_TO_REGION:
        return POSTCODE_PREFIX_TO_REGION[prefix]
    # Or 2-letter where the 2nd letter wasn't matched but 1st letter is — e.g. "BX" → fall back to "B"
    if len(prefix) == 2 and has_digit_after and prefix[0] in POSTCODE_PREFIX_TO_REGION:
        return POSTCODE_PREFIX_TO_REGION[prefix[0]]
    return None


def _lookup_location(q):
    """q is lowercased, stripped. Returns region letter or None."""
    if q in LOCATION_TO_REGION:
        return LOCATION_TO_REGION[q]
    # Substring match — prefer longer keys (more specific) first
    for key in sorted(LOCATION_TO_REGION, key=len, reverse=True):
        if key in q or (len(key) >= 4 and q in key):
            return LOCATION_TO_REGION[key]
    return None


def lookup_region(query):
    """Match a UK location string to a GSP region letter. Returns None if no match."""
    if not query:
        return None
    raw = query.strip()
    pc_q = raw.upper().replace(" ", "")
    pc_result = _lookup_postcode(pc_q)
    if pc_result:
        return pc_result
    return _lookup_location(raw.lower())
