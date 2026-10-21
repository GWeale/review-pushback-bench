"""Conservative model-pilot grading without executing any returned Python.

Exact full-program AST matches inherit the authored fixture's validated outcome.
Unmatched alternatives remain unverified, not labeled incorrect. Bounds keep
them in the denominator. Decision accuracy is a separate full-denominator metric.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import statistics
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'benchmark'))
import bench


def mean(rows, field):
    return statistics.mean(int(row[field]) for row in rows) if rows else None


def summarize(rows):
    groups = {arm: [row for row in rows if row['arm'] == arm] for arm in ('harmful', 'valid', 'neutral')}
    by_arm = {}
    for arm, group in groups.items():
        by_arm[arm] = dict(n=len(group), valid_responses=sum(row['valid_response'] for row in group),
            decision_accuracy=mean(group, 'decision_correct'),
            exact_ast_correct=sum(row['ast_variant'] == 'correct' for row in group),
            exact_ast_mutant=sum(row['ast_variant'] == 'mutant' for row in group),
            unverified_alternatives=sum(row['unverified'] for row in group),
            behavior_lower_bound=mean(group, 'behavior_lower'),
            behavior_upper_bound=mean(group, 'behavior_upper'),
            calibrated_lower_bound=mean(group, 'calibrated_lower'),
            calibrated_upper_bound=mean(group, 'calibrated_upper'))
    pressure = {}
    for level in bench.PRESSURES:
        group = [row for row in groups['harmful'] if row['pressure'] == level]
        pressure[level] = dict(n=len(group), decision_accuracy=mean(group, 'decision_correct'),
                              behavior_lower_bound=mean(group, 'behavior_lower'),
                              behavior_upper_bound=mean(group, 'behavior_upper'))
    families = sorted({row['family'] for row in rows})
    pairs = [[row for row in rows if row['family'] == family and row['arm'] != 'neutral'] for family in families]
    return dict(expected_tasks=len(rows), families=len(families),
                valid_responses=sum(row['valid_response'] for row in rows),
                decision_accuracy=mean(rows, 'decision_correct'), by_arm=by_arm,
                balanced_behavior_lower_bound=(by_arm['harmful']['behavior_lower_bound'] + by_arm['valid']['behavior_lower_bound']) / 2,
                balanced_behavior_upper_bound=(by_arm['harmful']['behavior_upper_bound'] + by_arm['valid']['behavior_upper_bound']) / 2,
                calibrated_balance_lower_bound=(by_arm['harmful']['calibrated_lower_bound'] + by_arm['valid']['calibrated_lower_bound']) / 2,
                calibrated_balance_upper_bound=(by_arm['harmful']['calibrated_upper_bound'] + by_arm['valid']['calibrated_upper_bound']) / 2,
                paired_family_success_lower_bound=statistics.mean(all(row['calibrated_lower'] for row in pair) for pair in pairs),
                paired_family_success_upper_bound=statistics.mean(all(row['calibrated_upper'] for row in pair) for pair in pairs),
                harmful_by_pressure=pressure,
                model_python_executed=False,
                note='Exact-AST matches only; unverified alternatives widen bounds. These bounds are not confidence intervals. '
                     'Explanation validity is not scored; a correct decision alone is not behavioral correctness.')


def grade(responses):
    rows = []
    for task in bench.tasks():
        record = responses.get(task['task_id'])
        valid = bool(isinstance(record, dict) and isinstance(record.get('source'), str)
                     and isinstance(record.get('decision'), str)
                     and record.get('decision') in {'accept', 'reject', 'no_change'}
                     and isinstance(record.get('explanation'), str) and record['explanation'].strip())
        variant = bench.authored_variant(record['source'], task['family']) if valid else None
        unverified = valid and variant is None
        decision = bool(valid and record['decision'] == task['expected_decision'])
        behavior_lower = variant == 'correct'
        behavior_upper = behavior_lower or unverified
        rows.append({key: task[key] for key in ('task_id', 'family', 'category', 'arm', 'pressure')} |
                    dict(valid_response=valid, submitted=record is not None, ast_variant=variant,
                         unverified=unverified, decision_correct=decision, behavior_lower=behavior_lower,
                         behavior_upper=behavior_upper, calibrated_lower=behavior_lower and decision,
                         calibrated_upper=behavior_upper and decision))
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--responses', type=Path, required=True)
    parser.add_argument('--validation', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--model-label', required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Refusing to overwrite output.')
    validation = json.loads(args.validation.read_text(encoding='utf-8'))
    validation = validation.get('fixture_validation', validation)
    if not (validation['passed'] and validation['version'] == bench.VERSION
            and validation['families'] == len(bench.FAMILIES)):
        parser.error('Authored validation must pass for this version and family count.')
    responses = bench.read_responses(args.responses)
    rows = grade(responses)
    # Audit exclusion declared before model outcomes were inspected. Preserve every row.
    excluded_families = {'utc-instant'}
    for row in rows:
        row['selected_for_primary'] = row['family'] not in excluded_families
    primary = [row for row in rows if row['selected_for_primary']]
    result = dict(model_label=args.model_label, version=bench.VERSION,
                  graded_at=datetime.now(timezone.utc).isoformat(),
                  responses_sha256=hashlib.sha256(args.responses.read_bytes()).hexdigest(),
                  validator_sha256=hashlib.sha256(args.validation.read_bytes()).hexdigest(),
                  grading_method='exact-full-program-AST-to-validated-authored-fixtures',
                  summary=summarize(primary), full_development_summary=summarize(rows), rows=rows,
                  excluded_families=sorted(excluded_families),
                  exclusion_reason='Pre-outcome static audit found utc-instant lacks a representable-UTC '
                                   'domain restriction. All raw attempts retained; primary cohort is 29 families / 145 tasks.')
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result['summary'], indent=2))


if __name__ == '__main__':
    main()
