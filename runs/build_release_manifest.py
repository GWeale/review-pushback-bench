"""Build a public release evidence ledger from executed artifacts; no API calls."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'benchmark'))
import bench


def sha(path):
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def main():
    validation = json.loads((ROOT / 'artifacts/validation.v0.2.json').read_text())
    policy = json.loads((ROOT / 'artifacts/selftest.v0.2.json').read_text())
    assert validation['passed'] and policy['passed']
    sources = [s for s in json.loads((ROOT / 'research.json').read_text(encoding='utf-8'))['sources'] if s['id'] != 'gemini-pricing']
    paper_sources = json.loads((ROOT / 'paper/sources.json').read_text(encoding='utf-8'))
    for source in paper_sources:
        if not any(item['id'] == source['id'] for item in sources):
            sources.append(dict(id=source['id'], title=source['use'], url=source['url'], accessed=source['accessed']))
    for id, title, url in [
        ('gemini-structured', 'Gemini structured output documentation', 'https://ai.google.dev/gemini-api/docs/structured-output'),
        ('gemini-thinking', 'Gemini thinking configuration documentation', 'https://ai.google.dev/gemini-api/docs/thinking'),
        ('harbor-multi-step', 'Harbor multi-step task documentation', 'https://docs.harborframework.com/tasks/multi-step'),
    ]:
        if not any(source['id'] == id for source in sources):
            sources.append(dict(id=id, title=title, url=url, accessed='2026-10-20'))
    for source in json.loads((ROOT/'repository/sources.json').read_text()):
        id='upstream-'+source['id']
        if not any(item['id']==id for item in sources):
            sources.append(dict(id=id,title=source['id']+' pinned package source',url=source['snapshot_url'],accessed='2026-10-20'))
    output_specs = [
        ('validation', 'log', 'artifacts/validation.v0.2.json', 'python benchmark/bench.py validate --output NEW_PATH.json'),
        ('policies', 'log', 'artifacts/selftest.v0.2.json', 'python benchmark/bench.py selftest --output NEW_PATH.json'),
        ('pipeline', 'log', 'artifacts/pipeline-checks.json', 'python runs/verify_pipeline.py'),
        ('tests', 'log', 'artifacts/release-checks.json', 'python runs/check_release.py'),
        ('tasks-v02', 'data', 'artifacts/tasks.v0.2.dev.jsonl', 'python benchmark/bench.py export --output NEW_PATH.jsonl --seed 20261020'),
        ('harbor-validation', 'log', 'artifacts/harbor-validation.v02.json', 'python harbor/validate_tasks.py --tasks EXPORTED_TASKS --require-harbor'),
        ('analysis-plan', 'data', 'artifacts/primary-analysis-plan.json', 'Pre-outcome static audit decision recorded locally before score inspection.'),
        ('paper-md', 'other', 'paper/paper.md', 'Authored technical report, source for paper/build_paper.py.'),
        ('paper-pdf', 'other', 'paper/review-pushback-bench.pdf', 'python paper/build_paper.py; then pdflatex -interaction=nonstopmode main.tex twice from paper/latex; copy main.pdf to release path.'),
        ('image', 'figure', 'assets/review-pushback-banner.png', 'User-selected built-in imagegen illustration; exact prompt and hash in assets/README.md.'),
        ('repository-validation','log','artifacts/repository-validation.v05.json','python repository/suite.py validate --output NEW_PATH.json'),
        ('repository-schema','log','artifacts/repository-harbor-validation.v05.json','python repository/check_native.py --tasks EXPORTED_TASKS --output NEW_PATH.json'),
        ('repository-cases','data','repository/cases.json','Benchmark-authored case definitions; reviews are not historical upstream comments.'),
        ('repository-sources','data','repository/sources.json','Pinned upstream files and documented packaging shim, with per-file SHA-256.'),
        ('repository-review-packet','data','repository/human_review.json','Unfilled independent human review records.'),
        ('repository-human-review','log','artifacts/repository-human-review.v05.json','python repository/review.py --output NEW_PATH.json'),
        ('repository-native','log','artifacts/repository-native.v05.json','python repository/check_native.py --tasks SMOKE_TASKS --jobs NATIVE_JOBS --output NEW_PATH.json; Linux Docker CI.'),
        ('repository-pilot-grade','data','artifacts/repository-pilot-grade.v05.json','python repository/check_docker.py; exact inputs and CI provenance in this artifact.'),
        ('repository-pilot-summary','data','artifacts/repository-pilot-summary.v05.json','python repository/summarize.py --pilot artifacts/repository-pilot.v05 --grades artifacts/repository-pilot-grade.v05.json --output NEW_PATH.json'),
    ]
    for path in sorted((ROOT/'artifacts/repository-pilot.v05').rglob('*')):
        if path.is_file():
            relative=path.relative_to(ROOT).as_posix()
            id='repo-pilot-'+path.relative_to(ROOT/'artifacts/repository-pilot.v05').as_posix().replace('/','-').replace('.','-')
            output_specs.append((id,'data',relative,'Original two-case read/edit tool-agent pilot. See frozen plan.json, index.json, and saved conversations. No candidate execution during generation.'))
    claims = []
    evidence = []
    def claim(id, kind, statement, *, outputs=(), refs=(), dependencies=(), caveats=()):
        claims.append(dict(id=id, kind=kind, statement=statement,
            status='reproduced' if kind == 'computational' else 'supported',
            sourceRefs=[dict(sourceId=source, locator=locator) for source, locator in refs],
            outputIds=list(outputs), dependsOn=list(dependencies), caveats=list(caveats)))
        evidence.append(f'<!-- claim:{id} -->\n\n{statement}\n')
    for source in paper_sources:
        claim('related-' + source['id'], 'empirical',
              'The paper uses ' + source['id'] + ' as a design or related-work source: ' + source['use'] + '.',
              refs=[(source['id'], source['locator'])], caveats=['This is source-grounded related work, not a reproduction of that source\'s model results.'])
    claim('dataset-validation', 'computational',
          'The frozen v0.2.0-dev development set has 30 authored families and 150 scenarios. '
          'All correct references pass authored visible/evaluator checks; all intended mutants pass visible checks and fail evaluator checks.',
          outputs=['validation', 'tasks-v02'], caveats=['These are finite authored checks, not formal proof over the full contract. Known contract-domain limits are disclosed.'])
    claim('policy-controls', 'computational',
          'Synthetic no-op and blind compliance score 0.5 balanced behavior and zero paired-family success; '
          'the answer-key policy scores 1.0. These are not model measurements.', outputs=['policies'])
    claim('repository-fixtures','computational',
          'Version 0.5 adds 20 cases from five pinned Python projects and 80 staged Harbor tasks. All correct fixtures pass finite checks; all declared mutants pass basic examples and fail a distinguishing check. Harbor 0.24.0 loads all 80 task schemas.',
          outputs=['repository-validation','repository-schema','repository-cases','repository-sources'],
          refs=[('harbor-multi-step','Multi-step structure, final reward strategy, and conversation resumption.')],
          caveats=['Comments are benchmark-authored. Package snapshots are not full repository histories. Compatibility shims are disclosed. Finite checks are not full API proof.'])
    claim('repository-review-status','computational',
          'All 20 repository cases remain pending independent human validation; the release has no private holdout.',
          outputs=['repository-human-review','repository-review-packet'],caveats=['Agent reviews are not human annotation.'])
    pilot_summary=json.loads((ROOT/'artifacts/repository-pilot-summary.v05.json').read_text())
    claim('repository-tool-agent-pilot','computational',
          f"A separate Gemini 2.5 Flash read/edit tool-agent pilot covers {pilot_summary['families']} convenience cases, "
          f"{pilot_summary['checkpoint_correct']} correct checkpoints, and {pilot_summary['graded_states']}/{pilot_summary['expected_saved_review_states']} graded saved review states. "
          'Correct-start arms share the exact saved pre-review conversation. Execution and strict disposition scores are reported separately.',
          outputs=['repository-pilot-summary','repository-pilot-grade','repository-native'],
          caveats=['One repetition, no shell or test tool, two convenience cases, no native Harbor model scores or causal attribution. Raw records are retained.'])
    claim('release-checks', 'computational', 'Local harness, adapter, canonical-grading, pipeline, and release-integrity checks pass.',
          outputs=['tests', 'pipeline'], caveats=['Remote CI status must be checked separately after publication.'])
    claim('primary-exclusion', 'computational',
          'The primary pilot cohort excludes utc-instant and contains 29 families / 145 scenarios per model; '
          'the declaration predates model score inspection and all 150 raw attempts per model are retained.',
          outputs=['analysis-plan'], caveats=['This was a concurrent pre-outcome audit decision, not formal preregistration.'])
    for folder, short in [('gemini-2.5-flash-v02', 'flash25'), ('gemini-3.5-flash-lite-v02', 'lite35')]:
        base = f'artifacts/model-runs/{folder}'
        run = json.loads((ROOT / base / 'run.json').read_text())
        grade = json.loads((ROOT / base / 'canonical-grade.json').read_text())
        assert run['status'] == 'completed' and run['attempts'] == 150
        for suffix, kind in [('run.json', 'log'), ('attempts.jsonl', 'data'), ('responses.jsonl', 'data'), ('canonical-grade.json', 'data')]:
            output_specs.append((short + '-' + suffix.split('.')[0], kind, base + '/' + suffix,
                'Original generation: see the reproduction guide and run.json config. Regrade: python runs/grade_canonical.py with this responses file, artifacts/validation.v0.2.json, a new output path, and exact model label.'))
        summary = grade['summary']
        h = summary['by_arm']['harmful']
        claim(short + '-pilot', 'computational',
              f"{run['config']['model_id']} returned {run['valid_responses']}/150 valid-format responses. "
              f"On the primary 145 scenarios its strict decision-label agreement is {summary['decision_accuracy']:.12f}; "
              f"harmful responses match the validated correct-reference AST in {h['exact_ast_correct']}/{h['n']} cases. "
              f"Balanced reference-test agreement is bounded by {summary['balanced_behavior_lower_bound']:.12f} "
              f"and {summary['balanced_behavior_upper_bound']:.12f} under conservative matching.",
              outputs=[short + '-run', short + '-attempts', short + '-responses', short + '-canonical-grade'],
              caveats=['No model-returned source was executed; alternative ASTs remain unverified. One repetition, convenience sample, different supported thinking settings. Bounds are not confidence intervals.'])
    claim('interpretation', 'synthetic',
          'This is an open development benchmark and methodology report with separate small direct-completion and read/edit tool-agent pilots; '
          'it does not establish causal sycophancy, representative real-review failure rates, or a frontier-model ranking.',
          dependencies=['dataset-validation', 'primary-exclusion', 'flash25-pilot', 'lite35-pilot'],
          caveats=['Explicit contracts and permission to disagree can make the harmful arms easy; valid arms start from broken code.'])
    output_records = [dict(id=id, kind=kind, path=path, sha256=sha(path), command=command,
                           environment='Python 3.13.4, Windows; standard library. Authored checks use a writable REVIEW_BENCH_SCRATCH.')
                      for id, kind, path, command in output_specs]
    for directory in ('benchmark', 'runs', 'harbor', 'repository'):
        for path in sorted((ROOT / directory).glob('*.py')):
            relative = path.relative_to(ROOT).as_posix()
            output_records.append(dict(id='source-' + directory + '-' + path.stem.replace('_', '-'),
                kind='code', path=relative, sha256=sha(relative), command='Versioned source; see recorded execution commands.'))
    report_path = 'docs/RESEARCH_EVIDENCE.md'
    (ROOT / report_path).write_text('# Release evidence ledger\n\nThis ledger supports the paper and README; '
        'it distinguishes measurements from interpretation. Source and output hashes are in research.json.\n\n' + '\n'.join(evidence), encoding='utf-8')
    question_path = 'inputs/question.md'
    (ROOT / question_path).write_text('# Research question and authorized release scope\n\n'
        'Can an implementing coding model reject an incorrect code-review change while accepting valid repairs? '
        'Create and publish a reproducible GitHub benchmark, technical paper, preliminary tests, and companion illustration. '
        'The user explicitly requested multi-agent creation and GitHub publication on October 20, 2026. '
        'The release is not represented as peer reviewed.\n', encoding='utf-8')
    manifest = dict(schemaVersion='1.0', id='review-pushback-bench',
        title='Review Pushback Bench: methodology and preliminary model pilot', deliverableMode='report',
        question=dict(path=question_path, sha256=sha(question_path)), sources=sources,
        outputs=output_records, claims=claims,
        report=dict(path=report_path, sha256=sha(report_path), status='approved'),
        approvals=dict(scope=dict(status='approved', approvedAt='2026-10-20',
                                  note='Direct user instruction to create benchmark, paper, image, and publish on GitHub.'),
                       final=dict(status='approved', approvedAt='2026-10-20',
                                  note='User explicitly authorized creation and publication in this turn. '
                                       'This records publication authorization, not a claim that the user reviewed every line or that peer review occurred.')))
    (ROOT / 'research.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print('Release ledger generated from completed artifacts and explicit publication authorization.')


if __name__ == '__main__':
    main()
