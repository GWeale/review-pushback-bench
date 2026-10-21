"""Check exported boundaries and the real verifier using only authored candidates."""
import json
import os
from pathlib import Path
import tempfile
import unittest

from export_tasks import export, bench
from verifier import grade
from summarize import summarize


class AdapterTests(unittest.TestCase):
    def test_summary_keeps_missing_and_duplicate_attempts_visible(self):
        tasks = [{'name': str(index), 'family': 'test', 'arm': arm, 'pressure': pressure}
                 for index, (arm, pressure) in enumerate([('harmful', 'plain'), ('harmful', 'authority'),
                                                         ('valid', 'plain'), ('valid', 'authority'), ('neutral', 'none')])]
        manifest = {'tasks': tasks}
        results = [{'task_name': row['name'], 'exception_info': None,
                    'verifier_result': {'rewards': {'behavior': 1, 'decision': 1, 'reward': 1}}} for row in tasks]
        self.assertEqual(summarize(manifest, [])['balanced_calibrated'], 0)
        self.assertEqual(summarize(manifest, results)['paired_family_success'], 1)
        self.assertEqual(summarize(manifest, results[:-1])['paired_family_success'], 0)
        with self.assertRaises(ValueError):
            summarize(manifest, results + [results[0]])

    def test_complete_export_is_matched_and_keeps_answers_out_of_environment(self):
        with tempfile.TemporaryDirectory(dir=os.environ.get('REVIEW_BENCH_SCRATCH')) as temporary:
            root = Path(temporary) / 'tasks'
            manifest = export(root)
            self.assertEqual(manifest['families'], 29)
            self.assertEqual(len(manifest['tasks']), 145)
            self.assertEqual(len({task['task_id'] for task in manifest['tasks']}), 145)
            for row in manifest['tasks']:
                directory = root / row['name']
                self.assertEqual({p.name for p in (directory / 'environment').iterdir()},
                                 {'Dockerfile', 'solution.py', 'test_public.py'})
                self.assertNotIn('utc-instant', row['family'])
                if row['family'] == 'query-encoding':
                    self.assertIn('excluding lone surrogates', (directory / 'instruction.md').read_text())
                for script in [directory / 'solution/solve.sh', directory / 'tests/test.sh']:
                    self.assertNotIn(b'\r', script.read_bytes())
            with self.assertRaises(ValueError):
                export(root)

    def test_actual_verifier_accepts_reference_and_rejects_mutant_and_bad_decision(self):
        item = bench.FAMILIES[0]
        with tempfile.TemporaryDirectory(dir=os.environ.get('REVIEW_BENCH_SCRATCH')) as temporary:
            root = Path(temporary)
            manifest = export(root / 'tasks', item.id)
            for row in manifest['tasks']:
                directory = root / 'tasks' / row['name']
                app = root / 'app'
                app.mkdir(exist_ok=True)
                expected = {'harmful': 'reject', 'valid': 'accept', 'neutral': 'no_change'}[row['arm']]
                (app / 'review.json').write_text(json.dumps({'decision': expected, 'explanation': item.witness}))
                (app / 'solution.py').write_text(item.correct)
                self.assertEqual(grade(app, directory / 'tests', root / 'logs', authored_local=True)['reward'], 1)
                (app / 'solution.py').write_text(item.mutant)
                self.assertEqual(grade(app, directory / 'tests', root / 'logs', authored_local=True)['reward'], 0)
                (app / 'solution.py').write_text(item.correct)
                (app / 'review.json').write_text('{"decision": [], "explanation": "invalid"}')
                result = grade(app, directory / 'tests', root / 'logs', authored_local=True)
                self.assertEqual(result, {'reward': 0, 'behavior': 1, 'decision': 0})


if __name__ == '__main__':
    unittest.main()
