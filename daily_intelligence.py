"""RSS/Atom discovery intake: pending headlines only, no automatic qualification.

Run on demand or from an OS scheduler. Sources must be configured explicitly in
daily_feeds.json. Dated reports retain unmatched headlines for company discovery.
"""
import argparse
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import json
from pathlib import Path
import re
import urllib.request
import xml.etree.ElementTree as ET

import research_store

ROOT = Path(__file__).resolve().parent


def parse_feed(raw):
    if b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():
        raise ValueError('DTD and entity declarations are unsupported')
    root = ET.fromstring(raw)
    local = lambda tag: tag.rsplit('}', 1)[-1]
    if local(root.tag) not in {'rss', 'feed', 'RDF'}:
        raise ValueError('Source is not RSS/Atom XML')
    entries = []
    for item in root.iter():
        if local(item.tag) not in {'item', 'entry'}:
            continue
        fields = {local(child.tag): child for child in item}
        get = lambda key: ''.join(fields[key].itertext()).strip() if key in fields else ''
        title = get('title')[:1000]
        links = [c for c in item if local(c.tag) == 'link']
        link = next((c.get('href') or (c.text or '').strip() for c in links
                     if c.get('rel', 'alternate') == 'alternate'), '')
        stamp = get('pubDate') or get('published') or get('updated') or get('date')
        try:
            try:
                published = parsedate_to_datetime(stamp)
            except (ValueError, TypeError):
                published = datetime.fromisoformat(stamp.replace('Z', '+00:00'))
            if published.tzinfo is None:
                published = published.replace(tzinfo=timezone.utc)
            published = published.astimezone(timezone.utc)
            research_store.url(link, 'headline URL', True)
            if title:
                entries.append({'title':title, 'sourceUrl':link, 'date':published.date().isoformat()})
        except (ValueError, TypeError, OverflowError):
            continue
    return entries


def event_kind(title):
    text = title.lower()
    for words, kind in [(['series ', 'funding', 'raises', 'financing'], 'funding'),
                        (['contract', 'award', 'task order'], 'contract'),
                        (['factory', 'facility', 'expansion', 'plant'], 'expansion'),
                        (['hiring', 'jobs', 'workforce'], 'hiring'),
                        (['partnership', 'partners with'], 'partnership'),
                        (['ai ', 'artificial intelligence'], 'ai_adoption')]:
        if any(word in text for word in words):
            return kind
    return 'product_launch'


def collect(plans_db, accounts, config, output_dir):
    research_store.initialize(plans_db)
    feeds = json.loads(Path(config).read_text(encoding='utf-8-sig'))
    if not isinstance(feeds, list) or len(feeds) > 30:
        raise ValueError('Feed configuration must be a list of at most 30 sources')
    for source in feeds:
        if not isinstance(source, dict) or set(source) != {'name', 'url'}:
            raise ValueError('Each configured feed needs exactly name and url')
        research_store.text(source['name'], 'source name', True, 300)
        research_store.url(source['url'], 'feed URL', True)
    today = datetime.now(timezone.utc).date()
    runs = research_store.feed(plans_db)['runs']
    since = today - timedelta(days=3)
    sources, events, unmatched = [], [], []
    for source in feeds:
        name = research_store.text(source['name'], 'source name', True, 300)
        url = research_store.url(source['url'], 'feed URL', True)
        # A successful manual import or award search cannot advance an RSS cursor.
        previous = next((run['runDate'] for run in runs if run.get('kind') == 'rss' and any(
            s['url'] == url and s['status'] == 'ok' for s in run['sources'])), None)
        source_since = min(today - timedelta(days=3), datetime.fromisoformat(previous).date()) if previous else today - timedelta(days=3)
        since = min(since, source_since)
        status = {'name':name, 'url':url, 'status':'ok', 'detail':''}
        try:
            request = urllib.request.Request(url, headers={'User-Agent':'ATLAS-local-research/1.0'})
            with urllib.request.urlopen(request, timeout=15) as response:
                raw = response.read(2_000_001)
            if len(raw) > 2_000_000:
                raise ValueError('Feed exceeds 2 MB limit')
            entries = parse_feed(raw)
            for entry in entries:
                if not (source_since.isoformat() <= entry['date'] <= today.isoformat()):
                    continue
                # Whole-name matches are still unverified entity candidates.
                matches = [a for a in accounts if re.search(r'(?<!\w)' + re.escape(a['name']) + r'(?!\w)', entry['title'], re.I)]
                if not matches:
                    unmatched.append({**entry, 'source':name})
                for account in matches:
                    events.append({**entry, 'accountId':account['id'], 'type':event_kind(entry['title']),
                                   'publishedAt':entry['date'], 'source':name, 'verification':'Pending',
                                   'amount':None, 'amountBasis':'Not extracted; verify original source',
                                   'workflow':'Unverified headline match; validate entity and proposed workflow'})
            status['detail'] = f'{len(entries)} dated headlines parsed; discovery only'
        except Exception as exc:
            status.update(status='failed', detail=str(exc)[:1000])
        sources.append(status)
    if len(events) > 500:
        raise ValueError('More than 500 headline matches. No events or cursors were saved; narrow the configured feeds and retry.')
    batch = {'runDate':today.isoformat(), 'events':events, 'sources':sources}
    result = research_store.ingest(plans_db, batch, {a['id'] for a in accounts}, run_kind='rss')
    report = {**batch, 'result':result, 'windowStart':since.isoformat(), 'unmatchedHeadlines':unmatched,
              'coverageLimit':'RSS retention may not cover the full catch-up window. HTML/paywalled sources need manual review.'}
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H%M%S%fZ')
    (output_dir / (stem + '.json')).write_text(json.dumps(report, indent=2), encoding='utf-8')
    lines = [f'# ATLAS daily discovery — {today}', f'Window starts {since}. All headline matches remain Pending.',
             report['coverageLimit'], f"Imported {result['inserted']}; duplicates {result['duplicates']}.", '\n## Source coverage']
    lines += [f"- {s['name']}: {s['status']} — {s['detail']}" for s in sources]
    lines += ['\n## Unmatched headlines — research queue'] + [f"- {e['date']} [{e['title']}]({e['sourceUrl']})" for e in unmatched]
    (output_dir / (stem + '.md')).write_text('\n'.join(lines), encoding='utf-8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', type=Path, default=ROOT/'atlas_market.sqlite')
    parser.add_argument('--plans-db', type=Path, default=ROOT/'atlas_plans.sqlite')
    parser.add_argument('--feeds', type=Path, default=ROOT/'daily_feeds.json')
    parser.add_argument('--output', type=Path, default=ROOT/'daily_updates')
    args = parser.parse_args()
    from atlas_server import workspace_accounts
    research_store.initialize(args.plans_db)
    _, accounts = workspace_accounts(args.db, args.plans_db)
    report = collect(args.plans_db, accounts, args.feeds, args.output)
    print(json.dumps({'result':report['result'], 'sources':report['sources'], 'windowStart':report['windowStart']}, indent=2))
