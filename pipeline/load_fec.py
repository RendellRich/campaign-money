"""Download FEC bulk files and load individual contributions to members' committees into DuckDB.

The individual contributions file (indiv24.zip) is 4.2 GB zipped and 11 GB as text. It is streamed straight from the
zip into DuckDB and filtered to the committees that matter, so the full text never lands on disk.

  python pipeline/load_fec.py --cycle 2024        # about 3 minutes once the zip is downloaded
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
DB = RAW / "fec.duckdb"
BULK = "https://www.fec.gov/files/bulk-downloads/{cycle}/{name}"
INDIV = ["cmte_id", "amndt_ind", "rpt_tp", "transaction_pgi", "image_num", "transaction_tp", "entity_tp", "name",
         "city", "state", "zip_code", "employer", "occupation", "transaction_dt", "transaction_amt", "other_id",
         "tran_id", "file_num", "memo_cd", "memo_text", "sub_id"]


def fetch(cycle: int, name: str) -> Path:
    path = RAW / str(cycle) / name
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        print(f"downloading {name}", file=sys.stderr)
        urllib.request.urlretrieve(BULK.format(cycle=cycle, name=name), path)
    return path


def unzip(path: Path, member: str) -> Path:
    out = path.with_name(f"{path.stem}_{member}")
    if not out.exists():
        with zipfile.ZipFile(path) as z, z.open(member) as src, open(out, "wb") as dst:
            dst.write(src.read())
    return out


def load(cycle: int, cmtes: list[str]):
    import duckdb
    con = duckdb.connect(str(DB))
    con.execute("CREATE OR REPLACE TABLE cmtes AS SELECT unnest(?) AS cmte_id", [cmtes])
    zpath = fetch(cycle, f"indiv{str(cycle)[2:]}.zip")
    cols = "{" + ",".join(f"'{c}':'VARCHAR'" for c in INDIV) + "}"
    t = time.time()
    # itcont.txt should be the whole file, and by_date/ the same rows split by date. They match for 2024, but in the
    # 2022 zip itcont.txt is 4.5 GB against 12.1 GB by date, so read whichever holds more.
    with zipfile.ZipFile(zpath) as z:
        whole = sum(i.file_size for i in z.infolist() if i.filename == "itcont.txt")
        parts = sum(i.file_size for i in z.infolist() if i.filename.startswith("by_date/"))
    members = ["itcont.txt"] if whole >= parts else ["by_date/*"]
    print(f"reading {members[0]} ({max(whole, parts) / 1e9:.1f} GB)", file=sys.stderr)
    unz = subprocess.Popen(["unzip", "-p", str(zpath), *members], stdout=subprocess.PIPE)
    # DuckDB reads the pipe through a file descriptor rather than this process's stdin.
    # One table holds every cycle; loading a cycle replaces only that cycle's rows.
    con.execute("""CREATE TABLE IF NOT EXISTS contrib (cycle INTEGER, cmte_id VARCHAR, transaction_tp VARCHAR,
                    entity_tp VARCHAR, name VARCHAR, state VARCHAR, zip5 VARCHAR, employer VARCHAR, occupation VARCHAR,
                    amt DOUBLE, memo_cd VARCHAR, sub_id VARCHAR)""")
    con.execute("DELETE FROM contrib WHERE cycle = ?", [cycle])
    con.execute(f"""
        INSERT INTO contrib
        SELECT {cycle} AS cycle, c.cmte_id, transaction_tp, entity_tp, name, state, left(zip_code, 5) AS zip5,
               employer, occupation, try_cast(transaction_amt AS DOUBLE) AS amt, memo_cd, sub_id
        FROM read_csv('/dev/fd/{unz.stdout.fileno()}', delim='|', header=false, quote='', escape='',
                      columns={cols}, ignore_errors=true, strict_mode=false) c
        JOIN cmtes USING (cmte_id)
    """)
    unz.wait()
    n = con.execute("SELECT count(*) FROM contrib WHERE cycle = ?", [cycle]).fetchone()[0]
    print(f"loaded {n:,} contributions in {time.time() - t:.0f} s -> {DB.relative_to(ROOT)}", file=sys.stderr)
    return con


def main() -> None:
    from member_committees import committees
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--cycle", type=int, default=2024)
    cycle = ap.parse_args().cycle
    cmtes = sorted({c for cs in committees(cycle)["cmtes"] for c in cs})
    load(cycle, cmtes)


if __name__ == "__main__":
    main()
