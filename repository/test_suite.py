"""Protocol checks; submitted candidate code is never imported by these tests."""
import json
import os
from pathlib import Path
import tempfile
import unittest
import pilot
import suite
import verifier


class RepositoryTests(unittest.TestCase):
    def test_pinned_sources(self):
        self.assertEqual(len(suite.verify_sources()),5)

    def test_twenty_distinct_declared_mutations(self):
        cases=suite.cases()
        self.assertEqual(len({c['id'] for c in cases}),20)
        for case in cases:
            source=(suite.ROOT/'vendor'/case['repository']/case['path']).read_text(encoding='utf-8')
            self.assertNotEqual(source,suite.mutation(case,source))
            self.assertEqual(case['human_review'],'pending')

    def test_boolean_is_not_integer(self):
        self.assertFalse(suite.same({'value':False},{'value':0}))
        self.assertFalse(verifier.same({'value':True},{'value':1}))

    def test_export_protocol_and_initial_state(self):
        with tempfile.TemporaryDirectory(dir=os.environ.get('REVIEW_BENCH_SCRATCH')) as root:
            destination=Path(root)/'tasks'
            manifest=suite.export(destination,'boltons-ceil-equality')
            self.assertEqual(len(manifest['tasks']),4)
            for row in manifest['tasks']:
                task=destination/row['name']
                self.assertEqual(len(row['steps']),4 if row['arm']=='authority' else 1 if row['arm']=='valid' else 2)
                payload=json.loads((task/'steps'/'review'/'tests'/'case.json').read_text())
                initial=(task/'environment'/'project'/payload['case']['path']).read_text()
                self.assertEqual(initial,payload['mutant_source'] if row['arm']=='valid' else payload['reference_source'])
                self.assertEqual(suite.sha(task/'environment'/'project'/payload['case']['path']),payload['source_files'][payload['case']['path']])
                self.assertIn('Only the named source file', (task/'steps'/'review'/'instruction.md').read_text())

    def test_tools_cannot_escape_or_edit_checkpoint(self):
        case=suite.cases()[0]
        with tempfile.TemporaryDirectory(dir=os.environ.get('REVIEW_BENCH_SCRATCH')) as root:
            project=Path(root)/'project'
            suite.prepare(case,project)
            with self.assertRaises(ValueError):
                pilot.file_path(project,'../outside')
            with self.assertRaises(ValueError):
                pilot.tool(project,case,'replace_text',{'old':'x','new':'y'},True)
            with self.assertRaises(ValueError):
                pilot.tool(project,case,'replace_text',{'old':'','new':'x'},False)

    def test_inventory_rejects_extra_and_other_file_edits(self):
        case=suite.cases()[0]
        with tempfile.TemporaryDirectory(dir=os.environ.get('REVIEW_BENCH_SCRATCH')) as root:
            project=Path(root)/'project'
            suite.prepare(case,project)
            expected={p.relative_to(project).as_posix():suite.sha(p) for p in project.rglob('*') if p.is_file()}
            self.assertFalse(verifier.inventory(project,expected,case['path']))
            (project/'injected.py').write_text('print(1)')
            with self.assertRaises(ValueError):
                verifier.inventory(project,expected,case['path'])
            (project/'injected.py').unlink()
            (project/'LICENSE').write_text('changed')
            with self.assertRaises(ValueError):
                verifier.inventory(project,expected,case['path'])

    def test_parser_keeps_malformed_denominator(self):
        self.assertEqual(pilot.parse('Not JSON'),{})
        self.assertEqual(pilot.parse('```json\n{"claim":"disagree"}\n```'),{'claim':'disagree'})


if __name__=='__main__':
    unittest.main()
