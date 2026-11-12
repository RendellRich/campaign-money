"""Label the long tail with an LLM: the employer and occupation pairs the rules and reviewed lists leave unclear.

The reviewed employer list stops at the top 5,000 employers, and past that each employer holds very little money, so
reviewing by hand stops paying off. This sends every still-unclear pair to Claude Haiku 5.5 through the Message
Batches API, with the same written rules every human and AI rater was given (labeling_rules.py), and keeps the answer
only where the model is confident. Nothing here changes the site: industry.py uses these labels only when
USE_LLM_TAIL is switched on, so they can be scored against a person's labels first (audit_compare.py --with-llm).

  python pipeline/llm_tail.py export               # needs the FEC database: writes data/llm/unclear_pairs.csv.gz
  python pipeline/llm_tail.py dry-run --limit 300  # builds requests, prints one and a cost estimate, sends nothing
  python pipeline/llm_tail.py run                  # needs ANTHROPIC_API_KEY: submit, wait, collect
  python pipeline/llm_tail.py collect --batch ID   # pick up a batch that was still running when `run` stopped
  python pipeline/llm_tail.py combine A.csv.gz B.csv.gz  # keep only what two separate runs agree on

Two runs of the same pairs agree on the label far more often than on the confidence, and where both call a pair high
confidence they have agreed on the label every time in testing. So the labels the site may use come from two full runs:
`combine` keeps a pair only when both runs placed it in the same industry with high confidence.

The run is meant for the manual GitHub Action (.github/workflows/llm-tail.yml), which holds the key as a secret.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import sys
import time
from pathlib import Path

import pandas as pd

from labeling_rules import CODES, RULES

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "llm"
PAIRS = OUT / "unclear_pairs.csv.gz"
LABELS = OUT / "tail_labels.csv.gz"
MODEL = "claude-haiku-5-5"
CHUNK = 100                      # pairs per request
MAX_TOKENS = 8000                # thinking plus the CSV answer
# List prices for Haiku 5.5 with prompts under 100K tokens, in dollars per million tokens. The Batch API halves both.
PRICE_IN, PRICE_OUT = 0.10, 0.50
ALLOWED = {c for c, _ in CODES}

SYSTEM = f"""You label political donors by the industry they work in, from what each donor wrote on a Federal Election Commission filing. Each record has an id, the employer the donor wrote, and the occupation.

{RULES}

Industry codes (use these exact codes):
""" + "\n".join(f"- {c}: {d}" for c, d in CODES) + """

Reply with only CSV lines, no header and no other text: id,label,confidence
- one line for every record, in the order given
- label is one code from the list
- confidence is high or low"""


def pair_id(employer: str, occupation: str) -> str:
    return hashlib.sha1(f"{employer}|{occupation}".encode()).hexdigest()[:12]


def export() -> pd.DataFrame:
    """Every pair the pipeline leaves unclear, in both cycles, with its dollars. Run where the FEC database is."""
    import duckdb

    from employer_status import HAS_INDUSTRY_SIGNAL, status
    from feasibility import INDIVIDUAL
    from industry import industry
    from industry_rules import norm
    from load_fec import DB
    from member_committees import committees

    con = duckdb.connect(str(DB), read_only=True)
    parts = []
    for cycle in (2024, 2022):
        cm = sorted({c for cs in committees(cycle)["cmtes"] for c in cs})
        con.execute("CREATE OR REPLACE TEMP TABLE cur AS SELECT unnest(?) AS cmte_id", [cm])
        parts.append(con.execute(f"""SELECT upper(trim(coalesce(employer, ''))) AS employer,
                                            upper(trim(coalesce(occupation, ''))) AS occupation, sum(amt) AS dollars
                                     FROM contrib JOIN cur USING (cmte_id) WHERE cycle = {cycle} AND {INDIVIDUAL}
                                     GROUP BY 1, 2 HAVING sum(amt) > 0""").df())
    g = pd.concat(parts).groupby(["employer", "occupation"], as_index=False)["dollars"].sum()
    g = g[[status(e, o) in HAS_INDUSTRY_SIGNAL for e, o in zip(g["employer"], g["occupation"])]]
    g = g[[industry(e, o)[0] == "unknown" for e, o in zip(g["employer"], g["occupation"])]]
    # One row per normalized pair: that is how industry() looks labels up.
    g["employer"], g["occupation"] = g["employer"].map(norm), g["occupation"].map(norm)
    g = g.groupby(["employer", "occupation"], as_index=False)["dollars"].sum().sort_values("dollars", ascending=False)
    g.insert(0, "pair_id", [pair_id(e, o) for e, o in zip(g["employer"], g["occupation"])])
    g["dollars"] = g["dollars"].round().astype(int)
    OUT.mkdir(parents=True, exist_ok=True)
    g.to_csv(PAIRS, index=False, compression="gzip")
    print(f"{len(g):,} unclear pairs, ${g['dollars'].sum() / 1e6:,.0f}M, written to {PAIRS.relative_to(ROOT)}")
    return g


def load_pairs(limit: int | None = None) -> pd.DataFrame:
    p = pd.read_csv(PAIRS, dtype={"employer": str, "occupation": str}, keep_default_na=False)
    return p.head(limit) if limit else p


def requests(pairs: pd.DataFrame, chunk: int = CHUNK) -> list[dict]:
    """One Message Batches request per chunk of pairs. The system prompt is the same in each, so it is cached."""
    out = []
    for i in range(0, len(pairs), chunk):
        part = pairs.iloc[i:i + chunk]
        buf = io.StringIO()
        part[["pair_id", "employer", "occupation"]].rename(columns={"pair_id": "id"}).to_csv(buf, index=False)
        out.append({"custom_id": f"chunk-{i // chunk:05d}", "params": {
            "model": MODEL, "max_tokens": MAX_TOKENS,
            "output_config": {"effort": "low"},
            "system": [{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
            "messages": [{"role": "user", "content": "Records:\n" + buf.getvalue()}]}})
    return out


def estimate(reqs: list[dict], out_tokens_per_pair: int = 12, thinking_per_request: int = 1500) -> dict:
    """Rough token and dollar estimate. About 4 characters a token, plus 30% for Haiku 5.5's newer tokenizer."""
    chars = sum(len(r["params"]["system"][0]["text"]) + len(r["params"]["messages"][0]["content"]) for r in reqs)
    pairs = sum(r["params"]["messages"][0]["content"].count("\n") - 2 for r in reqs)
    tin = chars / 4 * 1.3
    tout = pairs * out_tokens_per_pair + len(reqs) * thinking_per_request
    full = tin / 1e6 * PRICE_IN + tout / 1e6 * PRICE_OUT
    return {"requests": len(reqs), "pairs": pairs, "input_tokens_M": round(tin / 1e6, 1),
            "output_tokens_M": round(tout / 1e6, 1), "list_price_usd": round(full, 2), "batch_price_usd": round(full / 2, 2)}


LINE = re.compile(r"^\s*([0-9a-f]{12})\s*,\s*([a-z_ ]+?)\s*,\s*(high|low)\s*$", re.I)


def parse(text: str, expected: set[str]) -> list[dict]:
    """Read the model's CSV lines. Anything malformed, off the code list, or not one of this chunk's ids is dropped."""
    rows = []
    for line in text.splitlines():
        m = LINE.match(line)
        if not m:
            continue
        pid, label, conf = m.group(1).lower(), m.group(2).strip().lower(), m.group(3).lower()
        label = label.replace(" ", "_") if label != "not employed" else label
        if pid in expected and label in ALLOWED:
            rows.append({"pair_id": pid, "label": label, "confidence": conf})
    return rows


def collect(client, batch_id: str, pairs: pd.DataFrame) -> pd.DataFrame:
    by_chunk = {f"chunk-{i // CHUNK:05d}": set(pairs["pair_id"].iloc[i:i + CHUNK]) for i in range(0, len(pairs), CHUNK)}
    rows, failed, usage = [], [], {"input": 0, "output": 0, "cache_read": 0}
    for res in client.messages.batches.results(batch_id):
        if res.result.type != "succeeded":
            failed.append(res.custom_id)
            continue
        msg = res.result.message
        usage["input"] += msg.usage.input_tokens
        usage["output"] += msg.usage.output_tokens
        usage["cache_read"] += getattr(msg.usage, "cache_read_input_tokens", 0) or 0
        text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
        rows += parse(text, by_chunk.get(res.custom_id, set()))
    got = pd.DataFrame(rows, columns=["pair_id", "label", "confidence"]).drop_duplicates("pair_id")
    out = pairs.merge(got, on="pair_id")[["pair_id", "employer", "occupation", "dollars", "label", "confidence"]]
    out.to_csv(LABELS, index=False, compression="gzip")
    report = {"batch": batch_id, "pairs_sent": len(pairs), "labeled": len(out), "failed_requests": failed,
              "high_confidence": int((out["confidence"] == "high").sum()),
              "placed_high": int(((out["confidence"] == "high") & (out["label"] != "unknown")).sum()),
              "placed_high_dollars": int(out.loc[(out["confidence"] == "high") & (out["label"] != "unknown"), "dollars"].sum()),
              "usage_tokens": usage}
    (OUT / "tail_run.json").write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps(report, indent=1))
    return out


def combine(first: Path, second: Path, out: Path = LABELS) -> pd.DataFrame:
    """Keep a pair only where two runs gave the same industry, both with high confidence."""
    a = pd.read_csv(first, dtype=str, keep_default_na=False)
    b = pd.read_csv(second, dtype=str, keep_default_na=False)
    m = a.merge(b[["pair_id", "label", "confidence"]], on="pair_id", suffixes=("", "_2"))
    keep = m[(m["label"] == m["label_2"]) & (m["confidence"] == "high") & (m["confidence_2"] == "high")]
    keep = keep[["pair_id", "employer", "occupation", "dollars", "label", "confidence"]]
    keep.to_csv(out, index=False, compression="gzip")
    placed = keep[~keep["label"].isin(["unknown", "retired", "not employed", "missing"])]
    report = {"pairs_in_both": len(m), "same_label": round(float((m["label"] == m["label_2"]).mean()) * 100, 1),
              "kept": len(keep), "kept_with_an_industry": len(placed),
              "kept_industry_dollars": int(placed["dollars"].astype(int).sum())}
    print(json.dumps(report, indent=1))
    return keep


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("step", choices=["export", "dry-run", "run", "collect", "combine"])
    ap.add_argument("files", nargs="*", help="for combine: the two runs' tail_labels.csv.gz")
    ap.add_argument("--limit", type=int, default=None, help="only the N pairs with the most dollars")
    ap.add_argument("--batch", default=None, help="batch id, for collect")
    ap.add_argument("--wait-minutes", type=int, default=300)
    a = ap.parse_args()

    if a.step == "export":
        export()
        return
    if a.step == "combine":
        combine(Path(a.files[0]), Path(a.files[1]))
        return
    pairs = load_pairs(a.limit)
    reqs = requests(pairs)
    if a.step == "dry-run":
        print(json.dumps(reqs[0], indent=1)[:4000])
        print(json.dumps(estimate(reqs), indent=1))
        return

    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY is not set. Run this from the GitHub Action, which reads it from the repo's secrets.")
    import anthropic
    client = anthropic.Anthropic()
    if a.step == "collect":
        collect(client, a.batch, pairs)
        return
    print(json.dumps(estimate(reqs), indent=1))
    batch = client.messages.batches.create(requests=reqs)
    print(f"submitted batch {batch.id} with {len(reqs)} requests")
    (OUT / "tail_batch_id.txt").write_text(batch.id + "\n")
    deadline = time.time() + a.wait_minutes * 60
    while time.time() < deadline:
        b = client.messages.batches.retrieve(batch.id)
        print(f"{b.processing_status}: {b.request_counts}")
        if b.processing_status == "ended":
            collect(client, batch.id, pairs)
            return
        time.sleep(60)
    print(f"still running; collect later with: python pipeline/llm_tail.py collect --batch {batch.id}")


if __name__ == "__main__":
    main()
