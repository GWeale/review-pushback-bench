"""Check versioned contract corrections without rewriting historical fixtures."""
import ast
import unittest

from export_tasks import adapt_family, bench


class DomainTests(unittest.TestCase):
    def test_escaped_json_key_reaches_the_decoder_unchanged(self):
        original = next(item for item in bench.FAMILIES if item.id == 'json-duplicate-keys')
        corrected = adapt_family(original)
        tree = ast.parse(bench.test_file(corrected.hidden_tests))
        strings = [node.value for node in ast.walk(tree) if isinstance(node, ast.Constant) and isinstance(node.value, str)]
        self.assertIn('{"a": 1, "\\u0061": 2}', strings)
        self.assertNotEqual(corrected.hidden_tests, original.hidden_tests)

    def test_domain_corrections_are_confined_to_the_harbor_edition(self):
        restrictions = {'sql-values': 'TEXT COLLATE BINARY',
                        'numeric-release-versions': '1 to 100 ASCII digits',
                        'query-encoding': 'excluding lone surrogates'}
        for family_id, restriction in restrictions.items():
            item = next(item for item in bench.FAMILIES if item.id == family_id)
            corrected = adapt_family(item)
            self.assertIn(restriction, corrected.contract)
            self.assertNotIn(restriction, item.contract)
            self.assertEqual(corrected.correct, item.correct)


if __name__ == '__main__':
    unittest.main()
