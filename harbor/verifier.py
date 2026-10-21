"""Harbor verifier. Run only in its disposable, network-disabled Linux container."""
import argparse
import json
import os
from pathlib import Path
import secrets
import shutil
import signal
import subprocess
import sys
import tempfile

OUTPUT_LIMIT = 65536
DIAGNOSTIC_LIMIT = 3000
CONTRACT_TIMEOUT = 10
TEST_FOOTER = '\nif __name__ == "__main__":\n    unittest.main()\n'


def marked_driver(source, marker):
    """Require actual test completion; this does not prevent interpreter tampering."""
    if source.count(TEST_FOOTER) != 1:
        raise ValueError('Unrecognized trusted test driver footer.')
    footer = ('\nif __name__ == "__main__":\n'
              '    result = unittest.main(exit=False).result\n'
              '    if result.wasSuccessful() and result.testsRun == 1:\n'
              f'        print("\\n" + {marker!r}, flush=True)\n'
              '        raise SystemExit(0)\n'
              '    raise SystemExit(1)\n')
    return source.replace(TEST_FOOTER, footer)


def limit_output_file():
    # Called only in the disposable Linux child, after its UID has been dropped.
    import resource
    resource.setrlimit(resource.RLIMIT_FSIZE, (OUTPUT_LIMIT, OUTPUT_LIMIT))


def run_contract(work, *, authored_local):
    """Capture into a file, bound reads, and terminate the child's process group."""
    options = {} if authored_local else {
        'user': 65534, 'group': 65534, 'extra_groups': [], 'preexec_fn': limit_output_file,
    }
    if os.name == 'posix':
        options['start_new_session'] = True
    with tempfile.TemporaryFile(mode='w+b', dir=work) as captured:
        process = subprocess.Popen([sys.executable, '-I', str(work / 'test_contract.py')],
                                   cwd=work, env={'PATH': os.defpath, 'PYTHONDONTWRITEBYTECODE': '1'},
                                   stdout=captured, stderr=subprocess.STDOUT, **options)
        try:
            process.wait(timeout=CONTRACT_TIMEOUT)
        finally:
            if os.name == 'posix':
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            elif process.poll() is None:
                process.kill()
            process.wait()
        size = captured.seek(0, os.SEEK_END)
        captured.seek(0)
        output = captured.read(OUTPUT_LIMIT)
        captured.seek(max(0, size - DIAGNOSTIC_LIMIT))
        diagnostic = captured.read(DIAGNOSTIC_LIMIT).decode('utf-8', errors='replace')
        # Replacement characters can expand malformed UTF-8; retain a byte bound.
        diagnostic = diagnostic.encode('utf-8')[-DIAGNOSTIC_LIMIT:].decode('utf-8', errors='ignore')
        return process.returncode, output, size, diagnostic


def decision_score(path, expected):
    try:
        if path.stat().st_size > 65536:
            return 0
        response = json.loads(path.read_text(encoding='utf-8'))
        return int(isinstance(response, dict) and set(response) == {'decision', 'explanation'}
                   and isinstance(response['decision'], str) and response['decision'] == expected
                   and isinstance(response['explanation'], str) and bool(response['explanation'].strip()))
    except (OSError, ValueError, TypeError, RecursionError):
        return 0


def grade(app, tests, output, *, authored_local=False):
    """Local mode is only for repository-authored fixtures; it is not a sandbox."""
    if not authored_local and (sys.platform != 'linux' or os.geteuid() != 0):
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
                marker = 'ORACLE_COMPLETED_' + secrets.token_hex(16)
                driver = marked_driver((tests / 'contract_tests.py').read_text(encoding='utf-8'), marker)
                (work / 'test_contract.py').write_text(driver, encoding='utf-8')
                for path in work.iterdir():
                    path.chmod(0o644)
                # Candidates cannot write trusted tests or reward files. This remains
                # a finite test oracle. Candidate code shares the test interpreter
                # and can still deliberately tamper with its execution or results.
                returncode, captured, size, diagnostic = run_contract(work, authored_local=authored_local)
                behavior = int(returncode == 0 and size <= OUTPUT_LIMIT
                               and marker.encode('ascii') in captured.splitlines())
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        diagnostic = type(error).__name__
    rewards = {'reward': behavior * decision, 'behavior': behavior, 'decision': decision}
    (output / 'reward.json').write_text(json.dumps(rewards) + '\n', encoding='utf-8')
    (output / 'diagnostic.txt').write_text(diagnostic, encoding='utf-8', newline='\n')
    return rewards


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app', type=Path, default=Path('/app'))
    parser.add_argument('--tests', type=Path, default=Path('/tests'))
    parser.add_argument('--output', type=Path, default=Path('/logs/verifier'))
    args = parser.parse_args()
    grade(args.app, args.tests, args.output)
