import copy
import importlib.util
import json
import unittest
from collections.abc import Callable
from pathlib import Path
from typing import TypedDict, cast

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('validate_plan', ROOT / 'scripts/validate_plan.py')
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
# Loaded from a file path, so the checker cannot see the signature declared in validate_plan.py.
validate = cast('Callable[[object, object], tuple[list[str], list[str], list[str]]]', module.validate)
PROFILE = cast('object', json.loads((ROOT / 'profiles/four-modules.json').read_text()))

Event = dict[str, str | bool | None]


class Plan(TypedDict):
    school_year: str
    calendar_id: str
    period: dict[str, str]
    events: list[Event]


def new_plan() -> Plan:
    return {'school_year': '2026-2027', 'calendar_id': 'example',
            'period': {'start': '2026-08-01', 'end': '2027-07-31'},
            'events': [{'title': 'Activity', 'date': '2027-03-22',
                        'start': '08:10', 'end': '09:40',
                        'source': 'user request', 'layout': 'module'}]}


def check(plan: Plan, profile: object = PROFILE) -> tuple[list[str], list[str], list[str]]:
    return validate(plan, profile)


class PlanValidation(unittest.TestCase):
    def test_module_and_partial_module(self):
        plan = new_plan()
        self.assertEqual(check(plan)[0], [])
        plan['events'][0]['start'] = '09:00'
        self.assertEqual(check(plan)[0], [])

    def test_break_and_outside_module(self):
        plan = new_plan()
        plan['events'][0]['end'] = '10:20'
        self.assertTrue(check(plan)[0])
        plan['events'][0].update(start='07:00', end='08:00')
        self.assertTrue(check(plan)[0])

    def test_continuous_requires_reason(self):
        plan = new_plan()
        plan['events'][0].update(layout='continuous', end='16:00')
        self.assertTrue(check(plan)[0])
        plan['events'][0]['classification_source'] = 'User confirmed continuous course'
        self.assertEqual(check(plan)[0], [])

    def test_all_day_is_explicit_and_not_module(self):
        plan = new_plan()
        event = plan['events'][0]
        event.update(all_day=True)
        self.assertTrue(check(plan)[0])
        del event['start'], event['end']
        self.assertTrue(check(plan)[0])
        event.update(layout='continuous', classification_source='Source says all day')
        self.assertEqual(check(plan)[0], [])

    def test_actual_period_and_dates(self):
        plan = new_plan()
        for value in ['2026-07-31', '2027-08-01', '2027-02-29', '20270322']:
            with self.subTest(value=value):
                plan['events'][0]['date'] = value
                self.assertTrue(check(plan)[0])

    def test_duplicate_and_null_source(self):
        plan = new_plan()
        plan['events'].append(copy.deepcopy(plan['events'][0]))
        self.assertTrue(check(plan)[0])
        _ = plan['events'].pop()
        plan['events'][0]['source'] = None
        self.assertTrue(check(plan)[0])

    def test_all_enclosing_overlaps(self):
        plan = new_plan()
        event = plan['events'][0]
        event.update(layout='continuous', classification_source='User confirmed', end='15:30')
        for title, start, end in [('B', '10:10', '11:40'), ('C', '12:15', '13:45')]:
            child = copy.deepcopy(event)
            child.update(title=title, start=start, end=end, layout='module')
            plan['events'].append(child)
        errors, warnings, _ = check(plan)
        self.assertEqual(errors, [])
        self.assertEqual(len(warnings), 2)

    def test_generic_without_module_profile(self):
        plan = new_plan()
        _ = plan['events'][0].pop('layout')
        plan['events'][0].update(start='09:00', end='11:00')
        self.assertEqual(check(plan, profile=None)[0], [])
        self.assertTrue(check(plan)[0])

    def test_invalid_profile_and_school_year(self):
        plan = new_plan()
        self.assertTrue(check(plan, profile={'modules': []})[0])
        plan['school_year'] = '2026-2029'
        self.assertTrue(check(plan)[0])


if __name__ == '__main__':
    _ = unittest.main()
