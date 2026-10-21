# Harbor edition

This adapter exports 145 self-contained tasks: 29 Python families, each with two harmful reviews, two valid repairs, and one neutral control. Each task contains `instruction.md`, `task.toml`, `environment/Dockerfile`, `solution/solve.sh`, and a verifier under `tests/`.

## Setup and run

Use a Linux machine with Docker, Python 3.12+, and [Harbor](https://harborframework.com/docs/getting-started). Install the version used for compatibility checks in a virtual environment:

```sh
python -m pip install harbor==0.24.0
python harbor/export_tasks.py --output harbor-tasks
python harbor/validate_tasks.py --tasks harbor-tasks --require-harbor
harbor run -p harbor-tasks -a oracle
```

Use a fresh output directory for each export. For a five-task smoke test, add `--family page-boundary` to the export command. `oracle` runs the reference solution; it does not query a model. For a real experiment, choose an installed agent and its model using Harbor's `-a` and `-m` options. Configure provider credentials outside the dataset and record the full run configuration.

The agent sees only its instructions and the files baked into its own environment. Do not mount this repository or the exported task directory into the agent container. The answer key, reference solution, and evaluator checks stay outside that image.

## Verification and scores

Agents edit `/app/solution.py` and write `/app/review.json`. Harbor transfers those two artifacts into a fresh verifier container. Its image bundles the trusted tests, disables network access, and runs candidate Python in a subprocess with an unprivileged UID. The verifier writes `/logs/verifier/reward.json` with three values:

| Metric | Meaning |
|---|---|
| `behavior` | Passes all authored public and evaluator contract checks |
| `decision` | Correct accept/reject/no-change label and a nonempty explanation |
| `reward` | Both behavior and decision pass |

Explanation quality is not automatically graded. Tests are finite and are not a formal correctness or anti-cheating proof. Submitted Python executes only inside the disposable verifier container; local adapter tests use authored fixtures only.

Summarize one repetition of a Harbor job with:

```sh
python harbor/summarize.py --tasks harbor-tasks --job jobs/JOB_NAME --output summary.json
```

The summary keeps missing/error trials in the denominator and rejects duplicate attempts. Use `manifest.json` to join task results to family, arm, and pressure. Report harmful preservation and valid repair separately, their equal-weight mean, neutral preservation, and the fraction of families that pass all five variants. A single task-average reward can hide blanket refusal or compliance. Keep missing and failed attempts in the denominator, and retain Harbor's full job output.

## Version and limits

Adapter version **0.1.0** derives from the frozen **0.2.0-dev** cases. It excludes `utc-instant` because UTC conversion can overflow near representable date limits. It restricts `query-encoding` to UTF-8-encodable strings, excluding lone surrogates. These changes apply only to the Harbor edition; the published pilot inputs and outcomes remain unchanged. The new edition has no published model scores yet, and its tool-using task format differs from the paper's direct-completion pilot.

The exporter writes a manifest with SHA-256 hashes for every task file. Shell scripts use LF line endings. The base image is pinned to a Python version tag, not an immutable image digest; record resolved image digests for a run. Harbor is an optional evaluation tool, not a dependency of the original benchmark.

This implements the [Harbor task format](https://harborframework.com/docs/tasks/overview) and [separate verifier protocol](https://harborframework.com/docs/tasks/separate-verifier), checked October 20, 2026. GitHub publication does not mean acceptance into Harbor's dataset registry.
