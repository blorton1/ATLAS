"""Run with python -m unittest test_research -v; databases are temporary."""
import copy
from pathlib import Path
import tempfile
import unittest

import account_plan_store as plans
import research_store as research


class ResearchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'plans.sqlite'
        research.initialize(self.path)
        self.review = {'status': 'Qualified target', 'usVerified': True, 'sectorVerified': True,
                       'latestStage': 'Series B', 'latestStageVerified': True,
                       'stageSource': 'https://company.example/news/round',
                       'usSource': 'https://company.example/about',
                       'sectorSource': 'https://company.example/products',
                       'checkedOn': '2026-11-10', 'rationale': 'Primary newsroom stage and US headquarters checked.',
                       'reviewer': 'Test researcher'}
        self.event = {'accountId': 'one', 'type': 'expansion', 'title': 'New factory announced',
                      'date': '2026-11-09', 'publishedAt': '2026-11-10', 'source': 'Company newsroom',
                      'sourceUrl': 'https://company.example/news/factory?utm_source=mail',
                      'verification': 'Pending', 'amount': None, 'workflow': 'Planning hypothesis: quality assistant.'}
        self.batch = {'runDate': '2026-11-10', 'events': [self.event],
                      'sources': [{'name': 'Company newsroom', 'url': 'https://company.example/news', 'status': 'ok', 'detail': ''}]}

    def test_complete_qualification_and_optimistic_conflict(self):
        result = research.save_review(self.path, 'one', 0, self.review)
        self.assertTrue(research.qualified(result['review']))
        self.assertEqual(research.load_reviews(self.path)['one']['version'], 1)
        with self.assertRaises(plans.VersionConflict):
            research.save_review(self.path, 'one', 0, self.review)

    def test_incomplete_sales_fit_cannot_be_qualified(self):
        for field, value in [('usVerified', False), ('sectorVerified', False), ('usSource', ''),
                             ('sectorSource', ''), ('checkedOn', ''), ('reviewer', ''), ('rationale', '')]:
            bad = dict(self.review, **{field: value})
            with self.subTest(field=field), self.assertRaises(ValueError):
                research.save_review(self.path, 'one', 0, bad)
        with self.assertRaises(plans.VersionConflict):
            research.promote(self.path, 'one', 1, 0)

    def test_later_stage_and_unknown_funding_can_qualify_for_sales(self):
        for index, stage in enumerate(['Series E+', 'Public', 'Acquired', 'Unknown']):
            review=dict(self.review, latestStage=stage,latestStageVerified=False,stageSource='')
            saved=research.save_review(self.path,str(index),0,review)
            self.assertTrue(research.qualified(saved['review']))
            plan=research.promote(self.path,str(index),1,0)['plan']
            self.assertEqual(plan['relationship'],'Prospect')

    def test_review_downgrade_blocks_new_promotion(self):
        research.save_review(self.path, 'one', 0, self.review)
        saved = research.promote(self.path, 'one', 1, 0)
        self.assertEqual(saved['plan']['relationship'], 'Prospect')
        research.save_review(self.path, 'one', 1, dict(self.review, status='Outside target', latestStage='Public'))
        with self.assertRaises(ValueError):
            research.promote(self.path, 'one', 2, 1)
        self.assertTrue(plans.load_all(self.path)['one']['plan']['shortlisted'])

    def test_promotion_preserves_existing_crm_and_versions(self):
        original = {'relationship': 'Partner', 'stage': 'Discovery', 'owner': 'Brendan',
                    'notes': 'Existing account notes', 'contacts': [{'id': 'c', 'name': 'Buyer'}],
                    'opportunities': [{'id': 'o', 'name': 'Pilot', 'amount': 5000, 'stage': 'Pilot'}],
                    'activities': [{'id': 'a', 'date': '2026-11-01', 'type': 'Call', 'summary': 'Existing history'}]}
        plans.save(self.path, 'one', 0, original)
        research.save_review(self.path, 'one', 0, self.review)
        with self.assertRaises(plans.VersionConflict):
            research.promote(self.path, 'one', 1, 0)
        result = research.promote(self.path, 'one', 1, 1)
        for key in ('relationship', 'stage', 'owner', 'notes', 'contacts', 'opportunities'):
            self.assertEqual(result['plan'][key], original[key])
        self.assertEqual(result['plan']['activities'][0], original['activities'][0])
        self.assertTrue(result['plan']['shortlisted'])
        self.assertEqual(result['version'], 2)
        self.assertEqual(len(result['plan']['activities']), 2)

    def test_stale_review_cannot_promote(self):
        research.save_review(self.path, 'one', 0, self.review)
        research.save_review(self.path, 'one', 1, self.review)
        with self.assertRaises(plans.VersionConflict):
            research.promote(self.path, 'one', 1, 0)
        self.assertEqual(plans.load_all(self.path), {})

    def test_no_dollar_event_deduplicates_tracking_urls_and_titles(self):
        self.assertEqual(research.ingest(self.path, self.batch, {'one'})['inserted'], 1)
        next_batch = copy.deepcopy(self.batch)
        next_batch['events'][0]['sourceUrl'] = 'https://www.company.example/news/factory#details'
        self.assertEqual(research.ingest(self.path, next_batch, {'one'})['duplicates'], 1)
        next_batch['events'][0]['sourceUrl'] = 'https://another.example/factory'
        self.assertEqual(research.ingest(self.path, next_batch, {'one'})['duplicates'], 1)
        feed = research.feed(self.path)
        self.assertEqual(len(feed['events']), 1)
        self.assertIsNone(feed['events'][0]['amount'])
        self.assertEqual(feed['lastSuccessfulRun'], '2026-11-10')

    def test_bad_batch_is_atomic_and_rejects_unknown_company(self):
        bad = copy.deepcopy(self.batch)
        bad['events'].append(dict(self.event, accountId='unknown'))
        with self.assertRaises(ValueError):
            research.ingest(self.path, bad, {'one'})
        self.assertEqual(research.feed(self.path)['events'], [])
        self.assertEqual(research.feed(self.path)['runs'], [])

    def test_source_failure_retained_does_not_advance_success(self):
        bad = copy.deepcopy(self.batch)
        bad['sources'][0].update(status='failed', detail='HTTP 503')
        research.ingest(self.path, bad, {'one'})
        feed = research.feed(self.path)
        self.assertEqual(feed['runs'][0]['status'], 'partial')
        self.assertEqual(feed['runs'][0]['sources'][0]['detail'], 'HTTP 503')
        self.assertIsNone(feed['lastSuccessfulRun'])

    def test_same_source_can_support_distinct_events(self):
        batch = copy.deepcopy(self.batch)
        batch['events'].append(dict(self.event, title='Different factory announced'))
        self.assertEqual(research.ingest(self.path, batch, {'one'})['inserted'], 2)

    def test_amount_validation_and_unknown_publication(self):
        batch = copy.deepcopy(self.batch)
        batch['events'][0]['publishedAt'] = None
        research.ingest(self.path, batch, {'one'})
        for amount in [float('nan'), float('inf'), -1, True, '100']:
            batch['events'][0]['amount'] = amount
            with self.subTest(amount=amount), self.assertRaises(ValueError):
                research.ingest(self.path, batch, {'one'})
        batch['events'][0]['amount'] = 100
        with self.assertRaises(ValueError):
            research.ingest(self.path, batch, {'one'})

    def test_candidate_identity_and_persistence(self):
        candidate = {'name': 'New Company', 'website': 'https://company.example',
                     'sector': 'Defense technology', 'hq': 'Boston, MA', 'workflow': 'Planning hypothesis'}
        result = research.add_candidate(self.path, candidate, [])
        self.assertTrue(result['accountId'].startswith('research-'))
        self.assertEqual(research.candidates(self.path)[0]['name'], 'New Company')
        for mutation in [{'name': ' NEW-COMPANY '}, {'name': 'Different', 'website': 'https://www.company.example/about'}]:
            with self.assertRaises(ValueError):
                research.add_candidate(self.path, dict(candidate, **mutation), [])
        with self.assertRaises(ValueError):
            research.add_candidate(self.path, candidate, [{'name': 'New Company', 'id': 'old'}])

    def test_evidence_url_and_date_rejected(self):
        for source in ['javascript:alert(1)', 'http://company.example', 'https://user:pass@company.example', 'https://company.example/\ninvalid']:
            with self.subTest(source=source), self.assertRaises(ValueError):
                research.save_review(self.path, 'one', 0, dict(self.review, stageSource=source))
        for checked in ['2099-01-01', '2026-02-30', '20261110', True]:
            with self.subTest(checked=checked), self.assertRaises(ValueError):
                research.save_review(self.path, 'one', 0, dict(self.review, checkedOn=checked))


if __name__ == '__main__':
    unittest.main()
