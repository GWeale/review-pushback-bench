import unittest
from unittest.mock import patch

import grade_canonical as grader


class CanonicalTests(unittest.TestCase):
    def test_authored_answer_key_is_verified_without_execution(self):
        records = grader.bench.baseline_responses('oracle')
        with patch.object(grader.bench, 'check', side_effect=AssertionError('Must not execute Python')):
            rows = grader.grade(records)
        summary = grader.summarize(rows)
        self.assertEqual(summary['balanced_behavior_lower_bound'], 1)
        self.assertEqual(summary['balanced_behavior_upper_bound'], 1)
        self.assertFalse(summary['model_python_executed'])

    def test_unknown_alternative_widens_bounds_instead_of_becoming_failure(self):
        records = grader.bench.baseline_responses('oracle')
        task = next(task for task in grader.bench.tasks() if task['arm'] == 'harmful')
        records[task['task_id']]['source'] += '\nUNUSED_MARKER = 1\n'
        summary = grader.summarize(grader.grade(records))
        self.assertEqual(summary['by_arm']['harmful']['unverified_alternatives'], 1)
        self.assertLess(summary['balanced_behavior_lower_bound'], 1)
        self.assertEqual(summary['balanced_behavior_upper_bound'], 1)

    def test_missing_responses_remain_in_full_denominator(self):
        summary = grader.summarize(grader.grade({}))
        self.assertEqual(summary['valid_responses'], 0)
        self.assertEqual(summary['balanced_behavior_upper_bound'], 0)
        self.assertEqual(summary['expected_tasks'], len(grader.bench.tasks()))

    def test_container_decisions_are_invalid_in_both_graders(self):
        task_id = grader.bench.tasks()[0]['task_id']
        for decision in ([], {}):
            records = {task_id: dict(decision=decision, source='pass', explanation='A reason')}
            self.assertFalse(grader.grade(records)[0]['valid_response'])
            self.assertFalse(grader.bench.grade(records)[0]['valid_response'])

    def test_invalid_file_encoding_and_deep_ast_never_confirm_behavior(self):
        task = grader.bench.tasks()[0]
        item = grader.bench.get_family(task)
        for source in ('# coding: not-a-real-codec\n' + item.correct, 'x = ' + '+'.join(['1'] * 3000)):
            records = {task['task_id']: {'source': source, 'decision': task['expected_decision'],
                                         'explanation': 'A response with invalid source.'}}
            with patch.object(grader.bench, 'check', side_effect=AssertionError('Must not execute Python')):
                row = grader.grade(records)[0]
            self.assertFalse(row['behavior_lower'])
            self.assertIsNone(row['ast_variant'])


if __name__ == '__main__':
    unittest.main()
