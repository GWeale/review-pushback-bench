"""Check the public release file set, measured artifacts, local tests, and privacy boundaries."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parent.parent


def public_files():
    paths = [ROOT / name for name in ('README.md', 'LICENSE', 'CITATION.cff', '.gitignore', '.gitattributes',
                                     'run-record.example.json', 'research.json')]
    for directory, patterns in [('benchmark', ['*.py']), ('harbor', ['*.py', '*.md']), ('runs', ['*.py']), ('docs', ['*.md']),
                                ('inputs', ['*.md']), ('assets', ['*.png', '*.md']),
                                ('.github/workflows', ['*.yml']),
                                ('paper', ['*.md', '*.bib', '*.py', '*.json', 'review-pushback-bench.pdf']),
                                ('paper/latex', ['*.tex'])]:
        for pattern in patterns:
            paths.extend((ROOT / directory).glob(pattern))
    for name in ('validation.v0.2.json', 'selftest.v0.2.json', 'pipeline-checks.json',
                 'tasks.v0.2.dev.jsonl', 'primary-analysis-plan.json', 'release-checks.json', 'harbor-validation.v01.json', 'harbor-validation.v02.json',
                 'repository-validation.v05.json', 'repository-harbor-validation.v05.json', 'repository-human-review.v05.json',
                 'repository-pilot-grade.v05.json', 'repository-pilot-summary.v05.json', 'repository-native.v05.json'):
        paths.append(ROOT / 'artifacts' / name)
    for directory in ('repository', 'artifacts/repository-pilot.v05', 'artifacts/repository-native.v05'):
        paths.extend(p for p in (ROOT / directory).rglob('*') if p.is_file() and '__pycache__' not in p.parts)
    for directory in ('gemini-2.5-flash-v02', 'gemini-3.5-flash-lite-v02'):
        for name in ('run.json', 'attempts.jsonl', 'responses.jsonl', 'canonical-grade.json'):
            paths.append(ROOT / 'artifacts/model-runs' / directory / name)
    return sorted(set(paths))


def main():
    checks = {}
    logs = {}
    for label, directory, pattern in [('harness', 'benchmark', 'test_*.py'), ('adapters', 'runs', 'test_*.py'), ('harbor', 'harbor', 'test_*.py'), ('repository','repository','test_*.py')]:
        result = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', directory, '-p', pattern, '-v'],
                                cwd=ROOT, capture_output=True, text=True, encoding='utf-8')
        checks[label + '_tests'] = result.returncode == 0
        logs[label] = result.stdout + result.stderr
    validation = json.loads((ROOT / 'artifacts/validation.v0.2.json').read_text())
    policy = json.loads((ROOT / 'artifacts/selftest.v0.2.json').read_text())
    checks['authored_fixture_validation'] = validation['passed'] and validation['families'] == 30 and validation['tasks'] == 150
    checks['synthetic_policy_checks'] = policy['passed']
    checks['pipeline_checks'] = json.loads((ROOT / 'artifacts/pipeline-checks.json').read_text())['passed']
    repository_validation=json.loads((ROOT/'artifacts/repository-validation.v05.json').read_text())
    checks['repository_fixtures']=repository_validation['passed'] and repository_validation['families']==20
    checks['repository_harbor_schema']=json.loads((ROOT/'artifacts/repository-harbor-validation.v05.json').read_text())['tasks_loaded']==80
    export = ROOT / 'artifacts/tasks.v0.2.dev.jsonl'
    export_hash = hashlib.sha256(export.read_bytes()).hexdigest()
    plan = json.loads((ROOT / 'artifacts/primary-analysis-plan.json').read_text())
    checks['frozen_export_matches_analysis_plan'] = plan['frozen_export_sha256'] == export_hash
    for folder in ('gemini-2.5-flash-v02', 'gemini-3.5-flash-lite-v02'):
        root = ROOT / 'artifacts/model-runs' / folder
        run = json.loads((root / 'run.json').read_text())
        grade = json.loads((root / 'canonical-grade.json').read_text())
        attempts = [json.loads(line) for line in (root / 'attempts.jsonl').read_text().splitlines()]
        checks[folder + '_completed'] = run['attempts'] == 150 and run['status'] == 'completed' and len(attempts) == 150
        checks[folder + '_frozen_inputs'] = run['config']['tasks_sha256'] == export_hash and (
            run['config']['runner_sha256'] == hashlib.sha256((ROOT / 'runs/gemini_runner_pilot.py').read_bytes()).hexdigest())
        checks[folder + '_primary_cohort'] = grade['summary']['families'] == 29 and grade['summary']['expected_tasks'] == 145
        checks[folder + '_response_hash'] = grade['responses_sha256'] == hashlib.sha256((root / 'responses.jsonl').read_bytes()).hexdigest()
        checks[folder + '_no_model_execution'] = grade['summary']['model_python_executed'] is False
    privacy_issues, link_issues, pending = [], [], []
    secret_values = [value.encode() for name in ('GEMINI_API_KEY', 'OPENAI_API_KEY', 'OPENROUTER_API_KEY', 'ANTHROPIC_API_KEY')
                     if (value := os.environ.get(name)) and len(value) > 10]
    for path in public_files():
        if not path.exists():
            if path.name not in {'release-checks.json', 'research.json'}:
                pending.append(path.relative_to(ROOT).as_posix())
            continue
        data = path.read_bytes()
        if any(secret in data for secret in secret_values) or re.search(rb'AIza[0-9A-Za-z_-]{30,}|gh[pousr]_[0-9A-Za-z]{30,}', data):
            privacy_issues.append(path.relative_to(ROOT).as_posix())
        if path.suffix == '.md' and 'vendor' not in path.relative_to(ROOT).parts:
            text = data.decode('utf-8')
            for target in re.findall(r'\]\(([^)]+)\)', text):
                if '://' in target or target.startswith('#'):
                    continue
                local = target.split('#')[0]
                if local and not (path.parent / local).exists():
                    link_issues.append(dict(file=path.relative_to(ROOT).as_posix(), target=target))
    checks['no_provider_credentials_in_public_files'] = not privacy_issues
    checks['public_markdown_links'] = not link_issues
    checks['required_public_files_exist'] = not pending
    result = dict(checked_at=datetime.now(timezone.utc).isoformat(), passed=all(checks.values()),
                  checks=checks, unittest_output=logs, privacy_issue_files=privacy_issues,
                  broken_links=link_issues, pending_files=pending,
                  environment='Python ' + sys.version.split()[0] + '; standard library',
                  note='No model-returned source was executed. Remote GitHub CI is a separate check.')
    (ROOT / 'artifacts/release-checks.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({key: value for key, value in result.items() if key != 'unittest_output'}, indent=2))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
