"""Generate the short project README. Detailed methods live in the paper and guides."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = '''# Review Pushback Bench

<img src="assets/review-bot.png" alt="A robot questions a mistaken code review" width="230" align="right" />

**Can a coding agent push back when a reviewer is wrong?**

Give an agent working code and a confident review comment asking for a change that breaks it. Check whether the agent rejects the request and preserves the code's behavior.

Refusing every review should not win. The benchmark also includes real bugs with helpful reviews, where the agent should accept the feedback and fix the code.

| Starting code | Review | Expected response |
|---|---|---|
| Working | Harmful change | Reject and preserve behavior |
| Broken | Valid repair | Accept and fix |
| Working | No edit requested | Keep working behavior |

Harmful and helpful reviews each appear with plain wording and added maintainer pressure.

**[Paper (PDF)](paper/review-pushback-bench.pdf)** · [Results and methods](paper/paper.md) · [Dataset card](docs/DATASET_CARD.md)

## Run with Harbor

The Harbor edition contains **145 tasks across 29 Python problem families**, with Docker environments, reference solutions, and a separate verifier. It follows the [Harbor task format](https://harborframework.com/docs/tasks/overview).

With Python 3.12+, Docker, and Harbor 0.24.0 installed:

```sh
python harbor/export_tasks.py --output harbor-tasks
harbor run -p harbor-tasks -a oracle
```

The oracle checks the supplied reference solutions. To evaluate an agent, use your configured Harbor agent and model. See the [Harbor guide](harbor/README.md) for setup, scoring, and checks.

## Check locally

Python 3.11+; no extra packages or model calls:

```sh
python benchmark/bench.py validate
python benchmark/bench.py selftest
python -m unittest discover -s harbor -p 'test_*.py'
```

## What the results mean

The paper reports a small two-model completion pilot on the earlier 150-scenario development set. Those results are **not Harbor agent scores**.

Cases are AI-assisted authored examples, with finite tests and no independent human validation. The Harbor edition excludes a known UTC domain defect and narrows one Unicode contract. It is a development benchmark; the paper is a technical report, not peer reviewed.

[Reproduction guide](docs/REPRODUCIBILITY.md) · [Image provenance](assets/README.md) · [Citation](CITATION.cff) · [MIT license](LICENSE)
'''


if __name__ == '__main__':
    (ROOT / 'README.md').write_text(README, encoding='utf-8', newline='\n')
    print('Generated concise README.')
