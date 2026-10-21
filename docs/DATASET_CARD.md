# Dataset card

Version 0.5 adds a separate [repository tier](../repository/README.md): 20 cases from five pinned Python projects, exported as 80 staged Harbor tasks. Source provenance is in [sources.json](../repository/sources.json). The code is upstream; comments, mutations, and tests are benchmark-authored. All 20 cases await independent human validation. There is no private holdout. The earlier authored tier described below remains available and retains its original pilot records.

## Purpose and release status

Review Pushback Bench measures how a coding system responds to technically incorrect and correct code-review feedback. It tests whether the final program meets a supplied contract, and whether the system's accept/reject decision agrees with that contract.

This is an authored development set and methodology release. It is not a private held-out leaderboard. The `benchmark/cases.py` evaluator source and its answer labels are public. The intended evaluation exposes only an exported task or a restricted prepared workspace to the system being tested.

The v0.2.0-dev release contains 30 problem families and 150 scenarios, confirmed by executable fixture validation. A family contributes five related scenarios: harmful/plain, harmful/authority, valid/plain, valid/authority, and neutral. Thirty families mean at most 30 problem clusters, not 150 independent problems. The first model pilot's primary analysis excludes the `utc-instant` family after a pre-outcome contract audit, leaving 29 families and 145 scenarios per model; all 150 raw attempts are retained.

Known issue: `utc-instant` omits the requirement that UTC conversion remain inside Python datetime's representable range. All authored checks use representable modern dates, so passing those checks does not cover the full frozen contract. The audit exclusion is documented in `artifacts/primary-analysis-plan.json`; a contract repair belongs in a new dataset version.

A later AI-assisted review, after model outcomes were inspected, found that `query-encoding` says arbitrary Unicode strings while Python's `urlencode` rejects lone surrogates. Its current witnesses use UTF-8-encodable strings. This caveat is disclosed without retrospectively changing the recorded primary cohort; the Harbor edition restricts that input domain. The primary cohort is not claimed to have exhaustive domain validation.

## Contents

Each family contains an explicit Python API contract, a correct implementation, one harmful source mutation, a plausible incorrect review asking for that mutation, a valid review asking to repair the mutant, visible checks, evaluator-only checks, and a behavioral witness.

The harmful and neutral arms start with code passing all authored checks. The valid arm starts with the known mutant and is intentionally wrong on evaluator-only inputs. Every arm in a family has the same visible checks. Authority variants prepend a claimed maintainer role and approval pressure to the same technical request.

Exports contain task IDs, source files, the contract, visible tests, a review comment, and the prompt. They omit arm labels, expected decisions, evaluator-only tests, and the alternative implementation. IDs are deterministic hashes, not a cryptographic protection against access to this repository.

## Provenance and curation

The fixture code, contracts, review comments, and checks were authored for this project with AI assistance. They are not copies or imported slices of SWE-bench, EvalPlus, BigCodeBench, or c-CRAB. Those sources inform evaluation design and related-work discussion. No claim of upstream task coverage, upstream equivalence, or human-mined review authenticity is made.

The release process uses executable validation of the correct implementation and the specific mutant, plus AI-assisted review of artifacts. Automated checking and multiple AI agents do not constitute independent human annotation. This release has no human inter-annotator agreement measurement or independently validated private split.

The code and authored fixture data are distributed under the repository's MIT license. External papers, upstream datasets, and linked repositories retain their own rights. Artwork provenance and any separate artwork terms are documented with the asset; do not assume that an external source's license applies to this dataset.

## Intended uses

- Developing and auditing model or agent adapters.
- Diagnosing review-induced regressions and excessive rejection of valid feedback.
- Studying how matched prompt wording and reviewer authority affect outcomes.
- Building larger, independently audited repository-level evaluations.

Results must identify the exact dataset version, exported task hash, model and serving provider, agent harness, tools, generation settings, budgets, repetitions, parsing policy, and missing responses.

## Interpretation limits

The initial tasks are single-module Python with explicit requirements. They are easier to inspect than many real pull requests. The review comments are authored examples of mistaken reasoning, not a representative sample of human review. There are no real repository histories or longitudinal agent workflows in the authored development tier.

Final correctness on finite checks does not prove full semantic correctness. A model might preserve correct code without understanding the review, repair the valid twin by recognizing a familiar pattern, or learn stylistic cues in the authored comments. Neutral preservation is not a pre-feedback demonstration of knowledge. A measured regression does not by itself establish sycophancy as the cause.

The metric called calibrated balance checks a decision label and executable behavior. It does not automatically validate the explanation, claimed tool use, or quality of a counterexample. Those require separate trace or human review. Synthetic no-op, compliance, and answer-key policies are harness sanity checks, not model evaluations.

Do not infer frontier-model behavior from smaller-model failures, or a broad ranking from this development set. Split future datasets by family and upstream lineage rather than paraphrase. Report uncertainty at the family level and keep direct-completion and tool-using agent tracks separate.

## Data sensitivity and execution

The authored tasks use synthetic inputs and example domains rather than personal records. Do not add private source, credentials, production data, or identifying review histories without a separate data-governance process.

Grading executes candidate Python. The built-in subprocess, isolated import mode, filtered environment, timeout, and completion marker are reliability checks, not a security sandbox. Candidates can still access host capabilities or interfere with the test process. Evaluate unreviewed code inside a disposable sandbox without credentials, host mounts, or network access. The public CI only executes the repository's authored fixtures and harness tests; it does not accept or grade external candidate code.


## Harbor task edition

Harbor adapter 0.2.0 exports 29 families and 145 scenarios. It excludes `utc-instant`, narrows Unicode, SQL collation, and numeric-version domains, and repairs the escaped duplicate-JSON-key check. These later findings do not change the frozen pilot cohort or its results. See the [Harbor guide](../harbor/README.md) for the exact restrictions and scoring.
