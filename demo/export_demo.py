"""Export the current ATLAS snapshot into a self-contained interview demo."""
import argparse
import json
import re
import shutil
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import atlas_server,account_plan_store,research_store

def export(destination):
    destination.mkdir(parents=True,exist_ok=True)
    meta,accounts=atlas_server.workspace_accounts(ROOT/'atlas_market.sqlite',ROOT/'atlas_plans.sqlite')
    seed=dict(asOf='2026-11-10',mode='PUBLIC MARKET INTELLIGENCE',accounts=accounts,
              accountPlans=account_plan_store.load_all(ROOT/'atlas_plans.sqlite'),
              researchReviews=research_store.load_reviews(ROOT/'atlas_plans.sqlite'),
              feed=research_store.feed(ROOT/'atlas_plans.sqlite'))
    (destination/'demo-seed.json').write_text(json.dumps(seed,ensure_ascii=False),encoding='utf-8')
    nominal=next(a['id'] for a in accounts if a['name']=='Nominal')
    banner=f'''<aside id="interview-banner" aria-label="Interview demo controls"><div><strong>ATLAS · Interview demo</strong><span>November 10 snapshot · Your edits stay in this browser</span></div><nav><a href="/research.html?account={nominal}">Try qualifying Nominal →</a><a href="https://github.com/blorton1/ATLAS" target="_blank" rel="noopener noreferrer">Source code ↗</a><button type="button" id="reset-interview-demo">Reset demo</button></nav></aside>'''
    for file in ['atlas_growth_live.html','research.html']:
        html=(ROOT/file).read_text(encoding='utf-8')
        html=re.sub(r'<script id="demo-data" type="application/json">.*?</script>', lambda _: '<script id="demo-data" type="application/json">'+json.dumps(seed).replace('<','\\u003c')+'</script>',html,flags=re.S)
        html=re.sub(r'<title>.*?</title>','<title>ATLAS | Sales Dashboard Demo</title>',html,count=1)
        html=html.replace('ATLAS: synthetic enterprise AI account acquisition and expansion intelligence demo.','ATLAS interview demo: sales prospecting, qualification, and account management.')
        html=html.replace('</head>','<link rel="stylesheet" href="/demo-shell.css"><script src="/demo-api.js"></script><script src="/demo-shell.js" defer></script></head>',1)
        html=re.sub(r'(<body[^>]*>)',lambda m:m.group(1)+banner,html,count=1)
        html=html.replace('Database unavailable. Start the local ATLAS server and refresh.','Demo data unavailable. Reload this page or check browser storage permissions.')
        html=html.replace('Sales workspace unavailable. Start the local ATLAS server and refresh.','Demo workspace unavailable. Reload this page or check browser storage permissions.')
        html=html.replace('Saved to local account database','Saved in this browser').replace('Saved to account database','Saved in this browser')
        html=html.replace('Check the two configured RSS feeds for public headlines. Matching company signals enter this feed as pending review; unmatched headlines and source coverage are saved in daily_updates.','This interview demo includes a saved intelligence snapshot. You can try importing a sample batch into your own browser below.')
        html=html.replace('Codex daily prospecting is scheduled for 7 AM Eastern. This button checks the two RSS feeds on demand.','Daily prospecting runs in the owner’s Codex workspace at 7 AM Eastern; new results appear here when the demo snapshot is republished.')
        html=html.replace("selected=query.get('account')||'';",f"selected=query.get('account')||'{nominal}';")
        (destination/file).write_text(html,encoding='utf-8')
    shutil.copyfile(destination/'atlas_growth_live.html',destination/'index.html')
    for file in ['demo-api.js','demo-shell.js','demo-shell.css']:
        shutil.copyfile(ROOT/'demo'/file,destination/file)
    print(json.dumps({'destination':str(destination),'accounts':len(accounts),'events':len(seed['feed']['events'])}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('destination',type=Path);export(p.parse_args().destination)
