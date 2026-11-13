import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline"))
import industry as industry_module  # noqa: E402
import llm_tail  # noqa: E402

PAIRS = pd.DataFrame({"pair_id": [llm_tail.pair_id("DELTA CONSTRUCTORS", "CEO"), llm_tail.pair_id("ZAROS FAMILY BAKERY", "OWNER"),
                                  llm_tail.pair_id("PIONEER GROUP", "PRESIDENT")],
                      "employer": ["DELTA CONSTRUCTORS", "ZAROS FAMILY BAKERY", "PIONEER GROUP"],
                      "occupation": ["CEO", "OWNER", "PRESIDENT"], "dollars": [5000, 3000, 2000]})


def test_requests_carry_the_shared_rules_and_every_pair():
    reqs = llm_tail.requests(PAIRS, chunk=2)
    assert len(reqs) == 2
    p = reqs[0]["params"]
    assert p["model"] == "claude-haiku-5-5" and p["output_config"] == {"effort": "low"}
    assert llm_tail.RULES in p["system"][0]["text"]
    assert "temperature" not in p  # Haiku 5.5 takes no sampling parameters
    text = "".join(r["params"]["messages"][0]["content"] for r in reqs)
    assert all(pid in text for pid in PAIRS["pair_id"])
    assert "dollars" not in text  # the model sees only what the donor wrote


def test_parse_keeps_only_valid_lines_for_this_chunk():
    a, b, c = PAIRS["pair_id"]
    reply = f"{a},real_estate,high\n{b}, Consumer ,LOW\n{c},banking,high\nnot a line\n000000000000,law,high"
    rows = llm_tail.parse(reply, {a, b, c})
    assert rows == [{"pair_id": a, "label": "real_estate", "confidence": "high"},
                    {"pair_id": b, "label": "consumer", "confidence": "low"}]


class FakeBatches:
    def __init__(self, replies):
        self.replies = replies

    def results(self, batch_id):
        for cid, text in self.replies.items():
            msg = SimpleNamespace(content=[SimpleNamespace(type="text", text=text)],
                                  usage=SimpleNamespace(input_tokens=1000, output_tokens=50, cache_read_input_tokens=800))
            yield SimpleNamespace(custom_id=cid, result=SimpleNamespace(type="succeeded", message=msg))


def test_collect_writes_labels_and_the_switch_uses_only_confident_industries(tmp_path, monkeypatch):
    monkeypatch.setattr(llm_tail, "OUT", tmp_path)
    monkeypatch.setattr(llm_tail, "LABELS", tmp_path / "tail_labels.csv.gz")
    a, b, c = PAIRS["pair_id"]
    client = SimpleNamespace(messages=SimpleNamespace(batches=FakeBatches(
        {"chunk-00000": f"{a},real_estate,high\n{b},consumer,low\n{c},unknown,high"})))
    out = llm_tail.collect(client, "batch_test", PAIRS)
    assert len(out) == 3

    monkeypatch.setattr(industry_module, "LLM_TAIL", tmp_path / "tail_labels.csv.gz")
    industry_module.llm_tail.cache_clear()
    monkeypatch.setattr(industry_module, "USE_LLM_TAIL", False)
    assert industry_module.industry("DELTA CONSTRUCTORS", "CEO")[0] == "unknown"  # the switch turns them off
    monkeypatch.setattr(industry_module, "USE_LLM_TAIL", True)
    assert industry_module.industry("DELTA CONSTRUCTORS", "CEO") == ("real_estate", "llm")
    assert industry_module.industry("ZAROS FAMILY BAKERY", "OWNER")[0] == "unknown"  # low confidence is not used
    assert industry_module.industry("PIONEER GROUP", "PRESIDENT")[0] == "unknown"
    assert industry_module.industry("GOOGLE", "ENGINEER")[0] == "tech"  # the list still decides first
    industry_module.llm_tail.cache_clear()


def test_estimate_for_the_full_run_is_small():
    est = llm_tail.estimate(llm_tail.requests(llm_tail.load_pairs()))
    assert est["pairs"] == len(llm_tail.load_pairs())
    assert est["list_price_usd"] < 20


def test_combine_keeps_only_what_both_runs_agree_on_confidently(tmp_path):
    a, b, c = PAIRS["pair_id"]
    base = PAIRS.copy()
    one = base.assign(label=["real_estate", "consumer", "media"], confidence=["high", "high", "high"])
    two = base.assign(label=["real_estate", "consumer", "nonprofit"], confidence=["high", "low", "high"])
    one.to_csv(tmp_path / "1.csv.gz", index=False, compression="gzip")
    two.to_csv(tmp_path / "2.csv.gz", index=False, compression="gzip")
    keep = llm_tail.combine(tmp_path / "1.csv.gz", tmp_path / "2.csv.gz", tmp_path / "out.csv.gz")
    assert list(keep["pair_id"]) == [a]  # b dropped for low confidence once, c for a different label


def test_llm_labels_are_on_for_the_site():
    assert industry_module.USE_LLM_TAIL is True
    assert len(industry_module.llm_tail()) > 90_000
