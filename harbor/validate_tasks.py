"""Validate exported task hashes, Harbor's schema, and authored reference behavior."""
import argparse
import hashlib
from importlib.metadata import version
import json
from pathlib import Path, PurePosixPath
import sys
import tomllib

import export_tasks

bench = export_tasks.bench
TASK_FILES = ('instruction.md', 'task.toml', 'environment/Dockerfile',
              'environment/solution.py', 'environment/test_public.py',
              'tests/Dockerfile', 'tests/test.sh', 'tests/verifier.py',
              'tests/expected.json', 'tests/contract_tests.py', 'solution/solve.sh')


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON key: ' + key)
        result[key] = value
    return result


def contained_file(root, relative):
    if not isinstance(relative, str):
        raise ValueError('File paths must be strings.')
    path = PurePosixPath(relative)
    if (not relative or '\\' in relative or ':' in relative or path.is_absolute()
            or '..' in path.parts or path.as_posix() != relative):
        raise ValueError('Invalid export-relative path: ' + relative)
    target = root / relative
    if not target.resolve().is_relative_to(root):
        raise ValueError('File escapes the export directory: ' + relative)
    if any(parent.is_symlink() for parent in [target, *target.parents]
           if parent != root and parent.is_relative_to(root)):
        raise ValueError('Export paths must not contain symbolic links: ' + relative)
    return target


def validate(root, require_harbor=False):
    root = Path(root).resolve()
    manifest = json.loads(contained_file(root, 'manifest.json').read_text(encoding='utf-8'),
                          object_pairs_hook=unique_object)
    if (manifest.get('adapter_version') != export_tasks.VERSION
            or manifest.get('source_benchmark_version') != bench.VERSION):
        raise ValueError('Manifest versions do not match this adapter and benchmark.')
    rows = manifest.get('tasks')
    if not isinstance(rows, list) or not rows:
        raise ValueError('The manifest must contain a nonempty task cohort.')
    canonical = {'rpb-' + task['task_id']: task for task in bench.tasks()
                 if task['family'] not in export_tasks.EXCLUDED}
    names = set()
    families = set()
    for row in rows:
        if not isinstance(row, dict) or not isinstance(row.get('name'), str):
            raise ValueError('Invalid manifest task row.')
        task = canonical.get(row['name'])
        if task is None:
            raise ValueError('Unknown task name: ' + row['name'])
        expected_row = {key: task[key] for key in ('task_id', 'family', 'arm', 'pressure')}
        expected_row['name'] = row['name']
        if row != expected_row or row['name'] in names:
            raise ValueError('Duplicate or inconsistent task row: ' + row['name'])
        names.add(row['name'])
        families.add(row['family'])
    expected_names = {name for name, task in canonical.items() if task['family'] in families}
    if names != expected_names or manifest.get('families') != len(families):
        raise ValueError('The manifest must contain every matched variant of each family.')
    hashes = manifest.get('files_sha256')
    if not isinstance(hashes, dict) or not hashes:
        raise ValueError('The manifest must contain a nonempty file inventory.')
    for relative in hashes:
        contained_file(root, relative)
    expected_files = {name + '/' + filename for name in names for filename in TASK_FILES}
    actual_files = set()
    for path in root.rglob('*'):
        relative = path.relative_to(root).as_posix()
        contained_file(root, relative)
        if path.is_file() and relative != 'manifest.json':
            actual_files.add(relative)
    if set(hashes) != expected_files or actual_files != expected_files:
        raise ValueError('Task files, manifest inventory, and matched cohort differ.')
    for relative, expected in hashes.items():
        if hashlib.sha256((root / relative).read_bytes()).hexdigest() != expected:
            raise ValueError('File hash mismatch: ' + relative)
    loaded = 0
    if require_harbor:
        from harbor.models.task.task import Task
        harbor_version = version('harbor')
    else:
        harbor_version = None
    for row in rows:
        directory = root / row['name']
        config = tomllib.loads((directory / 'task.toml').read_text(encoding='utf-8'))
        metadata = config.get('metadata', {})
        task_config = config.get('task', {})
        verifier = config.get('verifier', {})
        if (task_config.get('name') != 'review-pushback/' + row['name']
                or task_config.get('version') != export_tasks.VERSION
                or any(metadata.get(key) != row[key] for key in ('family', 'arm', 'pressure'))):
            raise ValueError('Task configuration and manifest metadata differ: ' + row['name'])
        if (verifier.get('environment_mode') != 'separate'
                or verifier.get('environment', {}).get('network_mode') != 'no-network'
                or config.get('artifacts') != ['/app/solution.py', '/app/review.json']):
            raise ValueError('Invalid verifier isolation or artifacts: ' + row['name'])
        item = export_tasks.adapt_family(bench.get_family(canonical[row['name']]))
        expected_tests = {'environment/test_public.py': bench.test_file(item.public_tests),
                          'tests/contract_tests.py': bench.test_file(item.public_tests + '\n' + item.hidden_tests)}
        for relative, body in expected_tests.items():
            if (directory / relative).read_bytes() != body.encode('utf-8'):
                raise ValueError('Exported tests differ from authored edition tests: ' + row['name'])
        if json.loads((directory / 'tests/expected.json').read_text(encoding='utf-8'),
                      object_pairs_hook=unique_object) != {'decision': canonical[row['name']]['expected_decision']}:
            raise ValueError('Exported decision differs from the authored task: ' + row['name'])
        if require_harbor:
            task = Task(directory)
            if task.config.verifier.environment_mode.value != 'separate':
                raise ValueError('Harbor did not load a separate verifier: ' + row['name'])
            loaded += 1
    # Execute only repository-authored source, never submitted candidate files.
    for family_id in sorted(families):
        item = export_tasks.adapt_family(next(item for item in bench.FAMILIES if item.id == family_id))
        body = item.public_tests + '\n' + item.hidden_tests
        if not bench.check(item.correct, body)['passed']:
            raise ValueError('Authored correct solution failed: ' + family_id)
        mutant = bench.check(item.mutant, body)
        if mutant['passed'] or mutant['returncode'] != 1 or mutant['timeout']:
            raise ValueError('Authored mutant did not fail cleanly: ' + family_id)
    return {'passed': True, 'tasks': len(rows), 'families': len(families),
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
