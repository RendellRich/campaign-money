# Campaign Money by Industry

Where members of Congress get their campaign money, by the industry their donors work in, from the Federal Election
Commission's public filings. The aim is an open method with measured accuracy, not just totals.

A companion to [PartyCohesion](https://github.com/RendellRich/partycohesion), which covers how members vote. The two
are kept on separate sites on purpose: this one never pairs a donation with a vote.

## Status

Phase 1 (feasibility) is done, and the answer is to go ahead with two changes. Phase 2 (classifier and audit) has
started: the 1,000 largest employers are labeled, the rules are in place, and a blind audit measures them.

## Phase 1: can donors be placed in an industry?

The test used the full 2024 cycle: individual contributions to the principal campaign committees of current members.

| | |
|---|---|
| Members mapped to a 2024 committee | 521 of 537 (425 House, 96 Senate) |
| Individual contributions | $1.43 billion |
| Itemized (donor details reported) | $969 million, 67.9%, in 6.4 million records |
| Unitemized (no donor details) | 32.1% |

The FEC only requires donor details above $200 per donor per cycle, so about a third of the money can't be placed in
any industry. Every number on the site will show that share.

What donors wrote in the employer field, as a share of itemized dollars:

| Employer field | Share |
|---|---|
| A named employer | 49.0% |
| Retired | 21.0% |
| Not employed | 19.0% |
| Self-employed, with an occupation | 8.6% |
| Missing or "information requested" | 2.3% |
| Occupation only | 0.2% |

- **Usable at all:** 97.6% of itemized dollars.
- **Points to an industry:** 57.6%. The median member committee is 70%, and the middle half of committees run 58% to 80%.
- **A long tail:** 178,315 distinct employer names. The top 1,000 cover 25% of named-employer dollars and the top 20,000
  cover 69%, so a hand-built list alone can't work.

Two changes came out of this:

1. Every breakdown shows industry, retired, not employed, missing and unitemized side by side, never industry alone.
2. Classification needs rules, a reviewed employer list and a text classifier from the start.

## Phase 2 so far: the employer list and rules

- **`pipeline/industry_rules.py`:** keyword rules on the employer name, then on the occupation, sorted into 20 industries
  plus "unknown". Employer rules come first, because an attorney at Microsoft works in tech.
- **`data/employer_industry.csv`:** the 1,000 employers with the most itemized dollars to members in 2024.
  - The rules placed 750 of them. The other 250 were left unplaced.
  - Every row was then reviewed one at a time by an AI assistant (Claude). It overruled the rules on 41 of the 750 and
    placed the 250. The `source` column says which rows the review changed.
  - The rules agreed with the review on 94.5% of the employers they placed.
- **Baseline:** the reviewed list plus the rules place 58% of the dollars that carry an industry signal. The other 42%
  is the long tail the text classifier will take on, measured against a blind, labeled sample.

## Audit: how often is the industry right?

A blind sample, drawn so each pick is one dollar of 2024 itemized money that carries an industry signal
(`pipeline/audit_sample.py`, seed 2024). 100 draws come from employers on the list and 200 from the long tail, giving
296 distinct employer and occupation pairs. An AI assistant (Claude) labeled each pair from the donor's own text,
before seeing any pipeline output, and marked 98 of them low confidence where a reasonable person could choose
differently (`data/audit_2024_labels.csv`). `pipeline/audit.py` scores the pipeline against those labels.

| Share of industry-signal dollars | All | List stratum | Long tail |
|---|---|---|---|
| Right industry | 61.3% (95% CI 56.1 to 66.6) | 81.0% | 51.5% |
| Wrong industry | 9.7% (6.3 to 13.0) | 7.0% | 11.0% |
| Left unknown | 29.0% | 12.0% | 37.5% |
| Right, when an industry is given | 86.3% | 92.0% | 82.4% |

On high-confidence labels only, the list is right 98.5% of the time it places a pair and the tail 90.8%.

What the audit found and fixed: "SELF EMPLOYED" is on the employer list (as unknown) because it is a top-1,000 string,
so the list overrode the occupation and every self-employed donor came out unknown. The list now applies only to
named employers. Before that fix the list stratum was 69% right and 25% unknown.

Known rule errors, left unfixed so this sample stays a fair test: words matched out of context ("POWER" in a law
firm's name, "INDUSTRIES" in a real estate developer, "CITY OF" in City of Hope, "FUND" in an art fund) and an order
problem where "PUBLIC SCHOOLS" hits government before education. Fixes will be measured on a fresh sample.

Limits: one labeler, and the same assistant wrote the rules, so the labels are not fully independent. A spot check by
a person on a random 50 would show how much that matters. The "list" stratum includes self-employed donors, since
that string is on the list. Every misread pair is in `data/audit_2024_misses.csv`.

## Wording rules

- Say "received from people who listed employers in finance", never "funded by" or "owned by" an industry.
- Use the same charts for every member and both parties, sorted by the data, never hand-picked.
- Always show the unitemized, retired, not employed, missing and unknown shares next to any industry number.
- Never pair a donation with a vote.

## Run it

```bash
pip install -r requirements.txt
cd pipeline
python member_committees.py --cycle 2024   # members to campaign committees
python load_fec.py --cycle 2024            # downloads the 4.2 GB contributions file, loads it in about 3 minutes
python feasibility.py --cycle 2024         # writes data/feasibility_2024.json
python audit_sample.py --cycle 2024        # draws the audit sample (already drawn; rerun gives the same draws)
python audit.py --cycle 2024               # scores the pipeline, writes data/audit_2024.json and the misses
cd .. && pytest -q
```

Raw downloads and the DuckDB file go in `data/raw/`, which git ignores.

## Data sources

- [FEC bulk data](https://www.fec.gov/data/browse-data/?tab=bulk-data): individual contributions, candidate master,
  candidate-committee linkage, and current campaigns summary. Public, no key needed.
- [congress-legislators](https://github.com/unitedstates/congress-legislators): Bioguide and FEC candidate IDs for
  current members.
