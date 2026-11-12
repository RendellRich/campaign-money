"""Score the pipeline against the blind audit labels.

Inputs: data/audit_<cycle>_sample.csv (from audit_sample.py) and data/audit_<cycle>_labels.csv, which an AI assistant
(Claude) filled in from the employer and occupation text alone, before seeing any pipeline output. Each label has a
confidence: "low" means a reasonable person could pick a different industry.

Every draw is one dollar picked at random, so the share of draws in each outcome estimates the share of dollars:
  correct   the pipeline gave the labeled answer
  wrong     the pipeline gave a different industry (or status)
  left      the pipeline said "unknown" but the label names an industry (work for the classifier)

  python pipeline/audit.py --cycle 2024
"""
from __future__ import annotations

import argparse
import json
import math

import pandas as pd

from industry import industry
from load_fec import ROOT


def outcome(predicted: str, label: str) -> str:
    if predicted == label:
        return "correct"
    if predicted == "unknown":
        return "left"
    return "wrong"


def score(sample: pd.DataFrame, labels: pd.DataFrame) -> pd.DataFrame:
    s = sample.merge(labels, on="id", how="inner", validate="one_to_one")
    s["predicted"], s["how"] = zip(*[industry(e, o) for e, o in zip(s["employer"], s["occupation"])])
    s["outcome"] = [outcome(p, l) for p, l in zip(s["predicted"], s["label"])]
    return s


def rates(s: pd.DataFrame) -> dict:
    n = int(s["draws"].sum())
    out = {"draws": n}
    for k in ("correct", "wrong", "left"):
        p = float(s.loc[s["outcome"] == k, "draws"].sum() / n) if n else 0.0
        out[k] = round(p * 100, 1)
        out[f"{k}_ci95"] = [round(x * 100, 1) for x in wilson(p, n)]
    placed = s[s["outcome"] != "left"]["draws"].sum()
    out["correct_when_placed"] = round(float(s.loc[s["outcome"] == "correct", "draws"].sum() / placed * 100), 1) if placed else None
    return out


def wilson(p: float, n: int, z: float = 1.96) -> tuple[float, float]:
    if not n:
        return (0.0, 1.0)
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def combined(s: pd.DataFrame) -> dict:
    """Weight each stratum by its share of industry-signal dollars."""
    w = s.groupby("stratum")["stratum_dollars"].first()
    w = w / w.sum()
    out = {}
    for k in ("correct", "wrong", "left"):
        p, var = 0.0, 0.0
        for stratum, weight in w.items():
            t = s[s["stratum"] == stratum]
            n = t["draws"].sum()
            q = t.loc[t["outcome"] == k, "draws"].sum() / n
            p += weight * q
            var += weight ** 2 * q * (1 - q) / n
        out[k] = round(p * 100, 1)
        out[f"{k}_ci95"] = [round(max(0, p - 1.96 * math.sqrt(var)) * 100, 1), round(min(1, p + 1.96 * math.sqrt(var)) * 100, 1)]
    out["stratum_weights"] = {k: round(float(v), 3) for k, v in w.items()}
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--cycle", type=int, default=2024)
    cycle = ap.parse_args().cycle
    sample = pd.read_csv(ROOT / "data" / f"audit_{cycle}_sample.csv", dtype={"employer": str, "occupation": str}, keep_default_na=False)
    labels = pd.read_csv(ROOT / "data" / f"audit_{cycle}_labels.csv", dtype=str, keep_default_na=False)
    s = score(sample, labels)
    report = {"cycle": cycle, "pairs": len(s), "all": combined(s),
              "by_stratum": {k: rates(t) for k, t in s.groupby("stratum")},
              "high_confidence_labels": {k: rates(t) for k, t in s[s["confidence"] == "high"].groupby("stratum")}}
    misses = s[s["outcome"] != "correct"].sort_values(["stratum", "outcome", "id"])
    misses[["id", "stratum", "employer", "occupation", "label", "confidence", "predicted", "how", "outcome", "draws"]].to_csv(
        ROOT / "data" / f"audit_{cycle}_misses.csv", index=False)
    (ROOT / "data" / f"audit_{cycle}.json").write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
