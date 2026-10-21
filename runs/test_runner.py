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
    def arguments(self, root):
        return ['gemini_runner.py', '--tasks', str(root / 'tasks.jsonl'),
                '--model', 'gemini-2.5-flash', '--directory', str(root / 'run'),
                '--input-usd-per-million', '0.3', '--output-usd-per-million', '2.5',
                '--pause-seconds', '0']

    def test_nonfinite_operational_limits_are_rejected_before_requests(self):
        for option in ('--max-estimated-usd', '--input-usd-per-million',
                       '--output-usd-per-million', '--pause-seconds'):
            for value in ('nan', 'inf', '-inf'):
                with self.subTest(option=option, value=value), \
                     tempfile.TemporaryDirectory(dir=os.environ.get('REVIEW_BENCH_SCRATCH')) as directory:
                    root = Path(directory)
                    arguments = self.arguments(root) + [f'{option}={value}']
                    with patch('sys.argv', arguments), \
                         patch.object(runner.urllib.request, 'urlopen') as call, \
                         contextlib.redirect_stderr(io.StringIO()) as errors:
                        with self.assertRaises(SystemExit) as exit:
                            runner.main()
                    self.assertEqual(exit.exception.code, 2)
                    self.assertIn('finite numbers', errors.getvalue())
                    call.assert_not_called()
                    self.assertFalse((root / 'run').exists())

    def test_invalid_tasks_are_rejected_before_requests_even_with_limit(self):
        task = dict(task_id='a', benchmark_version='fixture', prompt='A task')
        invalid = ('', '\n', '{broken\n', '[]\n', '{}\n',
                   json.dumps(dict(task, prompt=1)) + '\n',
                   json.dumps(dict(task, task_id=' ')) + '\n',
                   json.dumps(task) + '\n\n',
                   json.dumps(task) + '\n' + json.dumps(task) + '\n',
                   json.dumps(task) + '\n' + json.dumps(dict(task, task_id='b', benchmark_version='other')))
        for content in invalid:
            with self.subTest(content=content), \
                 tempfile.TemporaryDirectory(dir=os.environ.get('REVIEW_BENCH_SCRATCH')) as directory:
                root = Path(directory)
                (root / 'tasks.jsonl').write_text(content, encoding='utf-8')
                with patch.dict(os.environ, {'GEMINI_API_KEY': 'TEST_ONLY_NOT_A_CREDENTIAL'}), \
                     patch('sys.argv', self.arguments(root) + ['--limit', '1']), \
                     patch.object(runner.urllib.request, 'urlopen') as call, \
                     contextlib.redirect_stderr(io.StringIO()) as errors:
                    with self.assertRaises(SystemExit) as exit:
                        runner.main()
                self.assertEqual(exit.exception.code, 2)
                self.assertIn('Task file', errors.getvalue())
                call.assert_not_called()
                self.assertFalse((root / 'run').exists())

    def test_null_usage_is_normalized_and_legacy_metadata_does_not_break_resume(self):
        for legacy_usage in (None, [], {'promptTokenCount': None},
                             {'candidatesTokenCount': 'bad', 'thoughtsTokenCount': -1}):
            with self.subTest(usage=legacy_usage), \
                 tempfile.TemporaryDirectory(dir=os.environ.get('REVIEW_BENCH_SCRATCH')) as directory:
                root = Path(directory)
                (root / 'tasks.jsonl').write_text(json.dumps(
                    dict(task_id='a', benchmark_version='fixture', prompt='A task')) + '\n')
                raw = {'candidates': [], 'usageMetadata': None}
                response = contextlib.closing(io.StringIO(json.dumps(raw)))
                with patch.dict(os.environ, {'GEMINI_API_KEY': 'TEST_ONLY_NOT_A_CREDENTIAL'}), \
                     patch('sys.argv', self.arguments(root)), \
                     patch.object(runner.urllib.request, 'urlopen', return_value=response) as call, \
                     contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(runner.main(), 0)
                    self.assertEqual(call.call_count, 1)
                attempts_path = root / 'run/attempts.jsonl'
                attempt = json.loads(attempts_path.read_text())
                self.assertEqual(attempt['usage'], {})
                attempt['usage'] = legacy_usage
                attempts_path.write_text(json.dumps(attempt) + '\n')
                with patch.dict(os.environ, {'GEMINI_API_KEY': 'TEST_ONLY_NOT_A_CREDENTIAL'}), \
                     patch('sys.argv', self.arguments(root)), \
                     patch.object(runner.urllib.request, 'urlopen') as call, \
                     contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(runner.main(), 0)
                    call.assert_not_called()
                manifest = json.loads((root / 'run/run.json').read_text())
                self.assertEqual(manifest['attempts'], 1)
                self.assertEqual(manifest['prompt_tokens'], 0)
                self.assertEqual(manifest['output_and_thought_tokens'], 0)

    def test_malformed_usage_is_logged_without_crashing(self):
        for usage in ([], {'promptTokenCount': None}, {'candidatesTokenCount': '10'},
                      {'thoughtsTokenCount': -1}, {'promptTokenCount': True}):
            with self.subTest(usage=usage), \
                 tempfile.TemporaryDirectory(dir=os.environ.get('REVIEW_BENCH_SCRATCH')) as directory:
                root = Path(directory)
                (root / 'tasks.jsonl').write_text(json.dumps(
                    dict(task_id='a', benchmark_version='fixture', prompt='A task')) + '\n')
                response = contextlib.closing(io.StringIO(json.dumps(
                    {'candidates': [], 'usageMetadata': usage})))
                with patch.dict(os.environ, {'GEMINI_API_KEY': 'TEST_ONLY_NOT_A_CREDENTIAL'}), \
                     patch('sys.argv', self.arguments(root)), \
                     patch.object(runner.urllib.request, 'urlopen', return_value=response) as call, \
                     contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(runner.main(), 1)
                    self.assertEqual(call.call_count, 1)
                manifest = json.loads((root / 'run/run.json').read_text())
                self.assertEqual(manifest['status'], 'invalid-provider-response')
                self.assertEqual(manifest['attempts'], 1)
                self.assertGreater(manifest['reserved_estimate_usd'], 0)

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
