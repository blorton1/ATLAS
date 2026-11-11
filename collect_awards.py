"""Optional USAspending discovery: stage search matches, never verified awards.

Run after starting with the Pro Handoff research database. Results enter the
shared daily intelligence feed as Pending, without changing qualification,
account plans, customer status, or public-dollar metrics.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta, timezone
import json
import math
from pathlib import Path
import urllib.error
import urllib.parse
import urllib.request

ROOT = Path(__file__).resolve().parent
API_URL = 'https://api.usaspending.gov/api/v2/search/spending_by_award/'
AMOUNT_BASIS = 'Unreviewed USAspending search match; not verified target obligations'
MAX_RESPONSE_BYTES = 2_000_000


def award_url(row):
    internal_id = row.get('generated_internal_id')
    if not isinstance(internal_id, bool) and isinstance(internal_id, (str, int)) and 0 < len(str(internal_id).strip()) <= 500:
        return 'https://www.usaspending.gov/award/' + urllib.parse.quote(str(internal_id).strip(), safe='')
    return 'https://www.usaspending.gov/search'


def valid_date(value, today):
    if not isinstance(value, str):
        return None
    try:
        parsed = date.fromisoformat(value)
        if parsed.isoformat() != value or parsed > today:
            return None
        return value
    except ValueError:
        return None


def optional_amount(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        return value if math.isfinite(value) and value >= 0 else None
    except OverflowError:
        return None


def request_payload(name, cutoff, today):
    return {
        'filters': {
            'keywords': [name],
            'time_period': [{'start_date': cutoff.isoformat(), 'end_date': today.isoformat()}],
            'award_type_codes': ['A', 'B', 'C', 'D'],
        },
        'fields': ['Award ID', 'Recipient Name', 'Award Amount', 'Awarding Agency', 'Start Date'],
        'page': 1, 'limit': 10, 'sort': 'Award Amount', 'order': 'desc', 'subawards': False,
    }


def fetch_results(payload):
    request = urllib.request.Request(API_URL, data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json', 'User-Agent': 'ATLAS-local-research/1.0'}, method='POST')
    with urllib.request.urlopen(request, timeout=18) as response:
        body = response.read(MAX_RESPONSE_BYTES + 1)
    if len(body) > MAX_RESPONSE_BYTES:
        raise ValueError('Response exceeded the 2 MB limit')
    return json.loads(body)


def make_batch(accounts, *, limit=3, days=3, input_data=None, today=None):
    """Build an import batch. Offline input is keyed by exact account ID.

    Each value is the official API response shape {"results": [...]}, or
    {"error": "..."}. A missing account is a recorded source failure.
    Limit is intentionally bounded: this is a small, human-reviewed pilot.
    """
    if type(limit) is not int or not 1 <= limit <= 25:
        raise ValueError('limit must be between 1 and 25')
    if type(days) is not int or not 1 <= days <= 3660:
        raise ValueError('days must be between 1 and 3660')
    if input_data is not None and not isinstance(input_data, dict):
        raise ValueError('Offline input must be an object keyed by account ID')
    today = today or datetime.now(timezone.utc).date()
    cutoff = today - timedelta(days=days)
    batch = {'runDate': today.isoformat(), 'events': [], 'sources': []}
    selected = sorted(accounts, key=lambda a: (a['name'].casefold(), a['id']))[:limit]
    for account in selected:
        source = {'name': 'USAspending search: ' + account['name'], 'url': API_URL, 'status': 'ok', 'detail': ''}
        batch['sources'].append(source)
        try:
            if input_data is None:
                result = fetch_results(request_payload(account['name'], cutoff, today))
            else:
                if account['id'] not in input_data:
                    raise ValueError('No offline response supplied for this account')
                result = input_data[account['id']]
            if not isinstance(result, dict):
                raise ValueError('API response must be an object')
            if result.get('error'):
                raise ValueError(str(result['error'])[:2000])
            rows = result.get('results')
            if not isinstance(rows, list) or len(rows) > 100:
                raise ValueError('API results must be an array of at most 100 rows')
            skipped = 0
            outside = 0
            for row in rows:
                if not isinstance(row, dict):
                    skipped += 1
                    continue
                award = row.get('Award ID')
                recipient = row.get('Recipient Name')
                event_date = valid_date(row.get('Start Date'), today)
                if not isinstance(award, str) or not award.strip() or not isinstance(recipient, str) or not recipient.strip() or not event_date:
                    skipped += 1
                    continue
                if date.fromisoformat(event_date) < cutoff:
                    outside += 1
                    continue
                agency = str(row.get('Awarding Agency') or 'Agency not supplied')[:200]
                title = f'UNREVIEWED award match: {recipient.strip()[:300]} | {award.strip()[:200]} | {agency}'
                batch['events'].append({
                    'accountId': account['id'], 'type': 'contract', 'title': title,
                    'date': event_date,
                    # The endpoint supplies award start dates, not publication dates.
                    'publishedAt': None,
                    'source': 'USAspending keyword search (unreviewed)', 'sourceUrl': award_url(row),
                    'verification': 'Pending', 'amount': optional_amount(row.get('Award Amount')),
                    'amountBasis': AMOUNT_BASIS,
                    'workflow': 'Research lead only. Verify recipient legal name, UEI, ownership and award identifier before attributing this award to the prospect. No confirmed obligation or OpenAI revenue is asserted.',
                })
            source['detail'] = f'Checked first {len(rows)} results; {skipped} malformed or undated rows skipped; {outside} rows outside the requested window. Search is not exhaustive. All matches require entity/UEI review.'
            if skipped:
                source['status'] = 'failed'
        except (urllib.error.URLError, TimeoutError, OSError, ValueError, UnicodeError) as exc:
            source['status'] = 'failed'
            source['detail'] = ('Collection failed: ' + str(exc))[:4000]
    return batch


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', type=Path, default=ROOT / 'atlas_market.sqlite')
    parser.add_argument('--plans-db', type=Path, default=ROOT / 'atlas_plans.sqlite')
    parser.add_argument('--limit', type=int, default=3)
    parser.add_argument('--days', type=int, default=3)
    parser.add_argument('--input', type=Path, help='Offline API responses keyed by exact account ID; makes no network calls')
    args = parser.parse_args()
    import atlas_server
    import research_store
    _, accounts = atlas_server.load_accounts(args.db)
    research_store.initialize(args.plans_db)
    # Include research-intake companies in the same collection workflow.
    if hasattr(research_store, 'candidates'):
        for candidate in research_store.candidates(args.plans_db):
            accounts.append({'id': candidate.get('accountId', candidate.get('id')), 'name': candidate['name']})
    offline = json.loads(args.input.read_text(encoding='utf-8-sig')) if args.input else None
    batch = make_batch(accounts, limit=args.limit, days=args.days, input_data=offline)
    result = research_store.ingest(args.plans_db, batch, {a['id'] for a in accounts}, run_kind='awards')
    print(json.dumps({'result': result, 'sources': batch['sources'], 'note': 'All candidate matches remain Pending; no qualification or verified-dollar updates.'}, indent=2))


if __name__ == '__main__':
    main()

