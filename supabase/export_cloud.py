"""Build public demo and separate signed-in cloud pages; config is publishable only."""
import argparse,json,re,shutil,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'demo'))
from export_demo import export

def build(dest,config):
    if not config.get('key','').startswith(('sb_publishable_','eyJ')):
        raise ValueError('Only a Supabase publishable / legacy anon key belongs in browser configuration')
    export(dest)
    engine=(ROOT/'demo/demo-api.js').read_text(encoding='utf-8')
    marker='  const originalFetch=global.fetch.bind(global),script='
    assert marker in engine
    engine=engine[:engine.index(marker)]+"  global.ATLAS_CREATE_API=createDemoApi;\n})(globalThis);\n"
    engine=engine.replace('Demo qualification by ','Sales qualification by ')
    (dest/'demo-engine.js').write_text(engine,encoding='utf-8')
    (dest/'cloud-config.js').write_text('window.ATLAS_CLOUD_CONFIG='+json.dumps(config)+';\n',encoding='utf-8')
    for name in ['cloud-api.js','pipeline-login.html','cloud-shell.js']:
        shutil.copyfile(ROOT/'supabase'/name,dest/name)
    banner='<aside id="interview-banner" aria-label="Private pipeline"><div><strong>ATLAS · Your saved pipeline</strong><span>Owner-only · Changes save to Supabase</span></div><nav><a href="/">Public interview demo ↗</a><button id="cloud-sign-out" type="button">Sign out</button></nav></aside>'
    for source,target in [('atlas_growth_live.html','pipeline.html'),('research.html','pipeline-research.html')]:
        html=(dest/source).read_text(encoding='utf-8')
        html=re.sub(r'<script id="demo-data" type="application/json">.*?</script>','',html,flags=re.S)
        html=html.replace('<script src="/demo-api.js"></script><script src="/demo-shell.js" defer></script>','<script src="/cloud-config.js"></script><script src="/demo-engine.js"></script><script src="/cloud-api.js"></script><script src="/cloud-shell.js" defer></script>')
        html=re.sub(r'<aside id="interview-banner".*?</aside>',lambda _:banner,html,count=1,flags=re.S)
        html=html.replace('/atlas_growth_live.html','/pipeline.html').replace('/research.html','/pipeline-research.html')
        html=html.replace('Saved in this browser','Saved to your cloud pipeline')
        html=html.replace('Demo data unavailable. Reload this page or check browser storage permissions.','Cloud pipeline unavailable. Sign in again or refresh to retry.')
        html=html.replace('Demo workspace unavailable. Reload this page or check browser storage permissions.','Cloud pipeline unavailable. Sign in again or refresh to retry.')
        html=html.replace('This interview demo includes a saved intelligence snapshot. You can try importing a sample batch into your own browser below.','This is your private cloud intelligence feed. Daily discoveries remain pending review; imports save to your pipeline.')
        html=html.replace('Daily prospecting runs in the owner’s Codex workspace at 7 AM Eastern; new results appear here when the demo snapshot is republished.','Cloud prospecting is scheduled for 7 AM Eastern. Inspect run logs for the actual outcome and any source failures.')
        (dest/target).write_text(html,encoding='utf-8')
    for file in ['index.html','atlas_growth_live.html','research.html']:
        html=(dest/file).read_text(encoding='utf-8').replace('<nav><a href=', '<nav><a href="/pipeline-login.html">My saved pipeline →</a><a href=',1)
        (dest/file).write_text(html,encoding='utf-8')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('destination',type=Path);p.add_argument('config',type=Path)
    a=p.parse_args();build(a.destination,json.loads(a.config.read_text(encoding='utf-8')))
