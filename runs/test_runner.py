import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import gemini_runner as runner


class RunnerTests(unittest.TestCase):
    def test_parse_rejects_wrong_task_and_decision(self):
        record = dict(task_id='a', decision='reject', explanation='Reason', source='pass\n')
        self.assertEqual(runner.parse_record(json.dumps(record), 'a'), record)
        with self.assertRaises(ValueError):
            runner.parse_record(json.dumps(record), 'b')
        record['decision'] = 'maybe'
        with self.assertRaises(ValueError):
            runner.parse_record(json.dumps(record), 'a')
        for value in ([], {}):
            record['decision'] = value
            with self.assertRaises(ValueError):
                runner.parse_record(json.dumps(record), 'a')

    def test_missing_candidates_are_logged_and_resume_does_not_call_again(self):
        with tempfile.TemporaryDirectory(dir=os.environ.get('REVIEW_BENCH_SCRATCH')) as directory:
            root = Path(directory)
            tasks = root / 'tasks.jsonl'
            tasks.write_text(json.dumps(dict(task_id='a', benchmark_version='fixture', prompt='A task')) + '\n')
            arguments = ['gemini_runner.py', '--tasks', str(tasks), '--model', 'gemini-2.5-flash',
                         '--directory', str(root / 'run'), '--input-usd-per-million', '0.3',
                         '--output-usd-per-million', '2.5', '--pause-seconds', '0']
            response = contextlib.closing(io.StringIO(json.dumps({'candidates': [], 'usageMetadata': {}})))
            with patch.dict(os.environ, {'GEMINI_API_KEY': 'TEST_ONLY_NOT_A_CREDENTIAL'}), \
                 patch('sys.argv', arguments), patch.object(runner.urllib.request, 'urlopen', return_value=response) as call, \
                 contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(runner.main(), 0)
                self.assertEqual(call.call_count, 1)
            manifest = json.loads((root / 'run/run.json').read_text())
            self.assertEqual(manifest['attempts'], 1)
            self.assertEqual(manifest['valid_responses'], 0)
            with patch.dict(os.environ, {'GEMINI_API_KEY': 'TEST_ONLY_NOT_A_CREDENTIAL'}), \
                 patch('sys.argv', arguments), patch.object(runner.urllib.request, 'urlopen') as call, \
                 contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(runner.main(), 0)
                call.assert_not_called()

    def test_response_file_rebuilt_from_attempts_without_duplicates(self):
        with tempfile.TemporaryDirectory(dir=os.environ.get('REVIEW_BENCH_SCRATCH')) as directory:
            path = Path(directory) / 'responses.jsonl'
            records = [{'parsed_response': {'task_id': 'a'}}, {'parse_valid': False}]
            runner.save_responses(path, records)
            runner.save_responses(path, records)
            self.assertEqual(path.read_text(), '{"task_id": "a"}\n')

    def test_malformed_provider_json_is_a_logged_reserved_attempt(self):
        with tempfile.TemporaryDirectory(dir=os.environ.get('REVIEW_BENCH_SCRATCH')) as directory:
            root = Path(directory)
            tasks = root / 'tasks.jsonl'
            tasks.write_text(json.dumps(dict(task_id='a', benchmark_version='fixture', prompt='A task')) + '\n')
            arguments = ['gemini_runner.py', '--tasks', str(tasks), '--model', 'gemini-2.5-flash',
                         '--directory', str(root / 'run'), '--input-usd-per-million', '0.3',
                         '--output-usd-per-million', '2.5', '--pause-seconds', '0']
            response = contextlib.closing(io.StringIO('{truncated'))
            with patch.dict(os.environ, {'GEMINI_API_KEY': 'TEST_ONLY_NOT_A_CREDENTIAL'}), \
                 patch('sys.argv', arguments), patch.object(runner.urllib.request, 'urlopen', return_value=response), \
                 contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(runner.main(), 1)
            manifest = json.loads((root / 'run/run.json').read_text())
            self.assertEqual(manifest['attempts'], 1)
            self.assertEqual(manifest['status'], 'invalid-provider-response')
            self.assertGreater(manifest['reserved_estimate_usd'], 0)


if __name__ == '__main__':
    unittest.main()
