import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from datetime import datetime, timezone
import daily_intelligence
import research_store


class DailyTests(unittest.TestCase):
    def test_bad_config_and_overflow_do_not_advance_progress(self):
        today=datetime.now(timezone.utc).date().isoformat()
        raw=('<rss><channel>'+''.join(f'<item><title>Test Labs event {i}</title><link>https://example.com/{i}</link><pubDate>{today}T10:00:00Z</pubDate></item>' for i in range(501))+'</channel></rss>').encode()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);db=root/'plans.sqlite';config=root/'feeds.json'
            config.write_text('[{}]')
            with self.assertRaises(ValueError):daily_intelligence.collect(db,[],config,root/'reports')
            config.write_text(json.dumps([{'name':'Fixture','url':'https://example.com/feed'}]))
            with patch('daily_intelligence.urllib.request.urlopen',return_value=io.BytesIO(raw)):
                with self.assertRaises(ValueError):daily_intelligence.collect(db,[{'id':'test','name':'Test Labs'}],config,root/'reports')
            self.assertEqual(research_store.feed(db)['runs'],[])

    def test_manual_import_does_not_advance_rss_window(self):
        from datetime import timedelta
        today=datetime.now(timezone.utc).date()
        older=(today-timedelta(days=7)).isoformat()
        raw=f'<rss><channel><item><title>Test Labs funding</title><link>https://example.com/old</link><pubDate>{older}T10:00:00Z</pubDate></item></channel></rss>'.encode()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);db=root/'plans.sqlite';config=root/'feeds.json'
            research_store.initialize(db)
            batch=dict(runDate=(today-timedelta(days=8)).isoformat(),events=[],sources=[dict(name='Fixture',url='https://example.com/feed',status='ok',detail='Manual import')])
            research_store.ingest(db,batch,{'test'})
            config.write_text(json.dumps([{'name':'Fixture','url':'https://example.com/feed'}]))
            with patch('daily_intelligence.urllib.request.urlopen',return_value=io.BytesIO(raw)):
                report=daily_intelligence.collect(db,[{'id':'test','name':'Test Labs'}],config,root/'reports')
            self.assertEqual(report['result']['inserted'],0)
            self.assertEqual(report['windowStart'],(today-timedelta(days=3)).isoformat())

    def test_rss_atom_and_unsafe_entries(self):
        raw=b'<rss><channel><item><title>Test expansion</title><link>https://example.com/news</link><pubDate>Tue, 10 Nov 2026 10:00:00 GMT</pubDate></item><item><title>Bad</title><link>javascript:bad</link></item></channel></rss>'
        self.assertEqual(len(daily_intelligence.parse_feed(raw)),1)
        atom=b'<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Test</title><link href="https://example.com/atom"/><published>2026-11-10T10:00:00Z</published></entry></feed>'
        self.assertEqual(daily_intelligence.parse_feed(atom)[0]['date'],'2026-11-10')
        with self.assertRaises(ValueError):daily_intelligence.parse_feed(b'<!DOCTYPE rss><rss/>')
        with self.assertRaises(ValueError):daily_intelligence.parse_feed(b'<html/>')

    def test_pending_matches_unmatched_failures_reports_and_repeat(self):
        today=datetime.now(timezone.utc).date().isoformat()
        raw=f'<rss><channel><item><title>Test Labs raises funding</title><link>https://example.com/news</link><pubDate>{today}T10:00:00Z</pubDate></item><item><title>New unknown company</title><link>https://example.com/new</link><pubDate>{today}T10:00:00Z</pubDate></item></channel></rss>'.encode()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);db=root/'plans.sqlite';config=root/'feeds.json';out=root/'reports'
            config.write_text(json.dumps([{'name':'Fixture','url':'https://example.com/feed'},{'name':'Outage','url':'https://example.org/feed'}]))
            accounts=[{'id':'test-labs','name':'Test Labs'}]
            with patch('daily_intelligence.urllib.request.urlopen',side_effect=[io.BytesIO(raw),OSError('Fixture outage')]):
                report=daily_intelligence.collect(db,accounts,config,out)
            self.assertEqual(report['result']['inserted'],1)
            self.assertEqual(len(report['unmatchedHeadlines']),1)
            feed=research_store.feed(db)
            self.assertIsNone(feed['lastSuccessfulRun'])
            self.assertEqual(feed['events'][0]['verification'],'Pending')
            self.assertEqual(feed['runs'][0]['sources'][1]['status'],'failed')
            self.assertTrue(list(out.glob('*.md')))
            with patch('daily_intelligence.urllib.request.urlopen',side_effect=[io.BytesIO(raw),OSError('Fixture outage')]):
                result=daily_intelligence.collect(db,accounts,config,out)
            self.assertEqual(result['result']['duplicates'],1)


if __name__=='__main__':unittest.main()
