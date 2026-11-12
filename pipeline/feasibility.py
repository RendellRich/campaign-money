"""Phase 1 report: how much of members' itemized money can be placed in an industry at all.

Reads the contributions loaded by pipeline/load_fec.py and writes data/feasibility_<cycle>.json.

  python pipeline/feasibility.py --cycle 2024
"""
from __future__ import annotations

import argparse
import json

import duckdb
import pandas as pd

from employer_status import HAS_INDUSTRY_SIGNAL, status
from industry_rules import norm
from load_fec import DB, ROOT, fetch, unzip
from member_committees import committees

# Contributions from individuals that are money in: not memo lines, which annotate another line.
INDIVIDUAL = "entity_tp = 'IND' AND coalesce(memo_cd, '') <> 'X' AND transaction_tp IN ('15', '15E', '15C', '15J')"


def report(cycle: int) -> dict:
    con = duckdb.connect(str(DB), read_only=True)
    g = con.execute(f"""SELECT cmte_id, employer, occupation, sum(amt) AS dollars, count(*) AS n
                        FROM contrib WHERE cycle = {cycle} AND {INDIVIDUAL} GROUP BY 1, 2, 3""").df()
    g["status"] = [status(e, o) for e, o in zip(g["employer"], g["occupation"])]
    out = {"cycle": cycle, "itemized_dollars": float(g["dollars"].sum()), "itemized_records": int(g["n"].sum())}

    by = g.groupby("status")[["dollars", "n"]].sum().reindex(
        [s for s in ["named employer", "retired", "not employed", "self-employed, occupation given",
                     "missing or requested", "occupation only", "self-employed, no occupation"]]).fillna(0)
    by["share"] = (by["dollars"] / by["dollars"].sum() * 100).round(1)
    out["by_status"] = by.reset_index().to_dict("records")
    usable = by.drop(index=["missing or requested", "self-employed, no occupation"])["dollars"].sum()
    out["usable_share"] = round(usable / by["dollars"].sum() * 100, 1)
    signal = g[g["status"].isin(HAS_INDUSTRY_SIGNAL)]
    out["industry_signal_share"] = round(signal["dollars"].sum() / g["dollars"].sum() * 100, 1)

    per = g.assign(sig=g["status"].isin(HAS_INDUSTRY_SIGNAL)).groupby("cmte_id").apply(
        lambda x: pd.Series({"dollars": x["dollars"].sum(), "share": x.loc[x["sig"], "dollars"].sum() / x["dollars"].sum() * 100}),
        include_groups=False)
    per = per[per["dollars"] > 10_000]
    out["per_committee_industry_signal"] = {k: round(float(v), 1) for k, v in per["share"].describe().items()}

    named = g[g["status"] == "named employer"].assign(emp=lambda x: x["employer"].map(norm))
    e = named.groupby("emp")["dollars"].sum().sort_values(ascending=False)
    out["distinct_employers"] = int(len(e))
    out["top_employer_coverage"] = {k: round(e.head(k).sum() / e.sum() * 100, 1) for k in (100, 1000, 5000, 20000)}

    yy = str(cycle)[2:]
    webl = pd.read_csv(unzip(fetch(cycle, f"webl{yy}.zip"), f"webl{yy}.txt"), sep="|", header=None, dtype={0: str})
    cn = pd.read_csv(unzip(fetch(cycle, f"cn{yy}.zip"), "cn.txt"), sep="|", header=None, dtype=str)[[0, 9]]
    pccs = {c for cs in committees(cycle)["cmtes"] for c in cs}
    total = float(webl[webl[0].isin(cn[cn[9].isin(pccs)][0])][17].sum())
    out["total_individual_dollars"] = total
    out["itemized_share"] = round(out["itemized_dollars"] / total * 100, 1) if total else None
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--cycle", type=int, default=2024)
    cycle = ap.parse_args().cycle
    out = report(cycle)
    path = ROOT / "data" / f"feasibility_{cycle}.json"
    path.write_text(json.dumps(out, indent=1) + "\n")
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
