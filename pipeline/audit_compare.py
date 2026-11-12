"""Score the pipeline on the fresh sample against several independent raters, and measure how often they agree.

Each rater labels the same 100 records (data/audit_<cycle>_fresh_sample.csv) from the employer and occupation text
alone, without seeing the pipeline's answer or each other's labels. One file per rater:

  data/audit_<cycle>_fresh_labels_<rater>.csv   columns: id, label, confidence (high or low), note

  python pipeline/audit_compare.py --cycle 2024

Reports, for each rater, the pipeline's dollar-weighted share right, wrong and left unknown (as audit.py does); for
each pair of raters, how often they gave the same label and Cohen's kappa (agreement beyond chance); and the
pipeline's score on the records where every person and outside AI agreed, which is the least disputable answer key.
"""
from __future__ import annotations

import argparse
import itertools
import json

import pandas as pd

from audit import combined, score
from industry_rules import INDUSTRIES
from load_fec import ROOT

ALLOWED = set(INDUSTRIES) | {"unknown", "retired", "not employed", "missing"}


def read_labels(path) -> pd.DataFrame:
    lab = pd.read_csv(path, dtype=str, keep_default_na=False)
    lab.columns = [c.strip().lower() for c in lab.columns]
    lab["label"] = lab["label"].str.strip().str.lower().str.replace(" ", "_").replace({"not_employed": "not employed"})
    lab["confidence"] = lab.get("confidence", pd.Series("", index=lab.index)).str.strip().str.lower()
    bad = sorted(set(lab["label"]) - ALLOWED)
    if bad:
        raise SystemExit(f"{path.name}: labels not in the list: {bad}")
    return lab[["id", "label", "confidence"]]


def kappa(a: pd.Series, b: pd.Series) -> float:
    agree = (a == b).mean()
    cats = set(a) | set(b)
    chance = sum((a == c).mean() * (b == c).mean() for c in cats)
    return round((agree - chance) / (1 - chance), 3) if chance < 1 else 1.0


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--cycle", type=int, default=2024)
    a = ap.parse_args()
    tag = f"{a.cycle}_fresh"
    sample = pd.read_csv(ROOT / "data" / f"audit_{tag}_sample.csv", dtype={"employer": str, "occupation": str},
                         keep_default_na=False)
    files = sorted((ROOT / "data").glob(f"audit_{tag}_labels_*.csv"))
    raters = {f.stem.rsplit("_", 1)[-1]: read_labels(f) for f in files}
    report = {"cycle": a.cycle, "records": len(sample), "raters": list(raters), "pipeline": {}, "agreement": {}}

    for name, lab in raters.items():
        s = score(sample, lab)
        report["pipeline"][name] = {"records": len(s), **combined(s)}

    wide = sample[["id"]].copy()
    for name, lab in raters.items():
        wide = wide.merge(lab[["id", "label"]].rename(columns={"label": name}), on="id", how="left")
    for x, y in itertools.combinations(raters, 2):
        both = wide[[x, y]].dropna()
        report["agreement"][f"{x} vs {y}"] = {"records": len(both), "same_label": round(float((both[x] == both[y]).mean()) * 100, 1),
                                              "kappa": kappa(both[x], both[y])}

    # The answer key nobody disputes: records where every rater other than Claude agrees. Claude wrote the rules and
    # reviewed the lists, so its labels are reported but kept out of the key.
    outside = [r for r in raters if r != "claude"]
    if len(outside) >= 2:
        w = wide.dropna(subset=outside)
        agreed = w[w[outside].nunique(axis=1) == 1]
        key = agreed[["id", outside[0]]].rename(columns={outside[0]: "label"}).assign(confidence="high")
        s = score(sample, key)
        report["pipeline"]["agreed by " + " and ".join(outside)] = {"records": len(s), **combined(s)}
        (ROOT / "data" / f"audit_{tag}_disputed.csv").write_text(
            wide[~wide["id"].isin(agreed["id"])].merge(sample[["id", "employer", "occupation"]], on="id")
            .to_csv(index=False))

    (ROOT / "data" / f"audit_{tag}.json").write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
