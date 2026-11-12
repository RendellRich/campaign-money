"""The written labeling rules and industry codes, shared by every rater: people, outside AIs and the LLM pass on the
long tail. The same text is in data/audit_2024_fresh_prompt.txt, which round 5's raters were given."""

RULES = "How to label\n\n1. Label the industry of the organization the donor works for, not their job title. A lawyer at a bank is finance; a lawyer at a law firm is law.\n2. If the donor is self-employed, left the employer blank, or wrote only a title as the employer (CEO, OWNER, PRESIDENT), label the industry of their own work from the occupation (a self-employed optometrist is health).\n3. You may use what you know about a company, and look it up if you can (Jane Street is a trading firm, so finance).\n4. Use unknown when the text gives no way to tell: a vague or unrecognized company name, a person's name, or a generic title with nothing else.\n5. Confidence: high if most careful people would give the same answer; low if a reasonable person could pick a different one.\n6. Use retired, not employed or missing only if the text itself says so (for example N/A or REQUESTED in both fields)."

CODES = [
    ('finance', 'Finance and investment: banks, investment and trading firms, private equity, hedge funds, venture capital, mortgage lenders, financial advisors'),
    ('insurance', 'Insurers and insurance brokers, including health insurers'),
    ('law', 'Law firms, lawyers, mediators and arbitrators'),
    ('lobbying', 'Lobbying and public affairs: lobbying firms, government relations, political consultants, trade associations'),
    ('tech', 'Technology: software, internet companies, computer hardware, semiconductors'),
    ('health', 'Health care: hospitals, doctors, clinics, therapists, nursing, veterinary care'),
    ('pharma', 'Pharma, biotech and medical devices'),
    ('energy', 'Energy and utilities: oil, gas, coal, mining, electric and gas utilities, solar and wind'),
    ('real_estate', 'Real estate and construction: brokers, developers, property managers, builders, contractors, architects, title companies, building trades'),
    ('defense', 'Defense and aerospace contractors'),
    ('education', 'Education: schools, colleges, universities, tutors'),
    ('government', 'Government: agencies, elected officials and their staff, military, police and fire'),
    ('media', 'Media, entertainment and sports: news, film, TV, music, publishing, writers, artists'),
    ('manufacturing', 'Manufacturing: factories and industrial companies not covered elsewhere (steel, chemicals, machinery)'),
    ('consumer', 'Retail, food and consumer goods: stores, restaurants, hotels, car dealers, food and drink makers'),
    ('agriculture', 'Agriculture: farms, ranches, agribusiness, wineries, forestry, fishing'),
    ('transportation', 'Transportation: airlines, railroads, trucking, shipping, logistics'),
    ('telecom', 'Telecom and cable: phone, cable and internet providers'),
    ('nonprofit', 'Nonprofits and advocacy: charities, foundations, advocacy groups, religious organizations'),
    ('business_services', 'Consulting and business services: management consulting, accounting, staffing, marketing and PR agencies'),
    ('unknown', 'The text gives no way to tell the industry'),
    ('retired', 'Only if the text says retired'),
    ('not employed', 'Only if the text says not employed, homemaker or student'),
    ('missing', "Only if both fields are blank, N/A or 'information requested'"),
]
