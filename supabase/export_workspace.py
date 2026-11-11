"""Export canonical ATLAS data for an owner-private cloud migration.

Writes a local ignored file. Does not change SQLite or call Supabase.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import atlas_server
import account_plan_store
import research_store


def snapshot():
    metadata, accounts = atlas_server.workspace_accounts(ROOT/'atlas_market.sqlite', ROOT/'atlas_plans.sqlite')
    return dict(asOf=metadata.get('asOf'), mode='PUBLIC MARKET INTELLIGENCE', accounts=accounts,
                accountPlans=account_plan_store.load_all(ROOT/'atlas_plans.sqlite'),
                researchReviews=research_store.load_reviews(ROOT/'atlas_plans.sqlite'),
                feed=research_store.feed(ROOT/'atlas_plans.sqlite'))


if __name__ == '__main__':
    data = snapshot()
    assert len({a['id'] for a in data['accounts']}) == len(data['accounts']), 'Duplicate account IDs'
    target = ROOT/'supabase/.local/workspace.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'accounts':len(data['accounts']), 'plans':len(data['accountPlans']),
                      'reviews':len(data['researchReviews']), 'events':len(data['feed']['events']),
                      'export':str(target), 'cloudUploaded':False}))
