"""Per-member totals for the site: individual money by industry, with every share that isn't an industry kept.

Writes two small files to site/data/:
  members_<cycle>.csv          one row per member: name, chamber, party, state, individual money, itemized, unitemized
  member_money_<cycle>.csv     one row per member and category, in dollars

Categories add up to the member's total individual contributions:
  an industry      the donor's employer and occupation place them in one of the 20 industries
  unknown          they point to an industry, but the pipeline can't tell which
  retired          retired donors
  not employed     not employed, homemakers, students
  no information   employer and occupation missing, "information requested", or self-employed with no occupation
  unitemized       gifts from donors who gave $200 or less in the cycle, reported only as a total

  python pipeline/aggregate.py --cycle 2024
"""
from __future__ import annotations

import argparse

import duckdb
import pandas as pd

from feasibility import INDIVIDUAL
from industry import industry
from load_fec import DB, ROOT, fetch, unzip
from member_committees import committees, members as member_ids

SITE = ROOT / "site" / "data"
NOT_INDUSTRY = {"retired": "retired", "not employed": "not employed", "missing": "no information",
                "self-employed": "no information"}
# The reviewed employer list uses snake_case for its two status rows ("NOT EMPLOYED" variants, "RETIRED" variants).
SPELLING = {"not_employed": "not employed"}


def category(employer: str, occupation: str) -> str:
    ind, how = industry(employer, occupation)
    if how == "status":
        return NOT_INDUSTRY[ind]
    return SPELLING.get(ind, ind)


def build(cycle: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    con = duckdb.connect(str(DB), read_only=True)
    g = con.execute(f"""SELECT cmte_id, upper(trim(coalesce(employer, ''))) AS employer,
                               upper(trim(coalesce(occupation, ''))) AS occupation, sum(amt) AS dollars
                        FROM contrib WHERE {INDIVIDUAL} GROUP BY 1, 2, 3""").df()
    pairs = g[["employer", "occupation"]].drop_duplicates()
    pairs["category"] = [category(e, o) for e, o in zip(pairs["employer"], pairs["occupation"])]
    g = g.merge(pairs, on=["employer", "occupation"])

    m = committees(cycle)
    m = m[m["cmtes"].str.len() > 0]
    cm = m.explode("cmtes").rename(columns={"cmtes": "cmte_id"})[["bioguide_id", "cmte_id"]]

    # Keep a committee only for the member whose own FEC candidate ID names it as principal committee. The linkage
    # file can tie one committee to two members' IDs (it does for one House committee in 2024).
    yy = str(cycle)[2:]
    cn = pd.read_csv(unzip(fetch(cycle, f"cn{yy}.zip"), "cn.txt"), sep="|", header=None, dtype=str)[[0, 9]]
    cn = cn.rename(columns={0: "cand_id", 9: "cmte_id"})
    own = member_ids()[["bioguide_id", "cand_id"]].merge(cn, on="cand_id")[["bioguide_id", "cmte_id"]].drop_duplicates()
    shared = cm["cmte_id"].duplicated(keep=False)
    cm = pd.concat([cm[~shared], cm[shared].merge(own)]).drop_duplicates()
    money = (g.merge(cm, on="cmte_id").groupby(["bioguide_id", "category"], as_index=False)["dollars"].sum())

    # Total individual money per member from the FEC all-candidates summary (it includes senators not on the ballot
    # this cycle), matched through each principal committee.
    weball = pd.read_csv(unzip(fetch(cycle, f"weball{yy}.zip"), f"weball{yy}.txt"), sep="|", header=None,
                         dtype={0: str})
    cand = cn.rename(columns={"cand_id": "cand"}).merge(weball[[0, 17]].rename(columns={0: "cand", 17: "total"}))
    total = cand.merge(cm, on="cmte_id").drop_duplicates("cand").groupby("bioguide_id")["total"].sum()

    itemized = money.groupby("bioguide_id")["dollars"].sum()
    members = m.drop(columns="cmtes").set_index("bioguide_id")
    members["committees"] = cm.groupby("bioguide_id")["cmte_id"].agg(lambda c: ";".join(sorted(c)))
    members["itemized"] = itemized
    members["individual"] = total.reindex(members.index)
    members = members.dropna(subset=["itemized"])
    # Refunds and redesignations can leave the summary total a little under the itemized sum; never go negative.
    members["individual"] = members[["individual", "itemized"]].max(axis=1)
    members["unitemized"] = members["individual"] - members["itemized"]

    unit = members["unitemized"].rename("dollars").reset_index().assign(category="unitemized")
    money = pd.concat([money, unit[["bioguide_id", "category", "dollars"]]], ignore_index=True)
    money["dollars"] = money["dollars"].round(0).astype(int)
    members = members.reset_index()
    for c in ("itemized", "individual", "unitemized"):
        members[c] = members[c].round(0).astype(int)
    return members.sort_values("name"), money.sort_values(["bioguide_id", "dollars"], ascending=[True, False])


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--cycle", type=int, default=2024)
    cycle = ap.parse_args().cycle
    members, money = build(cycle)
    SITE.mkdir(parents=True, exist_ok=True)
    members.to_csv(SITE / f"members_{cycle}.csv", index=False)
    money.to_csv(SITE / f"member_money_{cycle}.csv", index=False)
    share = money.groupby("category")["dollars"].sum() / money["dollars"].sum() * 100
    print(f"{len(members)} members, ${members['individual'].sum() / 1e9:.2f}B individual money")
    print(share.sort_values(ascending=False).round(1).to_string())


if __name__ == "__main__":
    main()
