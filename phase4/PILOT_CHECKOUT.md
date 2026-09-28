# Phase 4 pilot checkout - how to rebuild it

`phase4/rtdl-revisiting-models/` is a **sparse checkout of the upstream research repository**
`yandex-research/rtdl-revisiting-models` pinned to commit

```text
e3ed46cac38568785289d8fa16b8cfa585bde27e   (Wed Nov 13 00:04:04 2024 +0300)
```

It is ~13 MB of other people's code and result files, so it is **not** re-vendored into this
repository (`.gitignore` excludes it). Only the two files that this project authored stay tracked:

```text
phase4/rtdl-revisiting-models/result-doctor.yml    the 98-line evidence manifest
phase4/rtdl-revisiting-models/EVIDENCE_NOTES.md    the field-by-field evidence worksheet
```

Everything those two files quote - `README.md`, `bin/mlp.py`, `bin/tune.py`, `lib/deep.py`,
`lib/util.py`, and the `output/**/stats.json` run results - comes from upstream at the pin above.
Upstream tracks 9,134 files under `output/`, so the audit is reproducible from a clone; nothing here
was produced by retraining.

## Rebuild (same recipe CI uses)

```bash
git clone https://github.com/yandex-research/rtdl-revisiting-models.git /tmp/rtdl-pilot
git -C /tmp/rtdl-pilot checkout e3ed46cac38568785289d8fa16b8cfa585bde27e
mkdir -p phase4/rtdl-revisiting-models
tar -C /tmp/rtdl-pilot --exclude .git -cf - . | tar -C phase4/rtdl-revisiting-models -xf -
```

Copy everything *except* upstream's `.git`. Git will not track files that live inside another
repository's working tree, so leaving upstream's `.git` in place would silently push our two tracked
files out of this repository's version control.

Then the frozen acceptance runs for real instead of skipping:

```bash
result-doctor audit phase4/rtdl-revisiting-models/result-doctor.yml
# 16 findings: PASS 6 / FAIL 0 / INCONCLUSIVE 6 / NOT_APPLICABLE 3 / NOT_RUN 1
```

Without that directory, `tests/test_cli.py` skips the pilot case (and `pytest` stays green), and every
other gate in this repository is independent of it.

## What the sparse checkout kept locally

```text
README.md
bin/mlp.py
bin/tune.py
lib/deep.py
lib/util.py
output/adult/mlp
output/aloi/mlp
output/california_housing/mlp
```

The upstream `LICENSE` applies to that content, not to this repository's code; it is intentionally not
copied here, and reading it is part of the clone step above.
