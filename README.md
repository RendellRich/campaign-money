# Campaign Money by Industry

Where members of Congress get their campaign money, by the industry their donors work in, from the Federal Election
Commission's public filings. The aim is an open method with measured accuracy, not just totals.

**Live site:** [campaign-money.streamlit.app](https://campaign-money.streamlit.app)

A companion to [PartyCohesion](https://github.com/RendellRich/partycohesion), which covers how members vote. The two
are kept on separate sites on purpose: this one never pairs a donation with a vote.

## Status

Phase 1 (feasibility) is done, and the answer is to go ahead with two changes. Phase 2 (classifier and audit) has
started: the 1,000 largest employers are labeled, the rules are in place, and a blind audit on a held-out sample measures them.

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
- **`data/employer_industry.csv`:** the 1,000 employers with the most itemized dollars to members in 2024 (round 3
  extended it to 4,447, see the audit section).
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

### Round 1: the first sample

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

### Round 2: rule fixes, scored on a held-out sample

The first sample became the dev set. Before any rule changed, a second sample was drawn (seed 2025, same design, 297
pairs), labeled blind, and committed (`data/audit_2024_test_*.csv`). Rules were then fixed using dev misses only:
words matched out of context (POWER, INDUSTRIES, FUND, AGENCY, SYSTEMS, COMMUNICATIONS), schools before government,
insurance before finance, generic employers like "CONSULTING" falling through to the occupation, "N/A" read as
missing, students as not employed, and common occupations (writer, construction, caregiver, accountant).

| Share of industry-signal dollars | Dev before | Dev after | Test before | Test after |
|---|---|---|---|---|
| Right industry | 61.3% | 81.3% | 59.3% | 60.4% (95% CI 55.2 to 65.5) |
| Wrong industry | 9.7% | 3.3% | 11.3% | 8.3% |
| Left unknown | 29.0% | 15.3% | 29.3% | 31.3% |

The dev gain was mostly fitting those 296 pairs. On fresh data the fixes cut wrong answers by about a quarter
(11.3% to 8.3%) but placed almost nothing new: the long tail is too varied for rules learned from a few hundred
examples. On the test set, when the pipeline gives an industry it is right 95.5% of the time for list employers and
82.1% in the tail.

Two tail methods were tried on dev and dropped because neither helped:
- **Employer vote** (give an employer the industry its donors' occupations point to): 8 of 12 dev pairs right, and it
  added wrong answers when staff jobs differ from the firm's business (lawyers at a real estate developer). At stricter
  settings it changed nothing.
- **Name model** (logistic regression on character n-grams of employer names, trained on 64,000 employers the list and
  rules place): 1 of 31 dev pairs right. The employers left unknown are the ones whose names carry no clue
  ("COUNTSY", "TRAILMARK"), so a model of names has nothing to learn from.

What would work: review more employers. 65% of the test set's unknown tail dollars sit with employers ranked in the
top 20,000 by dollars (28% in the top 5,000).

### Round 3: 4,447 reviewed employers, scored on the same held-out sample

The list grew from the top 1,000 employers to ranks 1,001 to 5,000 as well. Each candidate was shown with its top
occupation, the rule's answer, and where its donors' occupations point.
- Claude placed the employers the rules couldn't and checked the rule answers, overruling 109 of 1,515 (92.8%
  agreement).
- 553 names were left off on purpose: they carry no clue to an industry (a person's name, "VARIOUS", "PILOT"), so each
  donor's own occupation still decides.
- The list now has 4,447 employers.
- Three rule bugs found in the review were fixed: "HARRIS" (Fried Frank Harris, Brown Harris Stevens), "DOMINION" (Old
  Dominion Freight Line) and "ELECTRIC" (Electric Boat).

| Test sample, share of industry-signal dollars | Round 2 | Round 3 |
|---|---|---|
| Right industry | 60.4% | 69.7% (95% CI 64.6 to 74.7) |
| Wrong industry | 8.3% | 6.3% |
| Left unknown | 31.3% | 24.0% |
| Right, when an industry is given | 87.9% | 91.7% |

Caveat on the gain: 33 of the 300 test draws are placed by employers Claude reviewed in this round, after labeling the
test sample, and all 33 agree. That is partly the same judgment twice. If those agreed only at the tail's usual 89%,
the right share would be about 1.2 points lower.

Limits: one labeler, and the same assistant wrote the rules, so the labels are not fully independent. A spot check by
a person on a random 50 would show how much that matters. The "list" stratum includes self-employed donors, since
that string is on the list. Every misread pair is in `data/audit_2024_misses.csv` (dev) and `data/audit_2024_test_misses.csv` (test). The labeler saw
the test pairs while labeling them, so fixes were limited to words found in dev misses.


### Round 4: a reviewed occupation list, for donors whose employer says nothing

Self-employed donors, donors who left the employer blank, and donors who wrote only a title ("CEO", "OWNER") are
placed by their occupation, and the occupation rules missed many clear jobs: tutor, poet, optometrist, landman,
property manager. `data/occupation_industry.csv` holds the 800 occupations with the most still-unclear 2024 dollars,
reviewed by Claude. An occupation names an industry only when the job alone implies it; 387 do, and the rest (CEO,
engineer, consultant, designer) stay unknown. The list is a last resort, used only when the employer list and the rules
leave a donor unclear.

Two versions were tried, and the choice was made on the dev sample:

| Share right | Dev | Test |
|---|---|---|
| Round 3 | 86.0% | 69.7% |
| Occupation list for every unclear donor | 85.7% (2 new wrong) | 74.3% |
| Occupation list only when the employer says nothing (kept) | 86.0% | 71.7% (95% CI 66.8 to 76.5) |

The broader version scored higher on test, but on dev it placed nothing new and added two wrong answers, both for
named employers ("PROPERTY MANAGER" at a bus company). Picking it because of the test score would be tuning to the
test set, which is what round 2 warned about. On test the kept version is 6.3% wrong and 22.0% left
unknown, and 91.9% right when it gives an industry. On the site, the share of 2024 individual money placed in
an industry rises from 24.3% to 25.1%.

Caveat: the test misses from round 3 (which include self-employed poets and tutors) had been read before this list was
reviewed. Those occupations are on it because of their dollar rank, not picked from the misses, but the test sample is
now used up for tuning. The next score needs a fresh sample, labeled by a person.

### What would move it further

On test, about 20 of the unknown points sit with small named employers ("DELTA CONSTRUCTORS", "ZARO'S FAMILY BAKERY").
Across both cycles there are 263,879 distinct unclear employer and occupation pairs ($395M); the 100,000 largest hold
89% of those dollars. Reviewing by hand past the top 5,000 employers hits diminishing returns. A batch run of Claude
Haiku 5.5 over every pair, keeping only confident answers, is estimated at about $6 at list price (about 7M input and
10M output tokens, including its reasoning), before any batch discount. It needs a person-labeled test sample to score
it, since the current labels also come from Claude.


### Round 5 (in progress): a fresh sample, labeled by a person and another AI

Every label so far came from Claude, which also wrote the rules and reviewed the lists. Round 5 takes that out of the
answer key.
- `data/audit_2024_fresh_sample.csv`: 100 new draws (34 list, 66 tail, by dollar weight, seed 2026), none of them a
  pair already in the dev or test sample.
- Three raters label the same records from the employer and occupation text alone, following the same written rules
  (`data/audit_2024_fresh_prompt.txt`, which is also the exact prompt given to the outside AI): Ren, ChatGPT and
  Claude. Claude's labels (`data/audit_2024_fresh_labels_claude.csv`) were committed before anyone else labeled.
- `pipeline/audit_compare.py` scores the pipeline against each rater, reports how often each pair of raters agrees
  (with Cohen's kappa), and scores the pipeline on the records where Ren and the outside AI agree, the least disputed
  answer key. Records they disagree on go to `data/audit_2024_fresh_disputed.csv`.
- Nothing will be tuned against this sample.

## The site (phase 3, first page)

`site/app.py` is a two-page Streamlit app. Members (the default) lets you pick a member and see where their individual money came from. It reads two small files
written by `pipeline/aggregate.py` (`site/data/`, about 300 KB), so it runs on a free host.

- **Every dollar is shown.** The first chart splits each member's individual money into placed in an industry,
  industry unclear, retired, not employed, no information given, and unitemized. The industry chart below it uses
  the same total, so no bar reads bigger than it is.
- **Same charts for everyone,** sorted by the data, with a tick for the median of the member's party in their chamber.
- **Totals** come from the FEC all-candidates summary, which also covers senators not on the ballot that cycle.
- **Links** to each committee's FEC page and to PartyCohesion for voting records. No vote appears on this site.
- **Two cycles, 2022 and 2024.** A switch at the top of both pages picks the cycle. Each member page ends with how
  their money changed between cycles: a hollow dot for one, a filled dot for the other. On the Industries page a tick on
  each bar shows the other cycle. The reviewed employer list was built from 2024 donors, so slightly more 2022 money is
  "unclear" (11.9% against 10.1%).
- **Color with a job.** Each kind of money has its own color (industry green, unclear blue, retired amber, not employed
  purple, unitemized clay, missing gray), checked with a palette validator for color-blind readers and always labeled in
  words. The green header panel carries the site's mark: one strip showing every dollar current members raised, by kind.
- **Former members and a filter.** Each cycle now includes everyone who served in the Congress that sat during it
  (from congress-legislators' historical file), not only today's members: 603 profiles for 2024 (85 former, such as
  Jon Tester and Sherrod Brown) and 615 for 2022. Members whose committee only paid refunds in a cycle (Mitt Romney
  in 2024) are left out.
- **The filter sorts the data, not just the list.** The filter button above the member list picks a group by status
  (serving now by default, or former), chamber, party, state, money raised, and whether the member had a committee in
  both cycles. Everything on the Members page follows that group: the header strip and its total, a summary of the
  group (total, median member, largest industry), each industry's share of the group's money with a tick for all
  current members, and a sortable table of every member in the group with a link to their page and a CSV download.
  The Industries page has the same filter, and the setting carries over between the two pages, so its party and
  chamber bars, its top 15 and its member table follow the same group. Its tick for the other cycle shows the same
  members, those who had a committee then.
- **Industries page** (`site/views/industries.py`): pick an industry and see its share of each party's money in each
  chamber, and the 15 members for whom it made up the largest share (among members who raised at least $250K from
  individuals, so a few small gifts can't top the list). A table lists every member with a link to their profile.

```bash
pip install -r site/requirements.txt
streamlit run site/app.py
```

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
python load_fec.py --cycle 2022            # the 2022 zip's itcont.txt is incomplete, so this reads its by_date/ files
python feasibility.py --cycle 2024         # writes data/feasibility_2024.json
python audit_sample.py --cycle 2024        # draws an audit sample (the committed files are the record; later rule changes mean a rerun draws different pairs)
python audit.py --cycle 2024               # scores the pipeline on the dev sample
python audit.py --cycle 2024 --set test    # and on the held-out test sample
python audit_compare.py --cycle 2024       # the fresh sample, against each rater
python aggregate.py --cycle 2024           # per-member totals for the site (run for 2022 as well)
cd .. && pytest -q
```

Raw downloads and the DuckDB file go in `data/raw/`, which git ignores.

## Data sources

- [FEC bulk data](https://www.fec.gov/data/browse-data/?tab=bulk-data): individual contributions, candidate master,
  candidate-committee linkage, and current campaigns summary. Public, no key needed.
- [congress-legislators](https://github.com/unitedstates/congress-legislators): Bioguide and FEC candidate IDs for
  current members.
