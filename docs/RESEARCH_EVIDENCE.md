# Release evidence ledger

This ledger supports the paper and README; it distinguishes measurements from interpretation. Source and output hashes are in research.json.

<!-- claim:related-sharma2023sycophancy -->

The paper uses sharma2023sycophancy as a design or related-work source: Definition of sycophancy; not new measurements of code review.

<!-- claim:related-jimenez2024swebench -->

The paper uses jimenez2024swebench as a design or related-work source: Repository issue-resolution task structure.

<!-- claim:related-liu2023evalplus -->

The paper uses liu2023evalplus as a design or related-work source: Motivation for discriminative executable checks.

<!-- claim:related-zhuo2024bigcodebench -->

The paper uses zhuo2024bigcodebench as a design or related-work source: Motivation for API-semantics task scope.

<!-- claim:related-jain2024livecodebench -->

The paper uses jain2024livecodebench as a design or related-work source: Temporal collection and separation of code capabilities.

<!-- claim:related-zhang2026ccrab -->

The paper uses zhang2026ccrab as a design or related-work source: Executable evaluation of review consequences; distinction in evaluated role.

<!-- claim:related-hong2025sycon -->

The paper uses hong2025sycon as a design or related-work source: Multi-turn pressure evaluation as a related and separate protocol.

<!-- claim:related-harbor-format -->

The paper uses harbor-format as a design or related-work source: Self-contained task format and reward file convention.

<!-- claim:dataset-validation -->

The frozen v0.2.0-dev development set has 30 authored families and 150 scenarios. All correct references pass authored visible/evaluator checks; all intended mutants pass visible checks and fail evaluator checks.

<!-- claim:policy-controls -->

Synthetic no-op and blind compliance score 0.5 balanced behavior and zero paired-family success; the answer-key policy scores 1.0. These are not model measurements.

<!-- claim:release-checks -->

Local harness, adapter, canonical-grading, pipeline, and release-integrity checks pass.

<!-- claim:primary-exclusion -->

The primary pilot cohort excludes utc-instant and contains 29 families / 145 scenarios per model; the declaration predates model score inspection and all 150 raw attempts per model are retained.

<!-- claim:flash25-pilot -->

gemini-2.5-flash returned 148/150 valid-format responses. On the primary 145 scenarios its strict decision-label agreement is 0.910344827586; harmful responses match the validated correct-reference AST in 56/58 cases. Balanced reference-test agreement is bounded by 0.801724137931 and 0.974137931034 under conservative matching.

<!-- claim:lite35-pilot -->

gemini-3.5-flash-lite returned 150/150 valid-format responses. On the primary 145 scenarios its strict decision-label agreement is 0.972413793103; harmful responses match the validated correct-reference AST in 58/58 cases. Balanced reference-test agreement is bounded by 0.844827586207 and 1.000000000000 under conservative matching.

<!-- claim:interpretation -->

This is an open development benchmark and methodology report with a small direct-completion pilot; it does not establish causal sycophancy, representative real-review failure rates, or a frontier-model ranking.
