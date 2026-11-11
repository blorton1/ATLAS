"""Offline regression tests for the optional Phase 2 USAspending collector."""
from datetime import date
import io
import json
import unittest
import tempfile
from pathlib import Path
import research_store
from unittest.mock import patch
import urllib.error
import collect_awards as collector
TODAY = date(2026, 11, 10)
ACCOUNTS = [{'id': 'market-alpha', 'name': 'Alpha Robotics'}, {'id': 'market-beta', 'name': 'Beta Manufacturing'}]

def award(**changes):
    row = {'Award ID': 'AWARD-42', 'Recipient Name': 'ALPHA ROBOTICS LLC', 'Award Amount': 125000, 'Awarding Agency': 'Test agency', 'Start Date': '2026-11-09', 'generated_internal_id': 'CONT_AWARD_42'}
    row.update(changes)
    return row

class AwardCollectorTests(unittest.TestCase):
    def test_full_name_query_and_pending_result(self):
        captured = []
        def request(req, timeout):
            captured.append((json.loads(req.data), timeout, req.full_url))
            return io.BytesIO(json.dumps({'results': [award()]}).encode())
        with patch('collect_awards.urllib.request.urlopen', side_effect=request):
            batch = collector.make_batch(ACCOUNTS, limit=1, today=TODAY)
        self.assertEqual(captured[0][0]['filters']['keywords'], ['Alpha Robotics'])
        self.assertEqual(captured[0][1], 18)
        self.assertEqual(captured[0][2], collector.API_URL)
        event = batch['events'][0]
        self.assertEqual(event['verification'], 'Pending')
        self.assertEqual(event['type'], 'contract')
        self.assertIsNone(event['publishedAt'])
        self.assertEqual(event['sourceUrl'], 'https://www.usaspending.gov/award/CONT_AWARD_42')
        self.assertIn('not verified target obligations', event['amountBasis'])
        self.assertIn('ALPHA ROBOTICS LLC', event['title'])
        self.assertIn('AWARD-42', event['title'])
        self.assertEqual(batch['sources'][0]['status'], 'ok')

    def test_outage_is_logged_without_false_success(self):
        with patch('collect_awards.urllib.request.urlopen', side_effect=urllib.error.URLError('offline')):
            batch = collector.make_batch(ACCOUNTS, limit=2, today=TODAY)
        self.assertEqual(batch['events'], [])
        self.assertEqual([s['status'] for s in batch['sources']], ['failed', 'failed'])
        self.assertIn('offline', batch['sources'][0]['detail'])

    def test_offline_rows_never_attributed_as_verified(self):
        rows = [award(), award(**{'Award ID': 'NO-DATE', 'Start Date': None}), award(**{'Award ID': 'FUTURE', 'Start Date': '2027-01-01'}), award(**{'Award ID': 'OLD', 'Start Date': '2025-01-01'})]
        with patch('collect_awards.urllib.request.urlopen', side_effect=AssertionError('network used')):
            batch = collector.make_batch(ACCOUNTS, limit=1, today=TODAY, input_data={'market-alpha': {'results': rows}})
        self.assertEqual(len(batch['events']), 1)
        self.assertEqual(batch['sources'][0]['status'], 'failed')
        self.assertIn('2 malformed', batch['sources'][0]['detail'])
        self.assertIn('1 rows outside', batch['sources'][0]['detail'])
        self.assertEqual(batch['events'][0]['verification'], 'Pending')

    def test_missing_internal_id_uses_real_search_root(self):
        self.assertEqual(collector.award_url(award(generated_internal_id=None)), 'https://www.usaspending.gov/search')
        self.assertEqual(collector.award_url(award(generated_internal_id='A/B?C')), 'https://www.usaspending.gov/award/A%2FB%3FC')

    def test_invalid_amount_stays_unknown(self):
        for value in [True, -1, float('inf'), float('nan'), '123', None]:
            self.assertIsNone(collector.optional_amount(value))
        self.assertEqual(collector.optional_amount(0), 0)

    def test_invalid_envelopes_and_limits(self):
        for limit in [0, 26, True]:
            with self.assertRaises(ValueError): collector.make_batch(ACCOUNTS, limit=limit)
        for days in [0, 3661, True]:
            with self.assertRaises(ValueError): collector.make_batch(ACCOUNTS, days=days)
        with patch('collect_awards.urllib.request.urlopen', return_value=io.BytesIO(b'{not JSON')):
            batch = collector.make_batch(ACCOUNTS, limit=1, today=TODAY)
        self.assertEqual(batch['sources'][0]['status'], 'failed')
        self.assertEqual(batch['events'], [])

    def test_missing_offline_response_is_a_failure(self):
        batch = collector.make_batch(ACCOUNTS, limit=1, today=TODAY, input_data={})
        self.assertEqual(batch['sources'][0]['status'], 'failed')
        self.assertEqual(batch['events'], [])

    def test_oversized_response_is_a_failure(self):
        with patch('collect_awards.urllib.request.urlopen', return_value=io.BytesIO(b' ' * (collector.MAX_RESPONSE_BYTES + 1))):
            batch = collector.make_batch(ACCOUNTS, limit=1, today=TODAY)
        self.assertEqual(batch['sources'][0]['status'], 'failed')
        self.assertIn('2 MB', batch['sources'][0]['detail'])

    def test_real_feed_import_dedup_and_failed_cursor(self):
        with tempfile.TemporaryDirectory() as temp:
            db = Path(temp) / 'plans.sqlite'
            research_store.initialize(db)
            rows = [award(generated_internal_id=None), award(**{'Award ID': 'AWARD-43', 'generated_internal_id': None})]
            batch = collector.make_batch(ACCOUNTS, limit=1, today=TODAY, input_data={'market-alpha': {'results': rows}})
            result = research_store.ingest(db, batch, {'market-alpha'})
            self.assertEqual(result['inserted'], 2)
            repeated = research_store.ingest(db, batch, {'market-alpha'})
            self.assertEqual(repeated['inserted'], 0)
            self.assertEqual(repeated['duplicates'], 2)
            feed = research_store.feed(db)
            self.assertEqual(len(feed['events']), 2)
            self.assertTrue(all(e['verification'] == 'Pending' for e in feed['events']))
            self.assertEqual(research_store.load_reviews(db), {})
            failed = collector.make_batch(ACCOUNTS, limit=1, today=TODAY, input_data={})
            research_store.ingest(db, failed, {'market-alpha'})
            self.assertEqual(research_store.feed(db)['runs'][0]['status'], 'partial')
            self.assertEqual(research_store.feed(db)['lastSuccessfulRun'], TODAY.isoformat())

if __name__ == '__main__': unittest.main()

