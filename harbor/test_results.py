"""Exercise malformed result handling and smoke-trial identity checks."""
import json
import os
from pathlib import Path
import tempfile
import unittest

from check_smoke import check
from summarize import summarize


TASKS = [{'name': str(index), 'family': 'test', 'arm': arm, 'pressure': pressure}
         for index, (arm, pressure) in enumerate([('harmful', 'plain'), ('harmful', 'authority'),
                                                 ('valid', 'plain'), ('valid', 'authority'), ('neutral', 'none')])]


def trial(name, reward=1):
    return {'task_name': 'review-pushback/' + name, 'exception_info': None,
            'verifier_environment_mode': 'separate',
            'verifier_result': {'rewards': {'behavior': reward, 'decision': reward, 'reward': reward}}}


class ResultTests(unittest.TestCase):
    def test_malformed_rewards_cannot_score(self):
        malformed = [None, [], {'reward': 1}, {'behavior': 1, 'decision': 0, 'reward': 1},
                     {'behavior': True, 'decision': 1, 'reward': 1},
                     {'behavior': 1, 'decision': 1, 'reward': '1'},
                     {'behavior': 1, 'decision': 1, 'reward': float('nan')}]
        for payload in malformed:
            with self.subTest(payload=payload):
                results = [trial(task['name']) for task in TASKS]
                for result in results:
                    result['verifier_result']['rewards'] = payload
                summary = summarize({'tasks': TASKS}, results)
                self.assertEqual(summary['valid_results'], 0)
                self.assertEqual(summary['balanced_calibrated'], 0)
                self.assertEqual(summary['paired_family_success'], 0)
        for verifier in ([], 1, 'invalid'):
            result = trial('0')
            result['verifier_result'] = verifier
            self.assertEqual(summarize({'tasks': TASKS}, [result])['valid_results'], 0)

    def test_smoke_requires_each_expected_task_once(self):
        with tempfile.TemporaryDirectory(dir=os.environ.get('REVIEW_BENCH_SCRATCH')) as temporary:
            root = Path(temporary)
            tasks = root / 'tasks'
            tasks.mkdir()
            (tasks / 'manifest.json').write_text(json.dumps({'tasks': TASKS}))
            for agent, reward in [('oracle', 1), ('nop', 0)]:
                for index, task in enumerate(TASKS):
                    directory = root / 'jobs' / agent / str(index)
                    directory.mkdir(parents=True)
                    (directory / 'result.json').write_text(json.dumps(trial(task['name'], reward)))
            self.assertTrue(check(root / 'jobs', tasks)['oracle']['all_passed'])
            duplicate = root / 'jobs/oracle/4/result.json'
            duplicate.write_text(json.dumps(trial('0')))
            with self.assertRaises(ValueError):
                check(root / 'jobs', tasks)


if __name__ == '__main__':
    unittest.main()
