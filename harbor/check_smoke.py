"""Assert actual Harbor trial outputs, rather than trusting a CLI exit status."""
import argparse
import json
from pathlib import Path


def check(jobs):
    summary = {}
    for agent, expected in [('oracle', 1), ('nop', 0)]:
        results = [json.loads(path.read_text()) for path in (jobs / agent).glob('*/result.json')]
        assert len(results) == 5, (agent, len(results))
        for result in results:
            assert result['exception_info'] is None, result.get('exception_info')
            assert result['verifier_environment_mode'] == 'separate'
            assert result['verifier_result']['rewards']['reward'] == expected, result['verifier_result']
        summary[agent] = {'trials': len(results), 'expected_reward': expected, 'all_passed': True}
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--jobs', type=Path, required=True)
    check(parser.parse_args().jobs)
