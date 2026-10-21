"""Data-only validation regressions; never execute exported or candidate Python."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import export_tasks
from validate_tasks import validate


class ValidationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=os.environ.get('REVIEW_BENCH_SCRATCH'))
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name) / 'tasks'
        self.manifest = export_tasks.export(self.root, 'page-boundary')
        self.row = self.manifest['tasks'][0]
        self.check = patch.object(export_tasks.bench, 'check')
        self.mock_check = self.check.start()
        self.addCleanup(self.check.stop)
        self.mock_check.side_effect = [self.result(True), self.result(False)]

    @staticmethod
    def result(passed):
        return {'passed': passed, 'returncode': 0 if passed else 1, 'timeout': False}

    def save_manifest(self):
        (self.root / 'manifest.json').write_text(json.dumps(self.manifest), encoding='utf-8')

    def replace_file(self, relative, body):
        path = self.root / relative
        path.write_text(body, encoding='utf-8', newline='\n')
        self.manifest['files_sha256'][relative] = hashlib.sha256(path.read_bytes()).hexdigest()
        self.save_manifest()

    def test_valid_subset_checks_adapted_family_and_counts_both_checks(self):
        result = validate(self.root)
        self.assertEqual((result['tasks'], result['families'], result['authored_correct_and_mutant_checks']),
                         (5, 1, 2))
        item = export_tasks.adapt_family(export_tasks.bench.get_family(self.row))
        body = item.public_tests + '\n' + item.hidden_tests
        self.assertEqual(self.mock_check.call_args_list,
                         [unittest.mock.call(item.correct, body), unittest.mock.call(item.mutant, body)])

    def test_complete_export_uses_every_adapted_family(self):
        root = Path(self.temporary.name) / 'all-tasks'
        manifest = export_tasks.export(root)
        families = sorted({row['family'] for row in manifest['tasks']})
        self.mock_check.side_effect = [self.result(True), self.result(False)] * len(families)
        result = validate(root)
        self.assertEqual((result['tasks'], result['families']), (145, 29))
        expected = []
        for family_id in families:
            item = export_tasks.adapt_family(next(item for item in export_tasks.bench.FAMILIES
                                                  if item.id == family_id))
            body = item.public_tests + '\n' + item.hidden_tests
            expected.extend([unittest.mock.call(item.correct, body), unittest.mock.call(item.mutant, body)])
        self.assertEqual(self.mock_check.call_args_list, expected)
        self.assertEqual(result['authored_correct_and_mutant_checks'], len(expected))

    def test_rejects_empty_cohort(self):
        self.manifest['tasks'] = []
        self.save_manifest()
        with self.assertRaisesRegex(ValueError, 'nonempty task cohort'):
            validate(self.root)

    def test_rejects_missing_variant(self):
        self.manifest['tasks'].pop()
        self.save_manifest()
        with self.assertRaisesRegex(ValueError, 'every matched variant'):
            validate(self.root)

    def test_rejects_duplicate_and_relabelled_rows(self):
        original = json.loads(json.dumps(self.manifest))
        for mutation in ('duplicate', 'task_id', 'family', 'arm', 'pressure', 'name'):
            with self.subTest(mutation=mutation):
                self.manifest = json.loads(json.dumps(original))
                if mutation == 'duplicate':
                    self.manifest['tasks'].append(self.manifest['tasks'][0])
                else:
                    self.manifest['tasks'][0][mutation] = 'wrong'
                self.save_manifest()
                with self.assertRaises(ValueError):
                    validate(self.root)
        self.mock_check.assert_not_called()

    def test_rejects_incorrect_versions_and_family_count(self):
        for key in ('adapter_version', 'source_benchmark_version', 'families'):
            with self.subTest(key=key):
                original = self.manifest[key]
                self.manifest[key] = 'wrong'
                self.save_manifest()
                with self.assertRaises(ValueError):
                    validate(self.root)
                self.manifest[key] = original

    def test_rejects_unlisted_changed_tests(self):
        relative = self.row['name'] + '/tests/contract_tests.py'
        (self.root / relative).write_text('# no tests\n', encoding='utf-8')
        del self.manifest['files_sha256'][relative]
        self.save_manifest()
        with self.assertRaisesRegex(ValueError, 'inventory'):
            validate(self.root)

    def test_rejects_extra_file_and_missing_file(self):
        extra = self.root / self.row['name'] / 'environment/extra.txt'
        extra.write_text('fixture', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'inventory'):
            validate(self.root)
        extra.unlink()
        (self.root / self.row['name'] / 'tests/expected.json').unlink()
        with self.assertRaisesRegex(ValueError, 'inventory'):
            validate(self.root)

    def test_rejects_empty_inventory_and_escaping_or_noncanonical_paths(self):
        original = self.manifest['files_sha256']
        for relative in (None, '../outside', '/absolute', 'C:/outside', '..\\outside',
                         self.row['name'] + '//task.toml'):
            with self.subTest(relative=relative):
                self.manifest['files_sha256'] = {} if relative is None else {relative: '0' * 64}
                self.save_manifest()
                with self.assertRaises(ValueError):
                    validate(self.root)
        self.manifest['files_sha256'] = original
        self.mock_check.assert_not_called()

    def test_rejects_symlinked_task_file(self):
        target = Path(self.temporary.name) / 'outside.txt'
        target.write_text('authored fixture', encoding='utf-8')
        link = self.root / self.row['name'] / 'environment/linked.txt'
        try:
            link.symlink_to(target)
        except OSError as error:
            self.skipTest('Creating symlinks is unavailable: ' + str(error))
        with self.assertRaisesRegex(ValueError, 'escapes|symbolic links'):
            validate(self.root)
        self.mock_check.assert_not_called()

    def test_rejects_duplicate_inventory_keys_before_parsing_loses_them(self):
        path = self.root / 'manifest.json'
        text = path.read_text(encoding='utf-8')
        path.write_text(text[:-2] + ', "files_sha256": {}}', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'Duplicate JSON key'):
            validate(self.root)

    def test_rejects_rehashed_toml_mismatches(self):
        relative = self.row['name'] + '/task.toml'
        original = (self.root / relative).read_text(encoding='utf-8')
        replacements = [('review-pushback/', 'different/'),
                        ('version = "' + export_tasks.VERSION + '"', 'version = "wrong"'),
                        ('family = "page-boundary"', 'family = "wrong"'),
                        ('arm = "harmful"', 'arm = "neutral"'),
                        ('pressure = "plain"', 'pressure = "none"'),
                        ('environment_mode = "separate"', 'environment_mode = "same"'),
                        ('network_mode = "no-network"', 'network_mode = "bridge"'),
                        ('"/app/review.json"', '"/app/other.json"')]
        for old, new in replacements:
            with self.subTest(old=old):
                self.assertIn(old, original)
                self.replace_file(relative, original.replace(old, new))
                with self.assertRaises(ValueError):
                    validate(self.root)
        self.mock_check.assert_not_called()

    def test_rejects_rehashed_test_and_decision_mismatches(self):
        for suffix, replacement in [('environment/test_public.py', '# no public tests\n'),
                                    ('tests/contract_tests.py', '# no contract tests\n'),
                                    ('tests/expected.json', '{"decision":"accept"}')]:
            with self.subTest(file=suffix):
                relative = self.row['name'] + '/' + suffix
                original = (self.root / relative).read_text(encoding='utf-8')
                self.replace_file(relative, replacement)
                with self.assertRaises(ValueError):
                    validate(self.root)
                self.replace_file(relative, original)
        self.mock_check.assert_not_called()

    def test_authored_reference_failures_are_explicit(self):
        self.mock_check.side_effect = [self.result(False)]
        with self.assertRaisesRegex(ValueError, 'correct solution failed'):
            validate(self.root)
        self.mock_check.side_effect = [self.result(True), self.result(True)]
        with self.assertRaisesRegex(ValueError, 'mutant did not fail cleanly'):
            validate(self.root)

    def test_optimized_python_rejects_bad_hash_without_executing_source(self):
        relative = self.row['name'] + '/instruction.md'
        self.manifest['files_sha256'][relative] = '0' * 64
        self.save_manifest()
        result = subprocess.run([sys.executable, '-O', str(Path(__file__).with_name('validate_tasks.py')),
                                 '--tasks', str(self.root)], capture_output=True, text=True, timeout=15)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('File hash mismatch', result.stderr)
        self.mock_check.assert_not_called()


if __name__ == '__main__':
    unittest.main()
