"""Create a local SQLite database for the existing ATLAS Growth JSON demo.

Standard library only. Refuses to overwrite an existing database unless --force.
No external data is downloaded. All supplied account records are synthetic.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from tempfile import TemporaryDirectory
from contextlib import closing
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent
SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE accounts (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  sector TEXT NOT NULL,
  motion TEXT NOT NULL CHECK(motion IN ('Acquire','Expand','Deepen')),
  hq TEXT,
  funding_amount_usd INTEGER DEFAULT 0,
  funding_date TEXT,
  federal_obligations_usd INTEGER DEFAULT 0,
  ttm_revenue_usd INTEGER DEFAULT 0,
  contracted_annual_commitment_usd INTEGER DEFAULT 0,
  scenario_annual_value_usd INTEGER DEFAULT 0,
  scores_json TEXT NOT NULL,
  gate TEXT NOT NULL,
  evidence_strength INTEGER NOT NULL DEFAULT 0,
  stage TEXT NOT NULL,
  owner TEXT,
  products_json TEXT NOT NULL,
  workflows INTEGER DEFAULT 0,
  buyer TEXT,
  last_reviewed TEXT,
  notes TEXT,
  account_thesis TEXT,
  data_mode TEXT NOT NULL DEFAULT 'SYNTHETIC'
);
CREATE INDEX idx_accounts_motion ON accounts(motion);
CREATE INDEX idx_accounts_sector ON accounts(sector);
CREATE TABLE signals (
  signal_id TEXT PRIMARY KEY,
  account_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
  ordinal INTEGER NOT NULL,
  kind TEXT NOT NULL,
  event_date TEXT NOT NULL,
  title TEXT NOT NULL,
  amount_usd INTEGER,
  source_label TEXT NOT NULL,
  source_url TEXT,
  published_at TEXT,
  ingested_at TEXT NOT NULL,
  confidence REAL,
  amount_basis TEXT,
  evidence_type TEXT NOT NULL DEFAULT 'SYNTHETIC'
);
CREATE INDEX idx_signals_account ON signals(account_id,ordinal);
CREATE INDEX idx_signals_date ON signals(event_date);
CREATE TABLE use_cases (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  account_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
  ordinal INTEGER NOT NULL,
  title TEXT NOT NULL,
  description TEXT NOT NULL,
  product TEXT NOT NULL,
  buyer TEXT NOT NULL,
  validation_kpi TEXT NOT NULL
);
CREATE INDEX idx_use_cases_account ON use_cases(account_id,ordinal);
"""

def build(source: Path, dest: Path, force: bool = False) -> None:
    data = json.loads(source.read_text(encoding="utf-8"))
    build_data(data, dest, force)


def build_data(data: dict, dest: Path, force: bool = False) -> None:
    if dest.exists() and not force:
        raise FileExistsError(f"{dest} exists. Choose a new database or pass --force.")
    with TemporaryDirectory(dir=dest.parent) as directory:
        staged = Path(directory) / dest.name
        write_database(data, staged)
        if force:
            staged.replace(dest)
        else:
            # Hard-link only after the build finishes. Fails if dest was created concurrently.
            dest.hardlink_to(staged)
    print(f"Created {dest} with {len(data['accounts'])} accounts ({data.get('mode', 'SYNTHETIC DEMO')})")


def write_database(data: dict, dest: Path) -> None:
    accounts = data.get("accounts")
    if not isinstance(accounts, list) or not accounts:
        raise ValueError("Expected a non-empty 'accounts' array")
    ids = [a["id"] for a in accounts]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate account IDs")
    now = datetime.now(timezone.utc).isoformat()
    with closing(sqlite3.connect(dest)) as conn:
        conn.executescript(SCHEMA)
        conn.executemany("INSERT INTO metadata(key,value) VALUES (?,?)", [
            ("asOf", data.get("asOf", "")),
            ("mode", data.get("mode", "SYNTHETIC DEMO")),
            ("lastDatabaseBuild", now),
        ])
        for a in accounts:
            conn.execute("""INSERT INTO accounts VALUES (
              ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
                a["id"], a["name"], a["sector"], a["motion"], a.get("hq"),
                a.get("fundingAmount",0), a.get("fundingDate"), a.get("contractObligations",0),
                a.get("ttmRevenue",0), a.get("contractedACV",0),a.get("scenarioAnnualValue",0),
                json.dumps(a["scores"]),a["gate"],a.get("evidenceStrength",0),a["stage"],
                a.get("owner"),json.dumps(a.get("products",[])),a.get("workflows",0),
                a.get("buyer"),a.get("lastReviewed"),a.get("notes"),a.get("accountThesis"),
                a.get("dataMode","SYNTHETIC")
            ))
            for i,s in enumerate(a.get("signals",[])):
                conn.execute("""INSERT INTO signals
                    (signal_id,account_id,ordinal,kind,event_date,title,amount_usd,
                     source_label,source_url,published_at,ingested_at,confidence,evidence_type,amount_basis)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", (
                    s["id"],a["id"],i,s["type"],s["date"],s["title"],s.get("amount"),
                    s.get("source","Synthetic example"), s.get("sourceUrl"),
                    s.get("publishedAt"), now, None, s.get("evidenceType","SYNTHETIC"),
                    s.get("amountBasis")
                ))
            for i,u in enumerate(a.get("useCases",[])):
                conn.execute("""INSERT INTO use_cases
                    (account_id,ordinal,title,description,product,buyer,validation_kpi)
                    VALUES(?,?,?,?,?,?,?)""",(
                    a["id"],i,u["title"],u["description"],u["product"],u["buyer"],u["kpi"]
                ))
        conn.commit()

if __name__ == "__main__":
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", type=Path, default=ROOT/"atlas_growth_demo.json")
    ap.add_argument("--db", type=Path, default=ROOT/"atlas.sqlite")
    ap.add_argument("--force", action="store_true")
    args=ap.parse_args()
    build(args.source,args.db,args.force)
