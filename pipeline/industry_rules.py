"""Rules that map a donor's employer and occupation to an industry.

Order matters: the first rule that fires wins. Employer rules come before occupation rules, because "AMAZON" with
occupation "ATTORNEY" is a tech company employee, not a law firm. Occupation rules catch employers the name alone
can't place ("KIRKLAND ELLIS", occupation "ATTORNEY" -> law).

These rules are the first pass. Employers they leave unplaced are labeled by review in data/employer_industry.csv,
and anything still unplaced is "unknown", which is a real category, not a guess.
"""
from __future__ import annotations

import re

INDUSTRIES = {
    "finance": "Finance and investment (banks, funds, private equity, venture capital, crypto)",
    "insurance": "Insurance",
    "law": "Law firms and lawyers",
    "lobbying": "Lobbying, government relations and public affairs",
    "tech": "Technology and internet",
    "health": "Health care (hospitals, doctors, health plans)",
    "pharma": "Pharmaceuticals, biotech and medical devices",
    "energy": "Energy and utilities",
    "real_estate": "Real estate and construction",
    "defense": "Defense and aerospace",
    "education": "Education (universities and schools)",
    "government": "Government and public office",
    "media": "Media, entertainment and sports",
    "manufacturing": "Manufacturing and industry",
    "consumer": "Retail, food, beverage and consumer goods",
    "agriculture": "Agriculture",
    "transportation": "Transportation and logistics",
    "telecom": "Telecom and cable",
    "nonprofit": "Foundations, nonprofits and advocacy",
    "business_services": "Consulting, accounting and business services",
    "unknown": "Employer given but no industry can be told (e.g. 'Entrepreneur', 'Business owner')",
}

NORMALIZE = re.compile(r"\b(INC|LLC|LLP|CORP|CORPORATION|CO|COMPANY|LTD|PC|PLLC|PA|THE|L L C|L L P|LP)\b")


def norm(text: str | None) -> str:
    s = re.sub(r"[^A-Z0-9 ]", " ", (text if isinstance(text, str) else "").upper())
    return re.sub(r"\s+", " ", NORMALIZE.sub(" ", s)).strip()


# (industry, pattern on the normalized employer)
EMPLOYER_RULES = [
    ("unknown", r"^(ENTREPRENEUR|BUSINESS ?OWNER|OWNER|CEO|PRESIDENT|EXECUTIVE|INVESTOR|CONSULTANT|PARTNER|"
                r"PRINCIPAL|CHAIRMAN|MANAGER|SELF ?EMPLOYED|SELF|PRIVATE|BUSINESS|DIRECTOR|FOUNDER)$"),
    ("lobbying", r"\b(GOVERNMENT RELATIONS|GOVERNMENT AFFAIRS|PUBLIC AFFAIRS|PUBLIC POLICY|ADVOCACY|LOBBY|"
                 r"STRATEGIES|STRATEGY GROUP|CAPITOL|POTOMAC|FEDERAL STRATEGIES)\b"),
    ("government", r"\b(US SENATE|U ?S SENATE|HOUSE OF REPRESENTATIVES|US HOUSE|U ?S HOUSE|US CONGRESS|CONGRESS|"
                   r"STATE OF [A-Z ]+|CITY OF [A-Z ]+|COUNTY OF [A-Z ]+|COUNTY|FEDERAL GOVERNMENT|U ?S GOVERNMENT|"
                   r"US ARMY|US NAVY|US AIR FORCE|USMC|DEPARTMENT OF|DEPT OF|VETERANS AFFAIRS|^VA$|USPS|"
                   r"POSTAL SERVICE|GOVERNMENT|ATTORNEY GENERAL|SHERIFF|POLICE)\b"),
    ("education", r"\b(UNIVERSITY|COLLEGE|SCHOOL|ACADEMY|INSTITUTE OF TECHNOLOGY|^MIT$|^UCLA$|^UCSF$|^USC$|^NYU$|"
                  r"^ASU$|UC BERKELEY|UW MADISON|^HARVARD$|^STANFORD$|^YALE$|SCHOOL DISTRICT|UNIFIED|ISD)\b"),
    ("health", r"\b(HOSPITAL|HEALTH|MEDICAL|CLINIC|PHYSICIAN|MD|KAISER|MAYO|SURGERY|SURGICAL|ONCOLOGY|CANCER|"
               r"RADIOLOGY|DENTAL|ORTHOPAEDIC|ORTHOPEDIC|PEDIATRIC|CARDIOLOGY|DAVITA|HCA|OPTUM|ELEVANCE|"
               r"BLUE (CROSS|SHIELD)|UNITEDHEALTH|HUMANA|CIGNA|AETNA|NURSING|HOSPICE|DERMATOLOGY|EYE)\b"),
    ("pharma", r"\b(PHARMA|PHARMACEUTICAL|THERAPEUTICS|BIOTECH|BIOSCIENCES?|BIO|GENENTECH|AMGEN|PFIZER|MERCK|"
               r"ABBVIE|ELI LILLY|LILLY|GILEAD|REGENERON|MODERNA|JOHNSON JOHNSON|BRISTOL MYERS|NOVARTIS|ASTRAZENECA|"
               r"MEDTRONIC|STRYKER|ABBOTT|RESMED|GRAIL)\b"),
    ("law", r"\b(LAW|LAW FIRM|LAW OFFICES?|LEGAL|ATTORNEYS?|LAWYERS?)\b"),
    ("finance", r"\b(CAPITAL|INVEST|INVESTMENTS?|ASSET MANAGEMENT|FUND|FUNDS|EQUITY|EQUITIES|VENTURES?|BANK|"
                r"BANCORP|FINANCIAL|SECURITIES|TRADING|ADVISORS|WEALTH|PARTNERS LP|HOLDINGS|GOLDMAN|MORGAN STANLEY|"
                r"JP ?MORGAN|CITI|CITIGROUP|BLACKSTONE|BLACKROCK|KKR|CARLYLE|APOLLO|CITADEL|JANE STREET|"
                r"MERRILL|SCHWAB|FIDELITY|VANGUARD|EVERCORE|LAZARD|UBS|BARCLAYS|CREDIT SUISSE|DEUTSCHE|"
                r"WELLS FARGO|BANK OF AMERICA|CAPITAL ONE|EDWARD JONES|RAYMOND JAMES|STIFEL|COINBASE|"
                r"CRYPTO|BLOCKCHAIN|RIPPLE|PAXOS|UNISWAP|SOLANA|ROCKET|MORTGAGE|LOANS?)\b"),
    ("insurance", r"\b(INSURANCE|ASSURANCE|METLIFE|AFLAC|MASSMUTUAL|NORTHWESTERN MUTUAL|PROTECTIVE LIFE|GENWORTH|"
                  r"BRIGHTHOUSE|STATE FARM|ALLSTATE|PROGRESSIVE|NFP|RT SPECIALTY|STERLINGRISK|SAGESURE)\b"),
    ("real_estate", r"\b(REAL ESTATE|REALTY|REALTORS?|PROPERTIES|PROPERTY|DEVELOPMENT|DEVELOPERS?|CONSTRUCTION|"
                    r"BUILDERS?|HOMES|HOUSING|APARTMENTS?|COMMUNITIES|CBRE|JLL|CUSHMAN|COLDWELL|KELLER WILLIAMS|"
                    r"COMPASS|NEWMARK|SOTHEBY|RE MAX|REMAX|EXP REALTY|CONTRACTING|ARCHITECT)\b"),
    ("energy", r"\b(ENERGY|OIL|GAS|PETROLEUM|POWER|SOLAR|WIND|ELECTRIC|UTILIT|EXXON|CHEVRON|CONOCO|VALERO|"
               r"NEXTERA|DOMINION|DUKE ENERGY|SOUTHERN COMPANY|EDISON|INVENERGY|SUNRUN|CRUDE|RESOURCES|PIPELINE)\b"),
    ("defense", r"\b(LOCKHEED|BOEING|RAYTHEON|RTX|NORTHROP|GENERAL DYNAMICS|GENERAL ATOMICS|ANDURIL|PALANTIR|"
                r"LEIDOS|BOOZ ALLEN|SAIC|L3HARRIS|HARRIS|BAE|DEFENSE|AEROSPACE|SPACEX|UNITED LAUNCH|SIERRA NEVADA|"
                r"TRANSDIGM|AM GENERAL|HUNTINGTON INGALLS)\b"),
    ("tech", r"\b(GOOGLE|ALPHABET|MICROSOFT|APPLE|AMAZON|META|FACEBOOK|NETFLIX|NVIDIA|INTEL|AMD|ORACLE|IBM|"
             r"SALESFORCE|ADOBE|CISCO|QUALCOMM|BROADCOM|LINKEDIN|AIRBNB|UBER|LYFT|TWILIO|PAYPAL|INTUIT|"
             r"SYNOPSYS|ARISTA|VALVE|SOFTWARE|TECHNOLOG|SYSTEMS|LABS|AI|DATA|CLOUD|DIGITAL|NETWORKS)\b"),
    ("telecom", r"\b(AT T|VERIZON|T MOBILE|COMCAST|CHARTER|COX|DISH|ECHOSTAR|SPECTRUM|TELECOM|WIRELESS|"
                r"COMMUNICATIONS)\b"),
    ("media", r"\b(MEDIA|DISNEY|NETWORK|BROADCASTING|STUDIOS|PRODUCTIONS|PICTURES|FILMS?|ENTERTAINMENT|"
              r"BLOOMBERG|NEWS|PUBLISHING|AGENCY|CREATIVE ARTISTS|WASSERMAN|IHEART|SPORTS|GAMING|CASINO|"
              r"DRAFTKINGS|RECORDS|MUSIC)\b"),
    ("transportation", r"\b(AIRLINES?|AIR LINES|FEDEX|UPS|TRUCKING|LOGISTICS|RAILROAD|RAILWAY|SHIPPING|"
                       r"CRUISE|ROYAL CARIBBEAN|MARITIME|OFFSHORE|AVIATION)\b"),
    ("consumer", r"\b(WALMART|KROGER|TARGET|COSTCO|HOME DEPOT|LOWES|FOODS?|BEVERAGE|BREWING|WINES?|VINEYARDS?|"
                 r"RESTAURANTS?|HOTELS?|HOSPITALITY|RETAIL|BRANDS|ALTRIA|ESTEE LAUDER|AMWAY|MELALEUCA|ULINE|"
                 r"TRACTOR SUPPLY|SEAFOODS|DISTRIBUTING|BREAKTHRU|RNDC|TYSON)\b"),
    ("agriculture", r"\b(FARMS?|FARMING|RANCH|AGRI|GROWERS?|DAIRY|MILK|CATTLE|POULTRY|CROPS?|MOUNTAIRE|SUGAR)\b"),
    ("manufacturing", r"\b(MANUFACTURING|INDUSTRIES|STEEL|METAL|CHEMICAL|DOW|GENERAL MOTORS|FORD|TOYOTA|"
                      r"MACHINERY|ENGINEERING|COMPOSITES|TOOLS|PLASTICS|PAPER|EQUIPMENT)\b"),
    ("nonprofit", r"\b(FOUNDATION|CHARITABLE|PHILANTHROP|TRUST|NONPROFIT|NON PROFIT|INSTITUTE|MUSEUM|CHURCH|"
                  r"SOCIETY|ASSOCIATION|FEDERATION|COUNCIL|STAND UP AMERICA|ARNOLD VENTURES)\b"),
    ("business_services", r"\b(MCKINSEY|BAIN|BOSTON CONSULTING|DELOITTE|PWC|KPMG|ERNST YOUNG|^EY$|ACCENTURE|"
                          r"FTI CONSULTING|ANALYSIS GROUP|CORNERSTONE RESEARCH|KROLL|CONSULTING|ADVISORY|ACCOUNTING|"
                          r"CPA|MARKETING|STAFFING)\b"),
]

# (industry, pattern on the normalized occupation), used when no employer rule fires
OCCUPATION_RULES = [
    ("lobbying", r"\b(LOBBYIST|GOVERNMENT RELATIONS|GOVT AFFAIRS|GOVERNMENT AFFAIRS|PUBLIC AFFAIRS|POLICY ADVISOR)\b"),
    ("law", r"\b(ATTORNEY|LAWYER|COUNSEL|PARALEGAL|JUDGE|LITIGATOR)\b"),
    ("health", r"\b(PHYSICIAN|DOCTOR|SURGEON|NURSE|DENTIST|PSYCHIATRIST|PSYCHOLOGIST|OPHTHALMOLOGIST|"
               r"ANESTHESIOLOGIST|RADIOLOGIST|CARDIOLOGIST|PHARMACIST|THERAPIST|MD)\b"),
    ("education", r"\b(PROFESSOR|TEACHER|EDUCATOR|LECTURER|PRINCIPAL OF|SUPERINTENDENT)\b"),
    ("finance", r"\b(INVESTOR|INVESTMENT|FINANCE|FINANCIAL|BANKER|TRADER|PORTFOLIO|PRIVATE EQUITY|VENTURE|"
                r"HEDGE FUND|FUND MANAGER|ASSET)\b"),
    ("real_estate", r"\b(REAL ESTATE|REALTOR|DEVELOPER|BROKER|CONTRACTOR|HOME ?BUILDER)\b"),
    ("insurance", r"\b(INSURANCE|UNDERWRITER|ACTUARY)\b"),
    ("tech", r"\b(SOFTWARE|ENGINEER|PROGRAMMER|DEVELOPER|DATA SCIENTIST|PRODUCT MANAGER|TECH)\b"),
    ("government", r"\b(US SENATOR|SENATOR|CONGRESSMAN|CONGRESSWOMAN|REPRESENTATIVE|GOVERNOR|MAYOR|LEGISLATOR)\b"),
    ("agriculture", r"\b(FARMER|RANCHER|GROWER)\b"),
    ("transportation", r"\b(PILOT|TRUCK DRIVER|FLIGHT ATTENDANT)\b"),
    ("nonprofit", r"\b(PHILANTHROPIST|GRANTMAKER|NONPROFIT)\b"),
]

COMPILED_EMPLOYER = [(i, re.compile(p)) for i, p in EMPLOYER_RULES]
COMPILED_OCCUPATION = [(i, re.compile(p)) for i, p in OCCUPATION_RULES]


GENERIC_TITLE = re.compile(r"^(CEO|PRESIDENT|EXECUTIVE|CHAIRMAN|PARTNER|PRINCIPAL|OWNER|FOUNDER|MANAGER|DIRECTOR|"
                           r"ATTORNEY|LAWYER|CONSULTANT|INVESTOR|BANKER)$")


def classify(employer: str | None, occupation: str | None) -> tuple[str | None, str]:
    """(industry or None, which rule fired)."""
    e, o = norm(employer), norm(occupation)
    if GENERIC_TITLE.match(e) and o and not GENERIC_TITLE.match(o):
        # Donor swapped the fields: "CEO" as employer, the company as occupation. Read the occupation as the employer.
        for ind, pat in COMPILED_EMPLOYER:
            if ind != "unknown" and pat.search(o):
                return ind, f"swapped:{ind}"
    for ind, pat in COMPILED_EMPLOYER:
        if pat.search(e):
            return ind, f"employer:{ind}"
    for ind, pat in COMPILED_OCCUPATION:
        if pat.search(o):
            return ind, f"occupation:{ind}"
    return None, "none"
