"""Draw the blind audit sample: employer and occupation pairs, picked in proportion to their dollars.

Each draw picks one dollar of itemized money that carries an industry signal, then records the employer and
occupation written on that contribution. So a pair with twice the dollars is twice as likely to be drawn, and the
share of draws labeled correctly estimates the share of dollars labeled correctly.

Two strata, sampled separately so the long tail gets enough draws to measure:
  list  the employer is on data/employer_industry.csv (the top 1,000)
  tail  everything else, which is what the rules and the classifier have to handle

The sample file holds only what the donor wrote (no names, no rule output), so it can be labeled blind.

  python pipeline/audit_sample.py --cycle 2024                        # the first sample, now the dev set
  python pipeline/audit_sample.py --cycle 2024 --seed 2025 --set test  # the held-out test set
  python pipeline/audit_sample.py --cycle 2024 --seed 2026 --set fresh # labeled by a person and another AI
"""
from __future__ import annotations

import argparse

import duckdb
import numpy as np
import pandas as pd

from employer_status import HAS_INDUSTRY_SIGNAL, status
from feasibility import INDIVIDUAL
from industry import mapping
from industry_rules import norm
from load_fec import DB, ROOT
from member_committees import committees

DRAWS = {"list": 100, "tail": 200}
SEED = 2024


def pairs() -> pd.DataFrame:
    # Current members' committees only: the samples were drawn before former members were loaded, and this keeps a
    # rerun drawing the same pairs.
    current = committees(2024)
    cmtes = sorted({c for cs in current[current["current"]]["cmtes"] for c in cs})
    con = duckdb.connect(str(DB), read_only=True)
    con.execute("CREATE TEMP TABLE cur AS SELECT unnest(?) AS cmte_id", [cmtes])
    g = con.execute(f"""SELECT upper(trim(coalesce(employer, ''))) AS employer,
                               upper(trim(coalesce(occupation, ''))) AS occupation, sum(amt) AS dollars
                        FROM contrib JOIN cur USING (cmte_id) WHERE cycle = 2024 AND {INDIVIDUAL} GROUP BY 1, 2 HAVING sum(amt) > 0""").df()
    g = g[[status(e, o) in HAS_INDUSTRY_SIGNAL for e, o in zip(g["employer"], g["occupation"])]]
    listed = set(mapping())
    g["stratum"] = np.where(g["employer"].map(norm).isin(listed), "list", "tail")
    return g.reset_index(drop=True)


def draw(g: pd.DataFrame, draws: dict[str, int] = DRAWS, seed: int = SEED, prefix: str = "A") -> pd.DataFrame:
    """Probability-proportional-to-dollars draws, with replacement, per stratum. One row per distinct pair."""
    rng = np.random.default_rng(seed)
    out = []
    for stratum, n in draws.items():
        s = g[g["stratum"] == stratum].sort_values(["employer", "occupation"]).reset_index(drop=True)
        cum = s["dollars"].cumsum().to_numpy()
        hit = np.searchsorted(cum, rng.uniform(0, cum[-1], n), side="right")
        picked = s.iloc[hit].groupby(["employer", "occupation"], as_index=False).agg(
            draws=("dollars", "size"), dollars=("dollars", "first"))
        out.append(picked.assign(stratum=stratum, stratum_dollars=float(cum[-1])))
    sample = pd.concat(out, ignore_index=True).sample(frac=1, random_state=seed).reset_index(drop=True)
    sample.insert(0, "id", [f"{prefix}{i:03d}" for i in range(1, len(sample) + 1)])
    return sample


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--cycle", type=int, default=2024)
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--set", default="", help='"" for the dev sample, "test" for the held-out one')
    a = ap.parse_args()
    cycle = a.cycle
    g = pairs()
    draws = DRAWS
    if a.set == "fresh":
        # A third sample, scored by people and other AIs rather than tuned against: 100 draws split by the strata's
        # dollar weights, leaving out every pair already in the dev or test sample.
        seen = pd.concat([pd.read_csv(ROOT / "data" / f"audit_{cycle}{x}_sample.csv", dtype=str, keep_default_na=False)
                          for x in ("", "_test")])
        g = g[~(g["employer"] + "|" + g["occupation"]).isin(set(seen["employer"] + "|" + seen["occupation"]))]
        draws = {"list": 34, "tail": 66}
    prefix = {"": "A", "test": "B", "fresh": "C"}.get(a.set, "X")
    sample = draw(g, draws=draws, seed=a.seed, prefix=prefix)
    path = ROOT / "data" / f"audit_{cycle}{'_' + a.set if a.set else ''}_sample.csv"
    sample[["id", "stratum", "employer", "occupation", "draws", "dollars", "stratum_dollars"]].to_csv(path, index=False)
    print(sample.groupby("stratum").agg(pairs=("id", "size"), draws=("draws", "sum")))


if __name__ == "__main__":
    main()
