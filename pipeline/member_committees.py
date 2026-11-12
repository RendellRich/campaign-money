"""Map current members of Congress to their principal campaign committees for one FEC cycle.

Bioguide IDs and FEC candidate IDs come from congress-legislators (legislators-current.json). The FEC
candidate-committee linkage file (ccl) gives each candidate's principal campaign committee (designation "P").

  python pipeline/member_committees.py --cycle 2024
"""
from __future__ import annotations

import argparse
import json
import urllib.request
from pathlib import Path

import pandas as pd

from load_fec import RAW, fetch, unzip

LEGISLATORS = "https://unitedstates.github.io/congress-legislators/legislators-current.json"
CCL = ["cand_id", "cand_elec_yr", "fec_elec_yr", "cmte_id", "cmte_tp", "cmte_dsgn", "link_id"]


def members() -> pd.DataFrame:
    path = RAW / "legislators-current.json"
    if not path.exists():
        RAW.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(LEGISLATORS, path)
    rows = []
    for m in json.loads(path.read_text()):
        t = m["terms"][-1]
        for cand in m["id"].get("fec", []):
            rows.append({"bioguide_id": m["id"]["bioguide"], "name": m["name"].get("official_full"),
                         "chamber": {"rep": "House", "sen": "Senate"}[t["type"]], "party": t["party"],
                         "state": t["state"], "cand_id": cand})
    return pd.DataFrame(rows)


def committees(cycle: int) -> pd.DataFrame:
    """One row per member: bioguide_id, chamber, party, state and their principal committee IDs (may be empty)."""
    yy = str(cycle)[2:]
    ccl = pd.read_csv(unzip(fetch(cycle, f"ccl{yy}.zip"), "ccl.txt"), sep="|", header=None, names=CCL, dtype=str)
    pcc = ccl[ccl["cmte_dsgn"] == "P"][["cand_id", "cmte_id"]].drop_duplicates()
    m = members().merge(pcc, on="cand_id", how="left")
    return (m.groupby("bioguide_id")
            .agg(name=("name", "first"), chamber=("chamber", "first"), party=("party", "first"),
                 state=("state", "first"), cmtes=("cmte_id", lambda s: sorted(set(s.dropna()))))
            .reset_index())


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--cycle", type=int, default=2024)
    per = committees(ap.parse_args().cycle)
    per["has"] = per["cmtes"].str.len() > 0
    print(f"{per['has'].sum()} of {len(per)} members have a principal campaign committee")
    print(per.groupby("chamber")["has"].agg(["sum", "count"]).to_string())


if __name__ == "__main__":
    main()
