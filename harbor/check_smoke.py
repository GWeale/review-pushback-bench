"""Assert actual Harbor trial outputs, rather than trusting a CLI exit status."""
import argparse
import json
from pathlib import Path
from summarize import summarize


def check(jobs, tasks):
    manifest = json.loads((tasks / 'manifest.json').read_text(encoding='utf-8'))
    expected_names = {row['name'] for row in manifest['tasks']}
    if len(expected_names) != 5 or len(manifest['tasks']) != 5:
        raise ValueError('The smoke manifest must contain five distinct tasks.')
    summary = {}
    for agent, expected in [('oracle', 1), ('nop', 0)]:
        results = [json.loads(path.read_text()) for path in (jobs / agent).glob('*/result.json')]
        names = [result['task_name'].split('/')[-1] for result in results]
        if len(results) != 5 or len(set(names)) != 5 or set(names) != expected_names:
            raise ValueError(agent + ': trial identities do not match the five exported tasks.')
        scores = summarize(manifest, results)
        if scores['valid_results'] != 5:
            raise ValueError(agent + ': malformed verifier results.')
        for result in results:
            if (result.get('exception_info') is not None
                    or result.get('verifier_environment_mode') != 'separate'
                    or result['verifier_result']['rewards']['reward'] != expected):
                raise ValueError(agent + ': unexpected trial error, verifier mode, or reward.')
        summary[agent] = {'trials': len(results), 'expected_reward': expected, 'all_passed': True}
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--jobs', type=Path, required=True)
    parser.add_argument('--tasks', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(check(args.jobs, args.tasks), indent=2))
