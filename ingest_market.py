"""Build a separate ATLAS database from manually verified public announcements."""
import argparse
import csv
import re
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

from build_database import build_data

ROOT = Path(__file__).resolve().parent
AS_OF = date(2026, 11, 10)
MODE = "PUBLIC MARKET INTELLIGENCE"
WORKFLOWS = {
    "manufacturing": (
        "Manufacturing quality evidence assistant", "Manufacturing quality director",
        "Draft and cross-reference quality evidence from approved sample work instructions and inspection records.",
        "Median time to assemble a quality evidence packet and reviewer correction rate",
    ),
    "engineering": (
        "Engineering test documentation assistant", "Engineering operations lead",
        "Draft test summaries with references from approved, non-sensitive sample test logs and procedures.",
        "Median test-summary preparation time and reference accuracy",
    ),
    "support": (
        "Technical support knowledge assistant", "Technical support operations lead",
        "Retrieve cited answers and draft support responses from approved public manuals and sample cases.",
        "Time to first correct answer and reviewer acceptance rate",
    ),
}


def https_url(value):
    parts = urlsplit(value)
    return parts.scheme == "https" and bool(parts.hostname) and not parts.username and not parts.password


def load_seed(path):
    with path.open(encoding="utf-8-sig", newline="") as source:
        rows = list(csv.DictReader(source, delimiter="|"))
    accounts = []
    names = set()
    for row in rows:
        key = row["id"]
        name = row["name"]
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", key) or not name or name.casefold() in names:
            raise ValueError(f"Invalid or duplicate company: {name}")
        names.add(name.casefold())
        if not all(https_url(row[k]) for k in ("source_url", "location_url")):
            raise ValueError(f"Invalid source URL for {name}")
        event = date.fromisoformat(row["date"])
        amount = int(row["amount_usd"])
        signal_type = row["signal_type"]
        if (event > AS_OF or amount <= 0 or signal_type not in {"Funding", "Federal awards", "Commercial contract"}
                or any(not row[k].strip() for k in ("title", "amount_basis", "sector", "us_base"))):
            raise ValueError(f"Invalid signal for {name}")
        workflow, buyer, description, kpi = WORKFLOWS[row["workflow"]]
        age = (AS_OF - event).days
        urgency = 85 if age <= 180 else 70 if age <= 365 else 50 if age <= 730 else 30
        # Evidence indicates a public trigger. Capacity, access and feasibility remain unverified.
        scores = dict(fit=85 if row["workflow"] == "manufacturing" else 75,
                      urgency=urgency, capacity=50, access=50, feasibility=40)
        source = urlsplit(row["source_url"]).hostname
        account_id = f"market-{key}"
        accounts.append({
            "id": account_id, "name": name, "sector": row["sector"], "hq": row["us_base"],
            "motion": "Acquire", "gate": "Security review", "stage": "Identified", "owner": "Unassigned",
            "fundingAmount": amount if signal_type == "Funding" else None,
            "fundingDate": row["date"] if signal_type == "Funding" else None,
            "contractObligations": None, "ttmRevenue": None, "contractedACV": None,
            "scenarioAnnualValue": None, "workflows": None, "products": [],
            "scores": scores, "buyer": buyer, "lastReviewed": AS_OF.isoformat(),
            "dataMode": "PUBLIC", "notes": "",
            "accountThesis": f'{row["title"]} is a public signal for {name}. Test whether a {row["sector"].lower()} team has a measurable use case for {workflow.lower()}. Start with a synthetic or public-data evaluation and confirm the data boundary before any pilot.',
            "useCases": [{"title": workflow, "description": description,
                          "product": "OpenAI API evaluation (hypothesis)", "buyer": buyer, "kpi": kpi}],
            "signals": [
                {"id": f"{account_id}-signal", "type": signal_type, "date": row["date"],
                 "title": row["title"], "amount": amount, "amountBasis": row["amount_basis"],
                 "source": source, "sourceUrl": row["source_url"], "evidenceType": "PUBLIC ANNOUNCEMENT"},
                {"id": f"{account_id}-location", "type": "Company reference", "date": AS_OF.isoformat(),
                 "title": f'US location reference: {row["us_base"]}', "source": urlsplit(row["location_url"]).hostname,
                 "sourceUrl": row["location_url"], "evidenceType": "LOCATION REFERENCE"},
            ],
        })
    return {"asOf": AS_OF.isoformat(), "mode": MODE, "accounts": accounts}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=Path, default=ROOT / "market_seed.psv")
    parser.add_argument("--db", type=Path, default=ROOT / "atlas_market.sqlite")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if args.db.resolve() == (ROOT / "atlas.sqlite").resolve():
        parser.error("Choose a separate market database path.")
    build_data(load_seed(args.seed), args.db, args.force)


