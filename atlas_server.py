"""Local HTTP API for the ATLAS 2.0 dashboard.

No external dependencies. Use only on the local machine; no login, TLS, or
production-grade access controls are provided. Binds to 127.0.0.1 by default.
"""
from __future__ import annotations

import argparse
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from pathlib import Path
import json
import sqlite3
import account_plan_store
import research_store
import threading
from contextlib import closing
from urllib.parse import urlsplit, unquote, parse_qs
from mimetypes import guess_type

ROOT=Path(__file__).resolve().parent
ALLOWED_FILES={
    "/research.html":"research.html",
    "/atlas_growth_live.html":"atlas_growth_live.html",
    "/atlas_growth.html":"atlas_growth.html",
    "/atlas_growth_desktop.png":"atlas_growth_desktop.png",
    "/atlas_growth_mobile.png":"atlas_growth_mobile.png",
    "/atlas_growth_demo.csv":"atlas_growth_demo.csv",
}

def load_accounts(db:Path) -> tuple[dict,list[dict]]:
    with closing(sqlite3.connect(db)) as conn:
        conn.row_factory=sqlite3.Row
        m={r["key"]:r["value"] for r in conn.execute("SELECT key,value FROM metadata")}
        accounts=[]
        rows=conn.execute("SELECT * FROM accounts ORDER BY id").fetchall()
        signals={}
        for r in conn.execute("SELECT * FROM signals ORDER BY account_id,ordinal"):
            signals.setdefault(r["account_id"],[]).append({
                "id":r["signal_id"],"type":r["kind"],"date":r["event_date"],
                "title":r["title"],"amount":r["amount_usd"],"source":r["source_label"],
                "sourceUrl":r["source_url"],"publishedAt":r["published_at"],
                "ingestedAt":r["ingested_at"],"evidenceType":r["evidence_type"],
                "amountBasis":r["amount_basis"] if "amount_basis" in r.keys() else None
            })
        use_cases={}
        for r in conn.execute("SELECT * FROM use_cases ORDER BY account_id,ordinal"):
            use_cases.setdefault(r["account_id"],[]).append({
                "title":r["title"],"description":r["description"],"product":r["product"],
                "buyer":r["buyer"],"kpi":r["validation_kpi"]
            })
        for r in rows:
            id=r["id"]
            accounts.append({
                "id":id,"name":r["name"],"sector":r["sector"],"motion":r["motion"],"hq":r["hq"],
                "fundingAmount":r["funding_amount_usd"],"fundingDate":r["funding_date"],
                "contractObligations":r["federal_obligations_usd"],"ttmRevenue":r["ttm_revenue_usd"],
                "contractedACV":r["contracted_annual_commitment_usd"],
                "scenarioAnnualValue":r["scenario_annual_value_usd"],
                "scores":json.loads(r["scores_json"]),"gate":r["gate"],
                "evidenceStrength":r["evidence_strength"],"stage":r["stage"],
                "owner":r["owner"],"products":json.loads(r["products_json"]),
                "workflows":r["workflows"],"buyer":r["buyer"],
                "useCases":use_cases.get(id,[]),"signals":signals.get(id,[]),
                "lastReviewed":r["last_reviewed"],"notes":r["notes"],
                "accountThesis":r["account_thesis"],"dataMode":r["data_mode"]
            })
        return m,accounts

def workspace_accounts(db: Path, plans_db: Path):
    """Project durable research into the existing dashboard without rebuilding it."""
    meta, accounts = load_accounts(db)
    ids = {a['id'] for a in accounts}
    for candidate in research_store.candidates(plans_db):
        if candidate['accountId'] in ids:
            continue
        accounts.append({
            'id': candidate['accountId'], 'name': candidate['name'],
            'sector': candidate['sector'], 'hq': candidate['hq'], 'website': candidate['website'],
            'motion':'Acquire', 'fundingAmount':None, 'fundingDate':None,
            'contractObligations':None, 'ttmRevenue':None, 'contractedACV':None,
            'scenarioAnnualValue':None, 'scores':dict(fit=0,urgency=0,capacity=0,access=0,feasibility=0),
            'gate':'Security review', 'evidenceStrength':0, 'stage':'Identified',
            'owner':'Unassigned','products':[], 'workflows':None, 'buyer':'To validate',
            'useCases':[{'title':candidate['workflow'] or 'Needs discovery', 'description':'User-entered workflow hypothesis',
                         'product':'To validate','buyer':'To validate','kpi':'To validate'}],
            'signals':[], 'lastReviewed':None, 'notes':'', 'accountThesis':candidate.get('openaiFit') or 'Potential OpenAI client — sales fit to assess', 'dataMode':'PUBLIC',
            **{k:candidate.get(k,'') for k in ('businessNeed','openaiFit','buyerRole','nextStep')},
            'priority':candidate.get('priority','Unassessed'),
        })
    by_id = {a['id']:a for a in accounts}
    for event in research_store.feed(plans_db)['events']:
        if event['accountId'] in by_id:
            by_id[event['accountId']]['signals'].insert(0, {
                'id':event.get('id'), 'type':event['type'], 'date':event['date'], 'title':event['title'],
                'amount':event.get('amount'), 'source':event['source'], 'sourceUrl':event['sourceUrl'],
                'publishedAt':event.get('publishedAt'), 'ingestedAt':event.get('collectedAt'),
                'evidenceType':event['verification'], 'amountBasis':event.get('amountBasis'),
            })
    for account in accounts:
        account['signals'].sort(key=lambda signal: signal['date'], reverse=True)
    return meta, accounts


def create_handler(db:Path, plans_db:Path | None = None):
    plans_db = plans_db or ROOT / "atlas_plans.sqlite"
    account_plan_store.initialize(plans_db)
    research_store.initialize(plans_db)
    collection_lock = threading.Lock()
    class Handler(BaseHTTPRequestHandler):
        def send_json(self,obj,code=200):
            payload=json.dumps(obj,ensure_ascii=False,separators=(",",":")).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type","application/json; charset=utf-8")
            self.send_header("Cache-Control","no-store")
            self.send_header("Content-Length",str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        def do_GET(self):
            try:
                host = urlsplit('http://' + self.headers.get('Host',''))
                if host.hostname not in {'127.0.0.1','localhost'} or host.port != self.server.server_port:
                    raise ValueError('Unexpected host')
                origin = self.headers.get('Origin')
                if origin and origin != 'http://' + host.netloc:
                    raise ValueError('Unexpected origin')
            except ValueError:
                self.send_json({'error':'Use the local ATLAS address'},403)
                return
            parsed=urlsplit(self.path)
            path=unquote(parsed.path)
            if path in ("/", ""):
                self.send_response(302)
                self.send_header("Location","/atlas_growth_live.html")
                self.end_headers()
                return
            if path.startswith("/api/"):
                try:
                    meta,accounts=workspace_accounts(db, plans_db)
                    plans=account_plan_store.load_all(plans_db)
                except (OSError,sqlite3.Error,ValueError) as exc:
                    self.send_json({"error":"Database unavailable","detail":str(exc)},503)
                    return
                if path=="/api/research":
                    self.send_json({"accounts":accounts,"reviews":research_store.load_reviews(plans_db),"feed":research_store.feed(plans_db),"plans":plans})
                elif path=="/api/health":
                    self.send_json({"status":"ok","database":db.name,"data_mode":meta.get("mode")})
                elif path=="/api/bootstrap":
                    self.send_json({"asOf":meta.get("asOf"),"mode":meta.get("mode"),"accounts":accounts,"accountPlans":plans,"researchReviews":research_store.load_reviews(plans_db)})
                elif path=="/api/account-plans":
                    self.send_json(plans)
                elif path=="/api/accounts":
                    motion=parse_qs(parsed.query).get("motion",[None])[0]
                    self.send_json([a for a in accounts if not motion or a["motion"]==motion])
                elif path.startswith("/api/accounts/"):
                    target=path.split("/",3)[-1]
                    found=next((a for a in accounts if a["id"]==target),None)
                    self.send_json(found if found else {"error":"Account not found"},200 if found else 404)
                else:
                    self.send_json({"error":"Unknown endpoint"},404)
                return
            filename=ALLOWED_FILES.get(path)
            if not filename:
                self.send_error(404,"Not found")
                return
            file=ROOT/filename
            if not file.is_file():
                self.send_error(404,"Missing file")
                return
            body=file.read_bytes()
            mime=guess_type(str(file))[0] or "application/octet-stream"
            self.send_response(200)
            self.send_header("Content-Type",mime + ("; charset=utf-8" if mime.startswith("text/") else ""))
            self.send_header("Content-Length",str(len(body)))
            self.send_header("Cache-Control","no-store")
            self.end_headers()
            self.wfile.write(body)
        def do_PUT(self):
            path = unquote(urlsplit(self.path).path)
            research = path.startswith("/api/research/reviews/") or path.startswith("/api/research/promote/") or path in {"/api/research/import", "/api/research/candidates", "/api/research/collect"}
            if not path.startswith("/api/account-plans/") and not research:
                self.send_json({"error": "Unknown endpoint"}, 404)
                return
            # Same-origin browser writes only; explicit loopback Host prevents DNS rebinding.
            try:
                host = urlsplit("http://" + self.headers.get("Host", ""))
                origin = urlsplit(self.headers.get("Origin", ""))
                trusted = (host.hostname in {"127.0.0.1", "localhost"}
                           and host.port == self.server.server_port
                           and origin.scheme == "http" and origin.netloc == host.netloc
                           and not origin.path and not origin.query and not origin.fragment)
            except ValueError:
                trusted = False
            if not trusted:
                self.send_json({"error": "A matching local Origin is required"}, 403)
                return
            if self.headers.get_content_type() != "application/json":
                self.send_json({"error": "Use application/json"}, 415)
                return
            try:
                length = int(self.headers.get("Content-Length", ""))
            except ValueError:
                self.send_json({"error": "Content-Length is required"}, 411)
                return
            if length < 1 or length > 262144:
                self.send_json({"error": "Request must be between 1 and 262144 bytes"}, 413)
                return
            account_id = path.removeprefix("/api/account-plans/")
            try:
                self.connection.settimeout(10)
                raw = self.rfile.read(length)
                if len(raw) != length:
                    raise ValueError("Incomplete request body")
                payload = json.loads(raw)
                if research:
                    if not isinstance(payload, dict):
                        raise ValueError("Expected an object")
                    _, accounts = workspace_accounts(db, plans_db)
                    ids = {a['id'] for a in accounts}
                    if path == "/api/research/collect":
                        if payload:
                            raise ValueError('Collection accepts an empty object')
                        if not collection_lock.acquire(blocking=False):
                            self.send_json({'error':'Daily intake is already running'},409)
                            return
                        try:
                            import daily_intelligence
                            result = daily_intelligence.collect(plans_db, accounts, ROOT/'daily_feeds.json', plans_db.parent/'daily_updates')
                        finally:
                            collection_lock.release()
                    elif path == "/api/research/import":
                        result = research_store.ingest(plans_db, payload, ids)
                    elif path == "/api/research/candidates":
                        result = research_store.add_candidate(plans_db, payload, accounts)
                    else:
                        account_id = path.rsplit('/', 1)[-1]
                        if account_id not in ids:
                            self.send_json({"error":"Account not found"},404)
                            return
                        if '/reviews/' in path:
                            if set(payload) != {'version', 'review'}:
                                raise ValueError("Expected version and review")
                            result = research_store.save_review(plans_db, account_id, payload['version'], payload['review'])
                        else:
                            if set(payload) != {'reviewVersion', 'planVersion'}:
                                raise ValueError("Expected reviewVersion and planVersion")
                            result = research_store.promote(plans_db, account_id, payload['reviewVersion'], payload['planVersion'])
                    self.send_json(result)
                    return
                with closing(sqlite3.connect(db)) as conn:
                    exists = conn.execute("SELECT 1 FROM accounts WHERE id=?", (account_id,)).fetchone()
                if not exists:
                    exists = any(a['accountId'] == account_id for a in research_store.candidates(plans_db))
                if not exists:
                    self.send_json({"error": "Account not found"}, 404)
                    return
                if not isinstance(payload, dict) or set(payload) != {"version", "plan"}:
                    raise ValueError("Expected version and plan")
                # Legacy plan qualification cannot bypass the evidence review gate.
                current_review = research_store.load_reviews(plans_db).get(account_id, {}).get('review', {})
                if not isinstance(payload['plan'], dict):
                    raise ValueError('plan must be an object')
                if payload['plan'].get('qualification') == 'Qualified target' and not research_store.qualified(current_review):
                    raise ValueError("Complete a verified research review before marking a qualified target")
                # Preserve historical evidence snapshots when the CRM form omits
                # them. Displayed qualification comes from research_reviews.
                previous = account_plan_store.load_all(plans_db).get(account_id, {}).get('plan', {})
                for key in ('qualification', 'stageSource', 'stageRationale'):
                    if key not in payload['plan'] and key in previous:
                        payload['plan'][key] = previous[key]
                saved = account_plan_store.save(plans_db, account_id, payload["version"], payload["plan"])
                self.send_json(saved)
            except account_plan_store.VersionConflict as exc:
                self.send_json({"error": str(exc), "current": exc.current}, 409)
            except (ValueError, UnicodeError) as exc:
                self.send_json({"error": str(exc)}, 400)
            except (OSError, sqlite3.Error) as exc:
                self.send_json({"error": "Account plan unavailable", "detail": str(exc)}, 503)

        def log_message(self,format,*args):
            print("[ATLAS]",format%args)
        def do_POST(self):
            path = unquote(urlsplit(self.path).path)
            if not (path.startswith('/api/research/promote/') or path in {'/api/research/import','/api/research/candidates','/api/research/collect'}):
                self.send_json({'error':'Unknown endpoint'},404)
                return
            self.do_PUT()
    return Handler

if __name__=="__main__":
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path, default=ROOT/"atlas_market.sqlite")
    ap.add_argument("--plans-db", type=Path, default=ROOT/"atlas_plans.sqlite")
    ap.add_argument("--port", type=int,default=8766)
    ap.add_argument("--host",default="127.0.0.1")
    args=ap.parse_args()
    if not args.db.exists():
        raise SystemExit("No database found. First run: python build_database.py")
    if args.host not in ("127.0.0.1","localhost"):
        raise SystemExit("For this local, unauthenticated demo, use the default loopback host")
    server=ThreadingHTTPServer((args.host,args.port),create_handler(args.db,args.plans_db))
    print(f"ATLAS live-data-mode demo: http://{args.host}:{args.port}/atlas_growth_live.html")
    print("Database-backed local API. Keep this unauthenticated service on loopback.")
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()

