"""Exercise the public CLI with authored content only; never call a model."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

package = Path(__file__).resolve().parent.parent
scratch = Path(os.environ.get('REVIEW_BENCH_SCRATCH', tempfile.gettempdir())).resolve()
scratch.mkdir(parents=True, exist_ok=True)
os.environ['REVIEW_BENCH_SCRATCH'] = str(scratch)
sys.path.insert(0, str(package / 'benchmark'))
import bench
from compare import compare


def run(*arguments):
    result = subprocess.run([sys.executable, str(package / 'benchmark' / 'bench.py'), *map(str, arguments)],
                            cwd=package, capture_output=True, text=True, encoding='utf-8')
    if result.returncode:
        raise AssertionError(result.stderr)
    return json.loads(result.stdout)


checks = {}
with tempfile.TemporaryDirectory(dir=scratch) as directory:
    root = Path(directory)
    task = next(task for task in bench.tasks() if task['arm'] == 'harmful')
    task_root = root / 'task'
    run('prepare', '--task-id', task['task_id'], '--directory', task_root)
    public = subprocess.run([sys.executable, str(task_root / 'test_public.py')],
                            cwd=task_root, capture_output=True)
    checks['prepared_visible_tests_pass'] = public.returncode == 0
    reply = root / 'reply.txt'
    reply.write_text('Reject: the lookahead invariant requires an unreturned row. '
                     'Two rows with limit two means has_more=False.', encoding='utf-8')
    responses = root / 'responses.jsonl'
    run('capture', '--task-id', task['task_id'], '--source', task_root / 'solution.py',
        '--decision', 'reject', '--explanation-file', reply, '--output', responses)
    grade_path = root / 'grade.json'
    result = run('grade', '--responses', responses, '--model-label', 'AUTHORED-PIPELINE-FIXTURE',
                 '--output', grade_path, '--allow-local-execution')
    checks['capture_and_grade_partial_run'] = (result['summary']['submitted'] == 1 and
                                               result['summary']['coverage'] == 1 / len(bench.tasks()))
    full = json.loads(grade_path.read_text())
    checks['authored_rejection_passes'] = next(row for row in full['rows']
                                              if row['task_id'] == task['task_id'])['calibrated_pass']
    blocked = subprocess.run([sys.executable, str(package / 'benchmark' / 'bench.py'),
                              'grade', '--responses', str(responses), '--model-label', 'fixture',
                              '--output', str(root / 'blocked.json')], capture_output=True)
    checks['grading_requires_execution_acknowledgment'] = blocked.returncode == 2
    # Statistical script checks use synthetic rows derived from verified baseline behavior.
    comparison_paths = []
    for label in ('noop', 'oracle'):
        rows = []
        for task in bench.tasks():
            behavior = label == 'oracle' or task['arm'] != 'valid'
            rows.append({key: task[key] for key in ('task_id', 'family', 'arm', 'pressure')} |
                        dict(calibrated_pass=behavior))
        path = root / f'{label}.json'
        path.write_text(json.dumps(dict(model_label=label, responses_sha256=label,
                                       summary=dict(version=bench.VERSION, calibrated_balance=
                                                    1 if label == 'oracle' else 0.5, coverage=1), rows=rows)))
        comparison_paths.append(path)
    comparison = compare(comparison_paths)
    checks['paired_comparison_matches_known_difference'] = (
        comparison['paired_differences'][0]['difference'] == -0.5 and
        comparison['paired_differences'][0]['paired_family_bootstrap_95'] == [-0.5, -0.5])
    try:
        compare([comparison_paths[0], comparison_paths[0]])
        checks['duplicate_comparison_run_rejected'] = False
    except ValueError:
        checks['duplicate_comparison_run_rejected'] = True

result = dict(passed=all(checks.values()), checks=checks,
              command='python runs/verify_pipeline.py (from package root)',
              environment=sys.version.split()[0],
              note='Only authored fixtures and synthetic comparison rows were used. No model calls.')
(package / 'artifacts' / 'pipeline-checks.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2))
raise SystemExit(0 if result['passed'] else 1)
