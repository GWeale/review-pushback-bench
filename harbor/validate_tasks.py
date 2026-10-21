"""Validate exported task hashes, Harbor's schema, and authored reference behavior."""
import argparse
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import sys
import tomllib

from export_tasks import bench


def validate(root, require_harbor=False):
    manifest = json.loads((root / 'manifest.json').read_text())
    for relative, expected in manifest['files_sha256'].items():
        assert hashlib.sha256((root / relative).read_bytes()).hexdigest() == expected, relative
    loaded = 0
    if require_harbor:
        from harbor.models.task.task import Task
        harbor_version = version('harbor')
    else:
        harbor_version = None
    families = set()
    for row in manifest['tasks']:
        directory = root / row['name']
        config = tomllib.loads((directory / 'task.toml').read_text())
        assert config['verifier']['environment_mode'] == 'separate'
        assert config['verifier']['environment']['network_mode'] == 'no-network'
        assert config['artifacts'] == ['/app/solution.py', '/app/review.json']
        if require_harbor:
            task = Task(directory)
            assert task.config.verifier.environment_mode.value == 'separate'
            loaded += 1
        families.add(row['family'])
    # Execute only repository-authored source, never submitted candidate files.
    for family_id in sorted(families):
        item = next(item for item in bench.FAMILIES if item.id == family_id)
        body = item.public_tests + '\n' + item.hidden_tests
        assert bench.check(item.correct, body)['passed'], family_id
        mutant = bench.check(item.mutant, body)
        assert not mutant['passed'] and mutant['returncode'] == 1 and not mutant['timeout'], family_id
    return {'passed': True, 'tasks': len(manifest['tasks']), 'families': len(families),
            'harbor_version': harbor_version, 'harbor_tasks_loaded': loaded,
            'authored_correct_and_mutant_checks': len(families) * 2,
            'python': sys.version.split()[0], 'candidate_python_executed': False,
            'note': 'Schema and authored checks only. Docker trials are a separate CI check.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tasks', type=Path, required=True)
    parser.add_argument('--require-harbor', action='store_true')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = validate(args.tasks, args.require_harbor)
    if args.output:
        args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps(result, indent=2))
