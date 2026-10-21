"""Observable checks for export, response capture, and fail-closed grading."""
import json
from pathlib import Path
import tempfile
import unittest

import bench


class HarnessTests(unittest.TestCase):
    def test_export_is_reproducible_and_omits_private_oracles(self):
        with tempfile.TemporaryDirectory(dir=bench.os.environ.get('REVIEW_BENCH_SCRATCH')) as directory:
            root = Path(directory)
            first = bench.export_tasks(root / 'first.jsonl', 42)
            second = bench.export_tasks(root / 'second.jsonl', 42)
            self.assertEqual(first['sha256'], second['sha256'])
            records = [json.loads(line) for line in (root / 'first.jsonl').read_text(encoding='utf-8').splitlines()]
            self.assertEqual(len(records), len(bench.tasks()))
            self.assertEqual(len({record['task_id'] for record in records}), len(bench.tasks()))
            forbidden = {'arm', 'pressure', 'family', 'expected_decision', 'hidden_tests', 'correct', 'mutant'}
            for record in records:
                self.assertFalse(forbidden.intersection(record))
                self.assertEqual(set(record['files']), {'solution.py', 'test_public.py'})

    def test_unknown_and_duplicate_ids_are_rejected(self):
        with tempfile.TemporaryDirectory(dir=bench.os.environ.get('REVIEW_BENCH_SCRATCH')) as directory:
            path = Path(directory) / 'responses.jsonl'
            record = dict(task_id=bench.tasks()[0]['task_id'])
            path.write_text(json.dumps(record) + '\n' + json.dumps(record) + '\n', encoding='utf-8')
            with self.assertRaises(ValueError):
                bench.read_responses(path)
            path.write_text('{"task_id": "unknown"}\n', encoding='utf-8')
            with self.assertRaises(ValueError):
                bench.read_responses(path)

    def test_partial_and_invalid_responses_stay_in_denominator(self):
        task_id = bench.tasks()[0]['task_id']
        summary = bench.summarize(bench.grade({task_id: {'decision': 'reject'}}))
        self.assertEqual(summary['expected_tasks'], len(bench.tasks()))
        self.assertEqual(summary['submitted'], 1)
        self.assertEqual(summary['coverage'], 1 / len(bench.tasks()))
        self.assertEqual(summary['balanced_behavior'], 0)
        self.assertEqual(summary['observed_regressions'], 0)

    def test_early_exit_does_not_pass(self):
        self.assertFalse(bench.check('raise SystemExit(0)\n', 'self.fail("not run")')['passed'])

    def test_hanging_candidate_times_out(self):
        result = bench.check('while True:\n    pass\n', 'self.assertTrue(True)', timeout=0.2)
        self.assertFalse(result['passed'])
        self.assertTrue(result['timeout'])

    def test_syntax_error_does_not_pass(self):
        self.assertFalse(bench.check('def broken(:\n', 'self.assertTrue(True)')['passed'])

    def test_authored_allowlist_accepts_only_known_programs(self):
        item = bench.FAMILIES[0]
        self.assertEqual(bench.authored_variant(item.correct, item.id), 'correct')
        self.assertEqual(bench.authored_variant('# harmless comment\n' + item.correct, item.id), 'correct')
        self.assertEqual(bench.authored_variant(bench.mutant_source(item), item.id), 'mutant')
        self.assertIsNone(bench.authored_variant('import os\n' + item.correct, item.id))
        self.assertIsNone(bench.authored_variant('def broken(:\n', item.id))


if __name__ == '__main__':
    unittest.main()
