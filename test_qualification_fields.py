"""Qualification and federal fields round-trip without changing existing CRM records."""
from pathlib import Path
import tempfile
import unittest

import account_plan_store as store


class QualificationFieldsTests(unittest.TestCase):
    def test_additive_fields_preserve_existing_plan_and_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / 'plans.sqlite'
            store.initialize(db)
            original = dict(owner='Owner', notes='Existing notes',
                            contacts=[dict(id='c1', name='Contact', role='Operations')])
            store.save(db, 'example', 0, original)
            fields = dict(salesMotion='Federal', valueBaseline='Manual process: validate hours',
                          valueTarget='Agree measurable pilot KPI', economicBuyer='To identify',
                          champion='To validate', decisionProcess='Map stakeholders',
                          competitiveAdvantage='Compare incumbent', compellingEvent='Budget review',
                          missionOwner='Program office to identify', fundingPath='Funding source to validate',
                          acquisitionPath='Contracting route to confirm', deploymentRequirements='Data boundary to confirm')
            store.save(db, 'example', 1, {**original, **fields})
            record = store.load_all(db)['example']
            self.assertEqual(record['version'], 2)
            self.assertEqual(record['plan'], {**original, **fields})

    def test_optional_motion_and_text_validation(self):
        store.validate_plan({})
        store.validate_plan(dict(salesMotion=''))
        for motion in ('Commercial', 'Federal', 'Partner'):
            store.validate_plan(dict(salesMotion=motion))
        with self.assertRaises(ValueError):
            store.validate_plan(dict(salesMotion='Government'))
        with self.assertRaises(ValueError):
            store.validate_plan(dict(valueTarget=5))
        with self.assertRaises(ValueError):
            store.validate_plan(dict(deploymentRequirements='x' * 20001))


if __name__ == '__main__':
    unittest.main()
