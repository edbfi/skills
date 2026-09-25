import copy
import importlib.util
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('validate_plan', ROOT / 'scripts/validate_plan.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
PROFILE = json.loads((ROOT / 'profiles/four-modules.json').read_text())


class PlanValidation(unittest.TestCase):
    def setUp(self):
        self.plan = {'school_year': '2026-2027', 'calendar_id': 'example',
                     'period': {'start': '2026-08-01', 'end': '2027-07-31'},
                     'events': [{'title': 'Activity', 'date': '2027-03-22',
                                 'start': '08:10', 'end': '09:40',
                                 'source': 'user request', 'layout': 'module'}]}

    def check(self, profile=PROFILE):
        return module.validate(self.plan, profile)

    def test_module_and_partial_module(self):
        self.assertEqual(self.check()[0], [])
        self.plan['events'][0]['start'] = '09:00'
        self.assertEqual(self.check()[0], [])

    def test_break_and_outside_module(self):
        self.plan['events'][0]['end'] = '10:20'
        self.assertTrue(self.check()[0])
        self.plan['events'][0].update(start='07:00', end='08:00')
        self.assertTrue(self.check()[0])

    def test_continuous_requires_reason(self):
        self.plan['events'][0].update(layout='continuous', end='16:00')
        self.assertTrue(self.check()[0])
        self.plan['events'][0]['classification_source'] = 'User confirmed continuous course'
        self.assertEqual(self.check()[0], [])

    def test_all_day_is_explicit_and_not_module(self):
        event = self.plan['events'][0]
        event.update(all_day=True)
        self.assertTrue(self.check()[0])
        del event['start'], event['end']
        self.assertTrue(self.check()[0])
        event.update(layout='continuous', classification_source='Source says all day')
        self.assertEqual(self.check()[0], [])

    def test_actual_period_and_dates(self):
        for value in ['2026-07-31', '2027-08-01', '2027-02-29', '20270322']:
            with self.subTest(value=value):
                self.plan['events'][0]['date'] = value
                self.assertTrue(self.check()[0])

    def test_duplicate_and_null_source(self):
        self.plan['events'].append(copy.deepcopy(self.plan['events'][0]))
        self.assertTrue(self.check()[0])
        self.plan['events'].pop()
        self.plan['events'][0]['source'] = None
        self.assertTrue(self.check()[0])

    def test_all_enclosing_overlaps(self):
        event = self.plan['events'][0]
        event.update(layout='continuous', classification_source='User confirmed', end='15:30')
        for title, start, end in [('B', '10:10', '11:40'), ('C', '12:15', '13:45')]:
            child = copy.deepcopy(event)
            child.update(title=title, start=start, end=end, layout='module')
            self.plan['events'].append(child)
        errors, warnings, _ = self.check()
        self.assertEqual(errors, [])
        self.assertEqual(len(warnings), 2)

    def test_generic_without_module_profile(self):
        self.plan['events'][0].pop('layout')
        self.plan['events'][0].update(start='09:00', end='11:00')
        self.assertEqual(self.check(profile=None)[0], [])
        self.assertTrue(self.check()[0])

    def test_invalid_profile_and_school_year(self):
        self.assertTrue(self.check(profile={'modules': []})[0])
        self.plan['school_year'] = '2026-2029'
        self.assertTrue(self.check()[0])


if __name__ == '__main__':
    unittest.main()
