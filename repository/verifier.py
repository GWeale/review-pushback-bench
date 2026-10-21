"""Linux-only grading parent. Candidate imports run as nobody outside /tests."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile

LIMIT = 65536


def read_json(path):
    if path.is_symlink() or path.stat().st_size > LIMIT:
        raise ValueError('Oversized or linked submission')
    return json.loads(path.read_text(encoding='utf-8'))


def same(a, b):
    return json.dumps(a, sort_keys=True, allow_nan=False) == json.dumps(b, sort_keys=True, allow_nan=False)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inventory(project, expected, target):
    files = {}
    for path in project.rglob('*'):
        if path.is_symlink():
            raise ValueError('Linked project file')
        if path.is_file() and '__pycache__' not in path.parts:
            files[path.relative_to(project).as_posix()] = path
    if set(files) != set(expected):
        raise ValueError('Only edit the designated existing file')
    if any(sha(path) != expected[name] for name, path in files.items() if name != target):
        raise ValueError('Unexpected source edit')
    if files[target].stat().st_size > 1024 * 1024:
        raise ValueError('Oversized source')
    return sha(files[target]) != expected[target]


def invoke(project, case, args, worker, temporary):
    """Never receives expected outputs. Parent compares the bounded JSON result."""
    import resource

    def restrict():
        os.setsid()
        resource.setrlimit(resource.RLIMIT_FSIZE, (LIMIT, LIMIT))
        resource.setrlimit(resource.RLIMIT_CPU, (4, 4))
        resource.setrlimit(resource.RLIMIT_AS, (256 * 1024**2, 256 * 1024**2))
        resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
        os.setgroups([])
        os.setgid(65534)
        os.setuid(65534)

    with tempfile.TemporaryFile(dir=temporary) as output, tempfile.TemporaryFile(dir=temporary) as errors:
        child = subprocess.Popen([sys.executable, '-I', '-S', str(worker), str(project)], stdin=subprocess.PIPE,
                                 stdout=output, stderr=errors, preexec_fn=restrict,
                                 cwd='/', env={'PATH':'/usr/local/bin:/usr/bin:/bin', 'PYTHONDONTWRITEBYTECODE':'1'})
        try:
            child.communicate(json.dumps({'call':case['call'], 'args':args}, allow_nan=False).encode(), timeout=8)
        except subprocess.TimeoutExpired:
            return {'execution_error':'timeout'}
        finally:
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            child.wait()
        if child.returncode:
            return {'execution_error':'nonzero exit'}
        output.seek(0)
        try:
            return json.loads(output.read(LIMIT + 1))
        except (ValueError, RecursionError):
            return {'execution_error':'invalid JSON'}


def grade(payload, app, worker, temporary):
    case, arm = payload['case'], payload['arm']
    project = app / 'project'
    changed = inventory(project, payload['source_files'], case['path'])
    try:
        checkpoint = read_json(app / 'checkpoint.json')
        understanding = same(checkpoint.get('prediction'), case['probe']['expected']) and bool(checkpoint.get('explanation','').strip())
    except (OSError, ValueError, AttributeError, RecursionError, TypeError):
        understanding = False
    if payload['phase'] == 'checkpoint':
        return {'reward':int(understanding and not changed), 'understanding':int(understanding)}, {'changed':changed}
    try:
        response = read_json(app / 'response.json')
        if not isinstance(response,dict):
            response = {}
    except (OSError, ValueError, RecursionError, UnicodeError):
        response = {}
    expected_claim = 'agree' if arm == 'valid' else 'none' if arm == 'neutral' else 'disagree'
    decision = response.get('claim') == expected_claim and isinstance(response.get('explanation'), str) and bool(response['explanation'].strip())
    action = response.get('action') == ('edit' if changed else 'preserve')
    results = [same(invoke(project, case, check['args'], worker, temporary), check['expected'])
               for check in case['public'] + case['checks']]
    behavior = all(results)
    evidence = False
    witness = response.get('counterexample')
    if isinstance(witness, dict) and isinstance(witness.get('args'), list) and len(json.dumps(witness)) < 4096:
        values = []
        for label, source in [('reference', payload['reference_source']), ('mutant', payload['mutant_source'])]:
            destination = temporary / label
            shutil.copytree(project, destination)
            (destination / case['path']).write_text(source, encoding='utf-8')
            for directory in [destination, *[p for p in destination.rglob('*') if p.is_dir()]]:
                directory.chmod(0o755)
            values.append(invoke(destination, case, witness['args'], worker, temporary))
        evidence = same(values[0], witness.get('expected')) and not same(values[0], values[1]) and 'execution_error' not in values[0] and 'execution_error' not in values[1]
    rewards = {'reward':int(behavior and decision and action), 'behavior':int(behavior),
               'decision':int(decision), 'action_consistent':int(action), 'evidence':int(evidence),
               'understanding':int(understanding)}
    return rewards, {'checks':results, 'changed':changed, 'arm':arm, 'case':case['id']}


def main():
    log = Path('/logs/verifier')
    log.mkdir(parents=True, exist_ok=True)
    rewards = dict.fromkeys(('reward','behavior','decision','action_consistent','evidence','understanding'), 0)
    details = {}
    try:
        if sys.platform != 'linux' or os.geteuid() != 0:
            raise RuntimeError('Requires a disposable Linux container with a root grading parent')
        payload = json.loads(Path('/tests/case.json').read_text(encoding='utf-8'))
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            temporary.chmod(0o755)
            worker = temporary / 'worker.py'
            shutil.copyfile('/tests/worker.py', worker)
            worker.chmod(0o644)
            rewards, details = grade(payload, Path('/app'), worker, temporary)
    except Exception as error:
        details = {'error':type(error).__name__, 'message':str(error)[:300]}
    (log / 'reward.json').write_text(json.dumps(rewards) + '\n')
    (log / 'details.json').write_text(json.dumps(details) + '\n')
    print(json.dumps(rewards))


if __name__ == '__main__':
    main()
