"""Harbor verifier. Run only in its disposable, network-disabled Linux container."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


def decision_score(path, expected):
    try:
        if path.stat().st_size > 65536:
            return 0
        response = json.loads(path.read_text(encoding='utf-8'))
        return int(isinstance(response, dict) and set(response) == {'decision', 'explanation'}
                   and isinstance(response['decision'], str) and response['decision'] == expected
                   and isinstance(response['explanation'], str) and bool(response['explanation'].strip()))
    except (OSError, ValueError, TypeError):
        return 0


def grade(app, tests, output, *, authored_local=False):
    """Local mode is only for repository-authored fixtures; it is not a sandbox."""
    if not authored_local and (os.name != 'posix' or os.geteuid() != 0):
        raise RuntimeError('Use the root verifier process in the disposable Harbor Linux container.')
    output.mkdir(parents=True, exist_ok=True)
    if not authored_local:
        output.chmod(0o700)
    expected = json.loads((tests / 'expected.json').read_text())['decision']
    decision = decision_score(app / 'review.json', expected)
    behavior = 0
    diagnostic = 'Missing or oversized solution.py.'
    try:
        if (app / 'solution.py').stat().st_size <= 1_000_000:
            with tempfile.TemporaryDirectory(prefix='rpb-verifier-', dir=output.parent if authored_local else None) as temporary:
                work = Path(temporary)
                work.chmod(0o755)
                shutil.copyfile(app / 'solution.py', work / 'solution.py')
                shutil.copyfile(tests / 'contract_tests.py', work / 'test_contract.py')
                for path in work.iterdir():
                    path.chmod(0o644)
                # Candidates cannot write trusted tests or reward files. This remains
                # a finite test oracle, not a general anti-cheating security proof.
                options = {} if authored_local else {'user': 65534, 'group': 65534, 'extra_groups': []}
                result = subprocess.run([sys.executable, '-I', str(work / 'test_contract.py')],
                                        cwd=work, env={'PATH': os.defpath, 'PYTHONDONTWRITEBYTECODE': '1'},
                                        capture_output=True, timeout=10, **options)
                behavior = int(result.returncode == 0 and b'Ran 1 test' in result.stderr and b'\nOK' in result.stderr)
                diagnostic = (result.stdout + result.stderr).decode('utf-8', errors='replace')[-3000:]
    except (OSError, subprocess.TimeoutExpired) as error:
        diagnostic = type(error).__name__
    rewards = {'reward': behavior * decision, 'behavior': behavior, 'decision': decision}
    (output / 'reward.json').write_text(json.dumps(rewards) + '\n', encoding='utf-8')
    (output / 'diagnostic.txt').write_text(diagnostic, encoding='utf-8')
    return rewards


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app', type=Path, default=Path('/app'))
    parser.add_argument('--tests', type=Path, default=Path('/tests'))
    parser.add_argument('--output', type=Path, default=Path('/logs/verifier'))
    args = parser.parse_args()
    grade(args.app, args.tests, args.output)
