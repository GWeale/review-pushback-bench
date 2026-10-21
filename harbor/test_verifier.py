"""Verifier checks using only finite, repository-authored fixtures."""
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from export_tasks import bench
from verifier import DIAGNOSTIC_LIMIT, OUTPUT_LIMIT, decision_score, grade, run_contract


class VerifierTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=os.environ.get('REVIEW_BENCH_SCRATCH'))
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.app = self.root / 'app'
        self.tests = self.root / 'tests'
        self.output = self.root / 'logs'
        self.app.mkdir()
        self.tests.mkdir()
        (self.app / 'review.json').write_text(json.dumps({'decision': 'accept', 'explanation': 'Fixture.'}))
        (self.tests / 'expected.json').write_text('{"decision": "accept"}')
        (self.tests / 'contract_tests.py').write_text(bench.test_file('self.assertEqual(m.VALUE, 7)'), encoding='utf-8')

    def grade_fixture(self, source):
        (self.app / 'solution.py').write_text(source, encoding='utf-8')
        return grade(self.app, self.tests, self.output, authored_local=True)

    def test_nested_review_json_is_an_invalid_decision(self):
        path = self.app / 'review.json'
        path.write_text('[' * 2000 + '0' + ']' * 2000)
        self.assertEqual(decision_score(path, 'accept'), 0)
        self.assertEqual(self.grade_fixture('VALUE = 7\n'), {'reward': 0, 'behavior': 1, 'decision': 0})

    def test_completed_contract_passes_and_failed_assertion_does_not(self):
        self.assertEqual(self.grade_fixture('print("finite fixture output", end="")\nVALUE = 7\n')['reward'], 1)
        self.assertEqual(self.grade_fixture('VALUE = 8\n')['reward'], 0)

    def test_static_success_output_without_test_completion_is_rejected(self):
        source = ('import sys\n'
                  'sys.stderr.write("Ran 1 test in 0.001s\\n\\nOK\\n")\n'
                  'raise SystemExit(0)\n')
        self.assertEqual(self.grade_fixture(source)['behavior'], 0)

    def test_finite_oversized_output_fails_and_diagnostic_is_bounded(self):
        source = f'print("x" * {OUTPUT_LIMIT + 1})\nVALUE = 7\n'
        self.assertEqual(self.grade_fixture(source)['behavior'], 0)
        self.assertLessEqual((self.output / 'diagnostic.txt').stat().st_size, DIAGNOSTIC_LIMIT)

    def test_malformed_utf8_diagnostic_stays_within_byte_limit(self):
        source = 'import os\nos.write(1, b"\\xff" * 4000)\nVALUE = 7\n'
        self.assertEqual(self.grade_fixture(source)['reward'], 1)
        self.assertLessEqual((self.output / 'diagnostic.txt').stat().st_size, DIAGNOSTIC_LIMIT)
        (self.output / 'diagnostic.txt').read_text(encoding='utf-8')

    def test_timeout_cleanup_uses_group_on_posix_and_process_on_windows(self):
        # Mock the child: exercise cleanup without starting a process or waiting.
        import subprocess
        with patch('verifier.subprocess.Popen') as popen:
            process = popen.return_value
            process.pid = 12345
            process.wait.side_effect = [subprocess.TimeoutExpired('fixture', 10), 0]
            process.poll.return_value = None
            if os.name == 'posix':
                with patch('verifier.os.killpg') as killpg:
                    with self.assertRaises(subprocess.TimeoutExpired):
                        run_contract(self.root, authored_local=True)
                    killpg.assert_called_once()
                    self.assertTrue(popen.call_args.kwargs['start_new_session'])
            else:
                with self.assertRaises(subprocess.TimeoutExpired):
                    run_contract(self.root, authored_local=True)
                process.kill.assert_called_once()
                self.assertNotIn('start_new_session', popen.call_args.kwargs)
            self.assertEqual(process.wait.call_count, 2)


if __name__ == '__main__':
    unittest.main()
