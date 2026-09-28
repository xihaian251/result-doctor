# Changelog

## 0.1.0

First public candidate. Everything below exists and is tested; nothing else does.

* **Evidence manifest** - `result-doctor.yml` states, per printed value, where the tool can read it
  (`observed:`), that a named human declared it (`declared:`), or that nobody knows (`unknown:`).
  A manifest that is not a readable contract is refused with one of 26 `E_*` codes, a field path,
  and the smallest fix.
* **8-object evidence model** - reported cells, aggregations, members, result artifacts,
  transformations, candidate sets, selection events, comparison sets.
* **RD001-RD008** - eight rules, one per evidence question, each reporting per target as
  `PASS | FAIL | INCONCLUSIVE | NOT_APPLICABLE | NOT_RUN`. No overall score, no verdict.
* **Partial-audit discipline** - an unknown stays unknown; a missing object class reports `NOT_RUN`
  rather than a default; a `declared:` value is never promoted to a fact.
* **CLI** - `result-doctor audit PATH` prints the findings in `(rule, target)` order with a status
  census, and `--json` writes the canonical JSON line the Python API returns: fixed order, sorted
  keys, no timestamps, byte-identical across runs. Exit `0` whenever the audit ran, `2` for an
  unreadable manifest, `1` for a tool failure.
* **Packaging** - Python >= 3.11, one runtime dependency (PyYAML), console script
  `result-doctor`, importable package `result_doctor`.
* **Validated on** - one real public ML repository through a hand-written 98-line manifest
  (16 findings), plus two frozen research archives through project-specific loaders.
