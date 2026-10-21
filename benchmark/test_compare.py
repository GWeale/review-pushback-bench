"""Reject artifacts whose row labels contradict their task identities."""
import json
import os
from pathlib import Path
import tempfile
import unittest

import bench
import compare


class ComparisonTests(unittest.TestCase):
    def test_tampered_row_metadata_cannot_raise_comparison_score(self):
        rows = [{key: task[key] for key in ('task_id', 'family', 'arm', 'pressure')}
                | {'calibrated_pass': task['arm'] != 'valid'} for task in bench.tasks()]
        run = {'model_label': 'fixture', 'responses_sha256': 'fixture', 'rows': rows,
               'summary': {'version': bench.VERSION, 'calibrated_balance': .5, 'coverage': 1}}
        with tempfile.TemporaryDirectory(dir=os.environ.get('REVIEW_BENCH_SCRATCH')) as temporary:
            path = Path(temporary) / 'run.json'
            path.write_text(json.dumps(run))
            self.assertEqual(compare.compare([path])['models'][0]['calibrated_balance'], .5)
            for row in rows:
                if row['arm'] == 'valid':
                    row['arm'] = 'neutral'
            path.write_text(json.dumps(run))
            with self.assertRaises(ValueError):
                compare.compare([path])


if __name__ == '__main__':
    unittest.main()
