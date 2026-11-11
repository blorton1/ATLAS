"""Versioned local account plans, stored independently from imported research."""
from contextlib import closing
from datetime import date, datetime, timezone
import json
import math
from pathlib import Path
import sqlite3
from urllib.parse import urlsplit

TEXT_FIELDS = {
    'qualification', 'stageSource', 'stageRationale', 'stage', 'owner',
    'nextAction', 'nextActionDate', 'notes', 'planUpdatedAt', 'relationship', 'objectives',
}
LIST_FIELDS = {
    'contacts': {'id', 'name', 'role', 'email', 'influence'},
    'opportunities': {'id', 'name', 'stage', 'amount', 'product', 'nextStep'},
    'activities': {'id', 'date', 'type', 'summary'},
}
SALES_STAGES = {'Identified', 'Qualified', 'Outreach', 'Discovery', 'Pilot', 'Opportunity',
                'Customer', 'Growth discovery', 'Expansion opportunity', 'Disqualified'}
OPPORTUNITY_STAGES = {'Discovery', 'Evaluation', 'Pilot', 'Proposal', 'Negotiation', 'Won', 'Lost'}


class VersionConflict(Exception):
    def __init__(self, current):
        self.current = current
        super().__init__('Account plan changed. Reload the saved plan before retrying.')


def validate_date(value, field):
    if value:
        try:
            if date.fromisoformat(value).isoformat() != value:
                raise ValueError()
        except (ValueError, TypeError):
            raise ValueError(f'{field} must use YYYY-MM-DD') from None


def valid_amount(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def validate_plan(plan):
    if not isinstance(plan, dict) or set(plan) - TEXT_FIELDS - set(LIST_FIELDS) - {'shortlisted'}:
        raise ValueError('Plan contains unsupported fields or is not an object')
    for field in TEXT_FIELDS:
        value = plan.get(field)
        if value is not None and (not isinstance(value, str) or len(value) > 20000):
            raise ValueError(f'{field} must be text of at most 20000 characters')
    for field, allowed in {
        'qualification': {'Needs review', 'Qualified target', 'Outside target'},
        'stage': SALES_STAGES,
        'relationship': {'Prospect', 'Customer', 'Partner'},
    }.items():
        if plan.get(field) not in (None, '') and plan[field] not in allowed:
            raise ValueError(f'Unsupported {field}')
    if 'shortlisted' in plan and not isinstance(plan['shortlisted'], bool):
        raise ValueError('shortlisted must be a boolean')
    source = plan.get('stageSource')
    if source:
        parsed = urlsplit(source)
        if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
            raise ValueError('stageSource must be an HTTPS URL')
    if plan.get('qualification') == 'Qualified target' and not (plan.get('stageRationale') or '').strip():
        raise ValueError('Qualified prospects require a sales-fit rationale')
    validate_date(plan.get('nextActionDate'), 'nextActionDate')
    if plan.get('planUpdatedAt'):
        try:
            datetime.fromisoformat(plan['planUpdatedAt'].replace('Z', '+00:00'))
        except ValueError:
            raise ValueError('planUpdatedAt must be an ISO timestamp') from None
    for field, keys in LIST_FIELDS.items():
        records = plan.get(field, [])
        if not isinstance(records, list) or len(records) > 250:
            raise ValueError(f'{field} must be an array with at most 250 entries')
        ids = set()
        for record in records:
            if not isinstance(record, dict) or set(record) - keys:
                raise ValueError(f'Invalid {field} entry')
            record_id = record.get('id')
            if not isinstance(record_id, str) or not record_id.strip() or record_id in ids:
                raise ValueError(f'{field} entry IDs must be unique nonempty text')
            ids.add(record_id)
            for key, value in record.items():
                if key == 'amount' and field == 'opportunities':
                    if value not in (None, '') and not valid_amount(value):
                        raise ValueError('Opportunity amount must be a finite nonnegative number or null')
                elif value is not None and (not isinstance(value, str) or len(value) > 20000):
                    raise ValueError(f'{field}.{key} must be text')
            if field == 'opportunities' and record.get('stage') not in (None, '') and record['stage'] not in OPPORTUNITY_STAGES:
                raise ValueError('Unsupported opportunity stage')
            if field == 'activities':
                validate_date(record.get('date'), 'Activity date')
    return plan


def initialize(path: Path):
    with closing(sqlite3.connect(path)) as conn:
        conn.execute('''CREATE TABLE IF NOT EXISTS account_plans (
            account_id TEXT PRIMARY KEY, version INTEGER NOT NULL,
            plan_json TEXT NOT NULL, updated_at TEXT NOT NULL)''')
        conn.commit()


def record(row):
    return {'version': row[0], 'plan': json.loads(row[1]), 'updatedAt': row[2]}


def load_all(path: Path):
    with closing(sqlite3.connect(path)) as conn:
        return {row[0]: record(row[1:]) for row in conn.execute(
            'SELECT account_id,version,plan_json,updated_at FROM account_plans')}


def save(path: Path, account_id: str, version: int, plan: dict):
    if type(version) is not int or version < 0:
        raise ValueError('version must be a nonnegative integer')
    validate_plan(plan)
    encoded = json.dumps(plan, ensure_ascii=False, allow_nan=False, separators=(',', ':'))
    updated_at = datetime.now(timezone.utc).isoformat()
    with closing(sqlite3.connect(path, timeout=10)) as conn:
        try:
            conn.execute('BEGIN IMMEDIATE')
            current = conn.execute('SELECT version,plan_json,updated_at FROM account_plans WHERE account_id=?', (account_id,)).fetchone()
            actual_version = current[0] if current else 0
            if actual_version != version:
                raise VersionConflict(record(current) if current else {'version': 0, 'plan': {}, 'updatedAt': None})
            conn.execute('''INSERT INTO account_plans VALUES(?,?,?,?)
                ON CONFLICT(account_id) DO UPDATE SET version=excluded.version,
                plan_json=excluded.plan_json,updated_at=excluded.updated_at''',
                (account_id, version + 1, encoded, updated_at))
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    return {'version': version + 1, 'plan': plan, 'updatedAt': updated_at}
