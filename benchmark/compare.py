"""Compare graded runs with paired family-cluster bootstrap intervals (not model-call CIs)."""
import argparse
from collections import defaultdict
import json
from pathlib import Path
import random
import statistics

from bench import VERSION, tasks


def interval(values, seed=20261020, draws=2000):
    rng = random.Random(seed)
    samples = sorted(statistics.mean(rng.choices(values, k=len(values))) for _ in range(draws))
    return [samples[int(draws * 0.025)], samples[int(draws * 0.975) - 1]]


def compare(paths):
    grouped = defaultdict(list)
    seen = set()
    expected = {task['task_id'] for task in tasks()}
    for path in paths:
        run = json.loads(path.read_text(encoding='utf-8'))
        identity = (run['model_label'], run['responses_sha256'])
        if identity in seen:
            raise ValueError('Duplicate response content for the same model; do not count a run twice.')
        seen.add(identity)
        rows = run['rows']
        if (run['summary']['version'] != VERSION or len(rows) != len(expected)
                or {row['task_id'] for row in rows} != expected):
            raise ValueError('All runs must contain the complete same benchmark version and task IDs.')
        grouped[run['model_label']].append(run)
    family_ids = sorted({task['family'] for task in tasks()})
    means = {}
    models = []
    for label, runs in sorted(grouped.items()):
        family_scores = []
        for family_id in family_ids:
            # Equal counts of harmful and valid arms, so the mean is balanced.
            scores = [row['calibrated_pass'] for run in runs for row in run['rows']
                      if row['family'] == family_id and row['arm'] != 'neutral']
            family_scores.append(statistics.mean(scores))
        means[label] = family_scores
        models.append(dict(model_label=label, runs=len(runs), families=len(family_ids),
                           calibrated_balance=statistics.mean(family_scores),
                           family_bootstrap_95=interval(family_scores),
                           run_score_range=[min(run['summary']['calibrated_balance'] for run in runs),
                                            max(run['summary']['calibrated_balance'] for run in runs)],
                           minimum_coverage=min(run['summary']['coverage'] for run in runs)))
    differences = []
    labels = sorted(means)
    for index, left in enumerate(labels):
        for right in labels[index + 1:]:
            deltas = [a - b for a, b in zip(means[left], means[right])]
            differences.append(dict(left=left, right=right, difference=statistics.mean(deltas),
                                    paired_family_bootstrap_95=interval(deltas)))
    return dict(version=VERSION, models=models, paired_differences=differences,
                caveat=f'Intervals resample the {len(family_ids)} problem families, keeping all variants and repeats '
                       'together. They do not fully estimate provider or generation randomness. '
                       'Development set results do not establish a general model ranking.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('runs', nargs='+', type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Refusing to overwrite an existing comparison.')
    result = compare(args.runs)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
