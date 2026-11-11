"""HTTP regression tests against disposable stores, never the delivered dataset."""
from contextlib import closing
import json
from pathlib import Path
import shutil
import sqlite3
import tempfile
import threading
import unittest
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from http.server import ThreadingHTTPServer

import atlas_server


class ServerTests(unittest.TestCase):
    def test_legacy_evidence_survives_crm_edit_without_becoming_verified(self):
        import account_plan_store
        legacy=dict(qualification='Qualified target',stageSource='https://example.com/legacy',stageRationale='Prior legacy rationale',notes='Original notes')
        account_plan_store.save(self.plans,self.account,0,legacy)
        status,result=self.call('/api/account-plans/'+self.account,dict(version=1,plan={'notes':'Updated account notes'}),'PUT')
        self.assertEqual(status,200)
        self.assertEqual(result['plan']['stageRationale'],legacy['stageRationale'])
        self.assertEqual(result['plan']['stageSource'],legacy['stageSource'])
        self.assertEqual(result['plan']['notes'],'Updated account notes')
        self.assertNotIn(self.account,self.call('/api/research')[1]['reviews'])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name)/'market.sqlite'
        self.plans = Path(self.tmp.name)/'plans.sqlite'
        shutil.copyfile(Path(__file__).parent/'atlas_market.sqlite',self.db)
        self.server = ThreadingHTTPServer(('127.0.0.1',0),atlas_server.create_handler(self.db,self.plans))
        self.thread = threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.origin = f'http://127.0.0.1:{self.server.server_port}'
        self.account = self.call('/api/accounts')[1][0]['id']

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.tmp.cleanup()

    def call(self,path,body=None,method='GET',origin=True):
        headers = {'Content-Type':'application/json'}
        if origin:
            headers['Origin']=self.origin
        request=Request(self.origin+path,data=json.dumps(body).encode() if body is not None else None,headers=headers,method=method)
        try:
            response=urlopen(request,timeout=5)
        except HTTPError as exc:
            response=exc
        with response:
            raw=response.read()
            return response.status,json.loads(raw) if 'application/json' in response.headers.get('Content-Type','') else raw

    def review(self):
        return dict(status='Qualified target',usVerified=True,sectorVerified=True,latestStage='Series B',
                    latestStageVerified=True,stageSource='https://example.com/round',usSource='https://example.com/about',
                    sectorSource='https://example.com/sector',checkedOn='2026-11-10',rationale='TEST evidence only',reviewer='Test reviewer')

    def test_crm_survives_research_and_promotion(self):
        plan=dict(relationship='Partner',stage='Discovery',owner='Test owner',objectives='Keep objective',
                  contacts=[dict(id='c1',name='Test stakeholder')],opportunities=[dict(id='o1',name='Test pilot',amount=80000,stage='Pilot')],
                  activities=[dict(id='a1',date='2026-11-10',type='Research',summary='Keep history')])
        self.assertEqual(self.call('/api/account-plans/'+self.account,dict(version=0,plan=plan),'PUT')[0],200)
        saved=self.call('/api/research/reviews/'+self.account,dict(version=0,review=self.review()),'PUT')
        self.assertEqual(saved[0],200)
        self.assertEqual(self.call('/api/research/promote/'+self.account,dict(reviewVersion=1,planVersion=1),'POST')[0],200)
        result=self.call('/api/account-plans')[1][self.account]['plan']
        for key,value in plan.items():
            if key!='activities':self.assertEqual(result[key],value)
        self.assertEqual(result['activities'][0],plan['activities'][0])
        self.assertTrue(result['shortlisted'])
        self.assertEqual(self.call('/api/research/promote/'+self.account,dict(reviewVersion=1,planVersion=1),'POST')[0],409)

    def test_candidate_integration_and_persistence(self):
        payload=dict(name='Test Defense Labs',sector='Defense technology',hq='Boston, US',website='https://example.test',workflow='Test documentation')
        status,result=self.call('/api/research/candidates',payload,'POST')
        self.assertEqual(status,200)
        account_id=result['accountId']
        self.assertEqual(self.call('/api/research/candidates',payload,'POST')[0],400)
        bootstrap=self.call('/api/bootstrap')[1]
        candidate=next(a for a in bootstrap['accounts'] if a['id']==account_id)
        self.assertIsNone(candidate['ttmRevenue'])
        self.assertEqual(self.call('/api/account-plans/'+account_id,dict(version=0,plan={'notes':'Durable','relationship':'Prospect'}),'PUT')[0],200)
        self.assertIn(account_id,self.call('/api/account-plans')[1])
        with closing(sqlite3.connect(self.db)) as conn:
            self.assertEqual(conn.execute('select count(*) from accounts').fetchone()[0],25)

    def test_gates_origin_errors_and_existing_endpoints(self):
        request=Request(self.origin+'/api/account-plans',headers={'Host':f'evil.example:{self.server.server_port}'})
        with self.assertRaises(HTTPError) as rejected:
            urlopen(request,timeout=5)
        self.assertEqual(rejected.exception.code,403)
        path='/api/research/reviews/'+self.account
        self.assertEqual(self.call(path,dict(version=0,review=self.review()),'PUT',False)[0],403)
        self.assertEqual(self.call(path,dict(version=0,review={'status':'Qualified target'}),'PUT')[0],400)
        self.assertEqual(self.call('/api/research/promote/'+self.account,dict(reviewVersion=1,planVersion=0),'POST')[0],409)
        self.assertEqual(self.call('/api/account-plans/'+self.account,dict(version=0,plan=[]),'PUT')[0],400)
        fake={'qualification':'Qualified target','stageSource':'https://example.com','stageRationale':'Bypass'}
        self.assertEqual(self.call('/api/account-plans/'+self.account,dict(version=0,plan=fake),'PUT')[0],400)
        for url in ['/api/health','/api/bootstrap','/api/accounts','/api/account-plans','/api/research','/research.html','/atlas_growth_live.html']:
            self.assertEqual(self.call(url)[0],200,url)

    def test_import_no_dollars_dedupe_and_feed_projection(self):
        event=dict(accountId=self.account,type='hiring',title='TEST hiring',date='2026-11-10',publishedAt=None,
                   source='Test source',sourceUrl='https://example.com/test',verification='Pending',amount=None,amountBasis='Not disclosed',workflow='Test hypothesis')
        batch=dict(runDate='2026-11-10',events=[event],sources=[dict(name='Test',url='https://example.com',status='failed',detail='Fixture unavailable')])
        status,result=self.call('/api/research/import',batch,'POST')
        self.assertEqual(status,200)
        self.assertEqual(result['inserted'],1)
        self.assertEqual(self.call('/api/research/import',batch,'POST')[1]['duplicates'],1)
        data=self.call('/api/research')[1]
        self.assertEqual(data['feed']['events'][0]['verification'],'Pending')
        self.assertIsNone(data['feed']['lastSuccessfulRun'])
        account=next(a for a in data['accounts'] if a['id']==self.account)
        self.assertTrue(any(s['title']=='TEST hiring' for s in account['signals']))


if __name__=='__main__':unittest.main()
