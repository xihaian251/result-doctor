Result Doctor 0.1.0

## What it does

Audits how the runs behind a reported ML result became the printed number. Deterministic,
evidence-graded, no score.

- generic `result-doctor.yml` evidence manifest: every printed value is `observed:` (the tool can go
  read it), `declared:` (a named human said so), or `unknown:` (nobody knows). A manifest path that
  is not a readable contract stops with an `E_*` code and the field path to fix.
- rules `RD001`-`RD008`, one per question about the eight-object bundle: reported-value
  recomputability, aggregation membership, selection criterion, candidate set, spread semantics,
  transformation chain, presentation dependency, cross-artifact consistency.
- five statuses: `PASS` / `FAIL` / `INCONCLUSIVE` / `NOT_APPLICABLE` / `NOT_RUN`.
- partial audit is a first-class result: `INCONCLUSIVE` and `NOT_RUN` record missing evidence, not a
  found problem. Most honest audits of a real repository are mostly `INCONCLUSIVE`.
- deterministic JSON: `canonical_json` with fixed order, sorted keys, no timestamps - two runs on one
  manifest are byte-identical.
- CLI: `result-doctor audit <manifest-or-project-dir> [--json out.json]`.
  Exit 0 = the audit ran whatever it found; 2 = the manifest is not a readable contract; 1 = the tool
  failed unexpectedly.
- validated on one real public repository (98-line manifest, 16 findings) plus two frozen archives,
  and by a first-time user on a machine that had never seen the project.

## Known boundaries

- does not certify an entire paper, and the census is not a verdict;
- does not detect misconduct or cherry-picking;
- does not infer missing provenance - it reports what the evidence on file cannot decide;
- `UNKNOWN` and `INCONCLUSIVE` are intentional outcomes, not bugs.

## Install

```bash
pip install result-doctor        # Python >= 3.11, only runtime dependency is PyYAML
```

## Basic use

```bash
result-doctor audit path/to/project          # reads exactly project/result-doctor.yml
result-doctor audit path/to/result-doctor.yml --json report.json
result-doctor --help
```

Source, phase reports and the manifest contract: https://github.com/xihaian251/result-doctor
License: Apache-2.0.
