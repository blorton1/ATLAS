"""Human-reviewed research and intelligence, isolated from imported market data.

Verified means a named researcher attested to evidence; this module does not
independently fetch or verify sources and never infers a customer relationship.
"""
from contextlib import closing
from datetime import date, datetime, timezone
import hashlib
import json
import re
import sqlite3
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

import account_plan_store as plans

STAGES = {'Unknown', 'Seed', 'Series A', 'Series B', 'Series C', 'Series D', 'Series E+', 'Public', 'Acquired'}
ELIGIBLE = set(STAGES)  # Funding maturity informs sales context; it is not an exclusion gate.
TYPES = {'funding', 'contract', 'hiring', 'expansion', 'ai_adoption', 'partnership', 'product_launch'}


def now():
    return datetime.now(timezone.utc).isoformat()


def text(value, field, required=False, limit=20000):
    if not isinstance(value, str) or len(value) > limit or (required and not value.strip()):
        raise ValueError(f'{field} must be {"nonempty " if required else ""}text (maximum {limit} characters)')
    return value.strip()


def day(value, field, required=False):
    if not value and not required:
        return ''
    if not isinstance(value, str):
        raise ValueError(f'{field} must use YYYY-MM-DD')
    plans.validate_date(value, field)
    if not value or date.fromisoformat(value) > datetime.now(timezone.utc).date():
        raise ValueError(f'{field} must be a nonfuture YYYY-MM-DD date')
    return value


def url(value, field, required=False):
    value = text(value, field, required, 2048)
    if not value:
        return ''
    parsed = urlsplit(value)
    try:
        port = parsed.port
    except ValueError:
        raise ValueError(f'{field} has an invalid port') from None
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password
            or re.search(r'[\s\x00-\x1f]', value) or port not in (None, 443)):
        raise ValueError(f'{field} must be an HTTPS URL without credentials')
    return value


def canonical(value):
    parsed = urlsplit(value)
    query = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True)
             if not k.lower().startswith('utm_') and k.lower() not in {'fbclid', 'gclid'}]
    return urlunsplit(('https', parsed.hostname.lower().removeprefix('www.'), parsed.path.rstrip('/') or '/', urlencode(sorted(query)), ''))


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def initialize(path):
    plans.initialize(path)
    with closing(sqlite3.connect(path)) as conn:
        conn.executescript('''
            CREATE TABLE IF NOT EXISTS research_reviews (
                account_id TEXT PRIMARY KEY, version INTEGER NOT NULL,
                review_json TEXT NOT NULL, updated_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS research_candidates (
                account_id TEXT PRIMARY KEY, domain TEXT UNIQUE NOT NULL,
                normalized_name TEXT UNIQUE NOT NULL, candidate_json TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS intelligence_events (
                id TEXT PRIMARY KEY, event_key TEXT UNIQUE NOT NULL,
                source_key TEXT UNIQUE NOT NULL, event_json TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS intelligence_runs (
                id TEXT PRIMARY KEY, run_date TEXT NOT NULL,
                status TEXT NOT NULL, run_json TEXT NOT NULL);
        ''')
        conn.commit()


def review_record(row):
    return {'version': row[0], 'review': json.loads(row[1]), 'updatedAt': row[2]}


def load_reviews(path):
    with closing(sqlite3.connect(path)) as conn:
        return {r[0]: review_record(r[1:]) for r in conn.execute('SELECT * FROM research_reviews')}


def validate_review(review):
    allowed = {'status', 'usVerified', 'sectorVerified', 'latestStage', 'latestStageVerified',
               'stageSource', 'usSource', 'sectorSource', 'checkedOn', 'rationale', 'reviewer'}
    if not isinstance(review, dict) or set(review) - allowed:
        raise ValueError('Unsupported review fields')
    result = dict(review)
    result.setdefault('status', 'Needs review')
    result.setdefault('latestStage', 'Unknown')
    if not isinstance(result['status'], str) or result['status'] not in {'Needs review', 'Qualified target', 'Outside target'}:
        raise ValueError('Unsupported review status')
    if not isinstance(result['latestStage'], str) or result['latestStage'] not in STAGES:
        raise ValueError('Unsupported funding stage')
    for key in ('usVerified', 'sectorVerified', 'latestStageVerified'):
        result.setdefault(key, False)
        if type(result[key]) is not bool:
            raise ValueError(f'{key} must be a boolean')
    for key in ('stageSource', 'usSource', 'sectorSource'):
        result[key] = url(result.get(key, ''), key)
    result['checkedOn'] = day(result.get('checkedOn', ''), 'checkedOn')
    for key in ('rationale', 'reviewer'):
        result[key] = text(result.get(key, ''), key)
    if result['status'] == 'Qualified target' and not qualified(result):
        raise ValueError('Qualification requires US presence, business fit, supporting sources, review date, sales rationale and reviewer. Funding stage is optional context.')
    return result


def qualified(review):
    return bool(isinstance(review, dict) and review.get('status') == 'Qualified target'
                and review.get('usVerified') is True and review.get('sectorVerified') is True
                and review.get('latestStage', 'Unknown') in ELIGIBLE
                and all(review.get(k) for k in ('usSource', 'sectorSource', 'checkedOn', 'rationale', 'reviewer')))


def save_review(path, account_id, version, review):
    if type(version) is not int or version < 0:
        raise ValueError('version must be a nonnegative integer')
    review = validate_review(review)
    stamp = now()
    with closing(sqlite3.connect(path, timeout=10)) as conn:
        try:
            conn.execute('BEGIN IMMEDIATE')
            row = conn.execute('SELECT version,review_json,updated_at FROM research_reviews WHERE account_id=?', (account_id,)).fetchone()
            if (row[0] if row else 0) != version:
                raise plans.VersionConflict(review_record(row) if row else {'version': 0, 'review': {}, 'updatedAt': None})
            conn.execute('INSERT INTO research_reviews VALUES(?,?,?,?) ON CONFLICT(account_id) DO UPDATE SET version=excluded.version,review_json=excluded.review_json,updated_at=excluded.updated_at',
                         (account_id, version + 1, json.dumps(review, allow_nan=False), stamp))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    return {'version': version + 1, 'review': review, 'updatedAt': stamp}


def promote(path, account_id, review_version, plan_version):
    if type(review_version) is not int or type(plan_version) is not int or review_version < 1 or plan_version < 0:
        raise ValueError('reviewVersion and planVersion must be nonnegative integers (reviewVersion at least 1)')
    with closing(sqlite3.connect(path, timeout=10)) as conn:
        try:
            conn.execute('BEGIN IMMEDIATE')
            row = conn.execute('SELECT version,review_json,updated_at FROM research_reviews WHERE account_id=?', (account_id,)).fetchone()
            if not row or row[0] != review_version:
                raise plans.VersionConflict(review_record(row) if row else {'version': 0, 'review': {}, 'updatedAt': None})
            review = json.loads(row[1])
            if not qualified(review):
                raise ValueError('Save a fully evidenced Qualified target review before promotion')
            row = conn.execute('SELECT version,plan_json,updated_at FROM account_plans WHERE account_id=?', (account_id,)).fetchone()
            if (row[0] if row else 0) != plan_version:
                raise plans.VersionConflict(plans.record(row) if row else {'version': 0, 'plan': {}, 'updatedAt': None})
            plan = json.loads(row[1]) if row else {'relationship': 'Prospect', 'stage': 'Qualified'}
            activity_id = f'research-promotion-{review_version}'
            activities = plan.get('activities', [])
            if not any(a['id'] == activity_id for a in activities):
                activities.append({'id': activity_id, 'date': datetime.now(timezone.utc).date().isoformat(),
                                   'type': 'Research qualification', 'summary': f'Promoted after review by {review["reviewer"]}. Latest disclosed stage: {review["latestStage"]}. {review["rationale"]}'})
            plan.update({'shortlisted': True, 'qualification': 'Qualified target', 'stageSource': review['stageSource'],
                         'stageRationale': review['rationale'], 'activities': activities})
            plans.validate_plan(plan)
            stamp = now()
            conn.execute('INSERT INTO account_plans VALUES(?,?,?,?) ON CONFLICT(account_id) DO UPDATE SET version=excluded.version,plan_json=excluded.plan_json,updated_at=excluded.updated_at',
                         (account_id, plan_version + 1, json.dumps(plan, allow_nan=False), stamp))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    return {'version': plan_version + 1, 'plan': plan, 'updatedAt': stamp}


def candidates(path):
    with closing(sqlite3.connect(path)) as conn:
        return [json.loads(r[0]) for r in conn.execute('SELECT candidate_json FROM research_candidates ORDER BY rowid')]


def normalized_name(value):
    return re.sub(r'[^a-z0-9]', '', value.lower())


def add_candidate(path, payload, existing_accounts):
    if not isinstance(payload, dict) or set(payload) - {'name', 'sector', 'hq', 'website', 'workflow', 'businessNeed', 'openaiFit', 'buyerRole', 'nextStep', 'priority'}:
        raise ValueError('Unsupported candidate fields')
    record = {k: text(payload.get(k, ''), k, k in {'name', 'sector', 'hq'}, 1000) for k in ('name', 'sector', 'hq', 'workflow')}
    for field in ('businessNeed','openaiFit','buyerRole','nextStep'):
        record[field] = text(payload.get(field, ''), field, False, 4000)
    record['priority'] = payload.get('priority', 'Unassessed')
    if record['priority'] not in ('High','Medium','Low','Unassessed'):
        raise ValueError('Unsupported sales priority')
    record['website'] = url(payload.get('website', ''), 'website', True)
    domain = urlsplit(record['website']).hostname.lower().removeprefix('www.')
    norm = normalized_name(record['name'])
    if not norm:
        raise ValueError('Company name must include letters or numbers')
    for account in existing_accounts:
        existing_url = account.get('website') or ''
        existing_domain = urlsplit(existing_url).hostname
        if normalized_name(account['name']) == norm or (existing_domain and existing_domain.lower().removeprefix('www.') == domain):
            raise ValueError(f'Company already exists: {account["name"]}')
    record['accountId'] = 'research-' + digest(domain)[:16]
    record['createdAt'] = now()
    with closing(sqlite3.connect(path)) as conn:
        try:
            conn.execute('INSERT INTO research_candidates VALUES(?,?,?,?)', (record['accountId'], domain, norm, json.dumps(record)))
            conn.commit()
        except sqlite3.IntegrityError:
            raise ValueError('Company name or website already exists') from None
    return record


def validate_event(event, valid_ids, collected_at):
    allowed = {'accountId', 'type', 'title', 'date', 'publishedAt', 'source', 'sourceUrl', 'verification', 'amount', 'amountBasis', 'workflow'}
    if not isinstance(event, dict) or set(event) - allowed:
        raise ValueError('Unsupported event fields')
    result = dict(event)
    if not isinstance(result.get('accountId'), str) or result['accountId'] not in valid_ids:
        raise ValueError('Event accountId must identify an existing research company')
    if not isinstance(result.get('type'), str) or result['type'] not in TYPES:
        raise ValueError('Unsupported event type')
    for key in ('title', 'source'):
        result[key] = text(result.get(key, ''), key, True, 2000)
    for key in ('workflow', 'amountBasis'):
        result[key] = text(result.get(key, ''), key)
    result['date'] = day(result.get('date'), 'date', True)
    result['publishedAt'] = day(result.get('publishedAt'), 'publishedAt') or None
    result['sourceUrl'] = url(result.get('sourceUrl', ''), 'sourceUrl', True)
    result.setdefault('verification', 'Pending')
    if not isinstance(result['verification'], str) or result['verification'] not in {'Pending', 'Primary verified'}:
        raise ValueError('verification must be Pending or Primary verified')
    result.setdefault('amount', None)
    if result['amount'] is not None and not plans.valid_amount(result['amount']):
        raise ValueError('amount must be a finite nonnegative number or null')
    if result['amount'] is not None and not result['amountBasis']:
        raise ValueError('Disclosed amounts require amountBasis (equity, ceiling, obligation, etc.)')
    result['collectedAt'] = collected_at
    result['id'] = digest([result['accountId'], result['type'], result['date'], canonical(result['sourceUrl']), result['title'].lower()])[:24]
    return result


def ingest(path, payload, valid_ids, run_kind='manual'):
    if not isinstance(payload, dict) or set(payload) - {'runDate', 'events', 'sources'}:
        raise ValueError('Expected runDate, events and sources')
    run_date = day(payload.get('runDate'), 'runDate', True)
    raw_events, raw_sources = payload.get('events'), payload.get('sources')
    if not isinstance(raw_events, list) or len(raw_events) > 500:
        raise ValueError('events must be an array of at most 500 items')
    if not isinstance(raw_sources, list) or len(raw_sources) > 100:
        raise ValueError('sources must be an array of at most 100 items')
    stamp = now()
    events = [validate_event(event, set(valid_ids), stamp) for event in raw_events]
    sources = []
    for source in raw_sources:
        if not isinstance(source, dict) or set(source) - {'name', 'url', 'status', 'detail'}:
            raise ValueError('Unsupported source fields')
        item = {'name': text(source.get('name', ''), 'source name', True, 1000),
                'url': url(source.get('url', ''), 'source URL', True),
                'status': source.get('status'), 'detail': text(source.get('detail', ''), 'source detail')}
        if not isinstance(item['status'], str) or item['status'] not in {'ok', 'failed', 'paywalled'}:
            raise ValueError('Source status must be ok, failed or paywalled')
        sources.append(item)
    run_id = digest([run_kind, payload])[:24]
    status = 'success' if sources and all(s['status'] == 'ok' for s in sources) else 'partial'
    inserted = 0
    with closing(sqlite3.connect(path, timeout=10)) as conn:
        try:
            conn.execute('BEGIN IMMEDIATE')
            for event in events:
                event_key = digest([event['accountId'], event['type'], event['date'], re.sub(r'\s+', ' ', event['title'].lower()).strip()])
                source_key = digest([event['accountId'], event['type'], event['date'], canonical(event['sourceUrl']), event['title'].lower()])
                cursor = conn.execute('INSERT OR IGNORE INTO intelligence_events VALUES(?,?,?,?)', (event['id'], event_key, source_key, json.dumps(event, allow_nan=False)))
                inserted += cursor.rowcount
            run = {'id': run_id, 'kind':run_kind, 'runDate': run_date, 'status': status, 'sources': sources,
                   'collectedAt': stamp, 'inserted': inserted, 'duplicates': len(events) - inserted}
            conn.execute('INSERT OR IGNORE INTO intelligence_runs VALUES(?,?,?,?)', (run_id, run_date, status, json.dumps(run)))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    return {'inserted': inserted, 'duplicates': len(events) - inserted, 'runId': run_id}


def feed(path):
    with closing(sqlite3.connect(path)) as conn:
        events = [json.loads(r[0]) for r in conn.execute('SELECT event_json FROM intelligence_events')]
        runs = [json.loads(r[0]) for r in conn.execute('SELECT run_json FROM intelligence_runs ORDER BY run_date DESC, rowid DESC')]
    events.sort(key=lambda e: (e['date'], e['collectedAt']), reverse=True)
    return {'events': events, 'runs': runs, 'lastSuccessfulRun': next((r['runDate'] for r in runs if r['status'] == 'success'), None)}
