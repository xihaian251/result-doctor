# Result Doctor

Answers one question about a reported ML result: **how did the runs behind it become the printed
number?** Deterministic and evidence-graded. It does not score experiments, and it has no opinion
about whether a paper is trustworthy. It cannot detect cherry-picking or misconduct, and a clean
run certifies nothing - it only means the evidence you supplied was enough for these eight rules.

```text
result-doctor.yml + the project's own artifacts  ->  8-object Bundle  ->  RD001-RD008 findings
```

The bundle holds the eight things an audit needs - reported cells, aggregations, members,
result artifacts, transformations, candidate sets, selection events, comparison sets - and each
rule questions one of them.

## Install

The package is not published to PyPI, so `pip install result-doctor` will not find it. Two routes:

```bash
pip install .                                       # from a checkout of this repository
pip install path/to/result_doctor-<version>-py3-none-any.whl   # from a built wheel
```

Python 3.11 or newer; the only runtime dependency is PyYAML. In both cases the `result-doctor`
command is installed next to the interpreter you installed it with.

## Audit

```bash
result-doctor audit path/to/result-doctor.yml
result-doctor audit path/to/project        # reads exactly project/result-doctor.yml
```

The command never searches for a manifest, and never infers anything from a file, directory, run
or group name. It reads the artifacts the manifest quotes, and only those. Those quoted paths are
resolved relative to the manifest's `root:`, which is itself relative to the directory holding the
manifest - so the audit gives the same findings from any working directory.

```text
# result-doctor audit phase4/rtdl-revisiting-models/result-doctor.yml
RD001   PASS            mlp-tuned/adult
        reason: recomputed rendering equals the reported cell
RD004   INCONCLUSIVE    candidates:cand:adult-epochs
        reason: candidate universe recoverability is UNKNOWN; this is never inferred from the count ...
RD007   NOT_RUN         rule:RD007
        reason: no target of this class was supplied (comparison_sets is empty)

PASS: 6
FAIL: 0
INCONCLUSIVE: 6
NOT_APPLICABLE: 3
NOT_RUN: 1
```

The first line names the manifest that was actually loaded. Findings print in `(rule, target)`
order; the census counts findings and is not a summary judgement - a run with `FAIL: 0` is no more
"clean" than one with `FAIL: 3`.

### Which rule is which

| Rule | Name | What it asks |
| --- | --- | --- |
| `RD001` | Reported-Value Recomputability | can the reported number be recomputed from the declared members and transforms? |
| `RD002` | Aggregation Membership Derivability | is the aggregation membership enumerable, and are exclusions bindable? |
| `RD003` | Selection-Criterion Recoverability | is every selection criterion backed by direct evidence, and was the declared policy followed? |
| `RD004` | Candidate-Set Recoverability | how far can the candidate set be recovered? |
| `RD005` | Spread-Semantics Consistency | what is the published +/- and does it match the project's own wording? |
| `RD006` | Transformation-Chain Auditability | is every step from raw metric to table cell enumerated? |
| `RD007` | Presentation-Dependency Integrity | does the cell's presentation depend on data outside the cell, and is that dependency recomputable? |
| `RD008` | Cross-Artifact Consistency | does the same quantity agree across the products it appears in? |

`target` names the thing under questioning: a reported cell (`mlp-tuned/adult`), or an object of
the class the rule reads, prefixed by its kind (`aggregation:`, `reported:`, `selection:`,
`candidates:`, `quantity:`, `comparison:`). The odd case `rule:RD007` is not a data object - it
means the rule was given no target of its class at all.

## Read the statuses

| Status | Means |
| --- | --- |
| `PASS` | the evidence the manifest supplies decides this target in favour of the report |
| `FAIL` | one rule found an inconsistency in that evidence - not a failed experiment or paper |
| `INCONCLUSIVE` | the evidence on file is insufficient to decide |
| `NOT_APPLICABLE` | this target has no such dependency to check |
| `NOT_RUN` | no target of the class the rule reads was supplied |

`INCONCLUSIVE` and `NOT_RUN` record missing evidence, not a found problem. Most honest audits of a
real repository are mostly `INCONCLUSIVE`; that is the tool refusing to guess, which is the point.

## Exit codes and refusals

```text
0   the audit ran, whatever the rules said
2   the manifest is not a readable contract, or the command line itself was wrong
1   the tool failed unexpectedly
```

A rule saying `FAIL` exits `0`: a finding is not a broken program. A manifest that cannot be read
as a contract stops immediately and prints, unchanged:

```text
{code} at {where}: {problem}
```

The `code` is one of 26 `E_*` authoring codes defined in `src/result_doctor/manifest.py`. The
`where` is a manifest field path such as `reported_results[0]/value/observed`, and `problem` names
the smallest shape that fixes it - so a refusal is actionable without knowing the code list by
heart. Usage errors (a missing `path`, an unknown command) share exit code `2` but print a
`usage:` line instead of an `E_*` code.

## Machine-readable output

```bash
result-doctor audit project/result-doctor.yml --json report.json
```

`--json` is additive: the terminal table still prints. The file path resolves against your working
directory. `report.json` holds every finding with its full evidence list, `rule_name`, `question`,
`measurements` and `reason`, as the canonical JSON line the Python API returns from
`canonical_json(audit_manifest(path))`: fixed order, sorted keys, no timestamps. Two runs on one
manifest are byte-identical.

## Limitations

* Someone has to write `result-doctor.yml`. The tool reads evidence, it does not find it: there is
  no repository scanner, no PDF parser, no W&B/MLflow/Hydra integration.
* An audit covers only what the manifest quotes. Absent object classes print `NOT_RUN`, and the
  tool never upgrades an `unknown:` because surrounding files looked suggestive.
* `result_doctor.loaders` holds two adapters for two frozen research archives from the project's
  own evidence collection. They are not a general API and may change without notice.
* Rules are RD001-RD008 and no more; each questions one object class, not the whole report.

## Writing a manifest

`result-doctor.yml` states, for every printed value, either where the tool can go read it
(`observed:`), or that a named human declared it (`declared:`), or that nobody knows
(`unknown:`). Those three doors are the whole contract, and a `declared:` value never becomes a
fact because the file names it.

* The six authoring notes that prevent the usual mistakes: `src/result_doctor/manifest.py`,
  module docstring.
* A real 98-line manifest over a public repository: `phase4/rtdl-revisiting-models/`.
* The design reasoning behind the contract: `phase2/RESULT_DOCTOR_PHASE2_DESIGN.md`.

This README is a quickstart, not the contract; the phase reports in `phase0`-`phase6` are the
authoritative record of each stage.
