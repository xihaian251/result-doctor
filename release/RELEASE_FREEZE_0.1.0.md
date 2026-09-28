# Result Doctor 0.1.0 - Release Freeze

Round: PyPI recovery + `RESUME_AFTER_PYPI.md` state machine A→L, 2026-09-28.
This file is the authoritative post-release record. Every value below was measured in this session
against the published artifacts, not copied from an earlier report.

State: **RELEASED AND FROZEN.** `v0.1.0` is permanent; it is not to be moved, deleted or re-pointed.

---

## 1. Published identity

```text
Commit (what the code is)      bec3ab98e5289d4739d57c34413a7a4d2b687da0   (unchanged from staging)
Annotated tag object           5b87cbae38240d6480dcd26beacfa6dfa5349add  ->  peel: bec3ab9
Tag subject                    "Result Doctor 0.1.0"
GitHub release                 https://github.com/xihaian251/result-doctor/releases/tag/v0.1.0
  release id 398295197 · draft false · prerelease false · target_commitish bec3ab9
  published_at 2026-09-28T13:48:33Z
Publish run (the trigger)      36431268406  "Publish to PyPI"  completed / success  event=release
PyPI project                   https://pypi.org/project/result-doctor/
PyPI release                   https://pypi.org/project/result-doctor/0.1.0/
Source repo                    https://github.com/xihaian251/result-doctor  (public, default main)
```

The tag pointed at `bec3ab9` **before** this session resumed: step B found `v0.1.0` already created
(2026-09-28 21:19:37 +0800) and already on the remote, peeling to the frozen commit. It was therefore
not re-created, and it has not been moved. Steps C and D were satisfied by existing state rather than
duplicated.

## 2. PyPI artifacts - PYPI VERIFIED

Downloaded from `files.pythonhosted.org`, digests re-computed locally and compared against the PyPI
JSON API. Both matched, so these are published identities, not staging guesses.

```text
result_doctor-0.1.0-py3-none-any.whl   57,593 B
  sha256 54b3ddd9a9831cbf08ce4ec0ce2e172eb061ba5ae58121048234c229281038fe   bdist_wheel 13:49:01Z
result_doctor-0.1.0.tar.gz             78,008 B
  sha256 e054b57cf1c3f12e41d7d28c1e7567e6b0368fa18033be1f1d630e845d2a7343   sdist        13:49:02Z

Published wheel METADATA: Name result-doctor · Version 0.1.0 · License-Expression Apache-2.0 ·
  License-File LICENSE · Requires-Python >=3.11 · 20 members · no .git / venv / egg-info member ·
  licenses/LICENSE present inside the wheel.
```

## 3. Staged vs published hashes reconciled (this is the part that must not be misread)

The staged build (Windows, clean worktree) and the CI build (ubuntu, from the tag) produced different
archive bytes. That is expected, and it was verified rather than assumed:

```text
sdist    34/34 files byte-identical after newline normalisation   -> no content difference at all
wheel    20 members, same member set in both
         only METADATA differed: staged 13 CRLF line endings vs published 0  (generated file written
           in text mode; line-level diff is empty)
         RECORD differs solely because it hashes that METADATA (self-referential manifest)
         -> all 18 real payload modules byte-identical
```

So the three staged/published hash pairs are the **same content** under two build-time encodings.
The PyPI hashes in §2 are the published identity going forward; `release/SHA256SUMS` now carries both,
labelled. Anyone reproducing a build on Windows will get the staged-style bytes again.

## 4. Fresh install from PyPI (brand-new venv, never used for staging)

```text
F:/MLResearch/.rd-verify/pypi-venv   CPython 3.13.1 win-amd64
pip install result-doctor==0.1.0  ->  Successfully installed PyYAML-6.0.3 result-doctor-0.1.0
pip check                          ->  No broken requirements found.
result-doctor --version            ->  result-doctor 0.1.0
result_doctor.__version__          ->  0.1.0
result_doctor.__file__             ->  ...\pypi-venv\Lib\site-packages\result_doctor\__init__.py
result-doctor --help               ->  usage: result-doctor [-h] [--version] {audit} ...
```

## 5. Real pilot audit from the PyPI install (science unchanged)

Pinned pilot rebuilt per `phase4/PILOT_CHECKOUT.md` at `e3ed46cac38568785289d8fa16b8cfa585bde27e`
(`tar --exclude .git`), then audited with the **PyPI-installed** CLI:

```text
findings 16 | PASS 6 | FAIL 0 | INCONCLUSIVE 6 | NOT_APPLICABLE 3 | NOT_RUN 1   exit 0
--json    13,395 B, 0 CR bytes
sha256    2ad02c8fb6ace0af325c2bc50c08eb9f0162e77b25c659e96951df96f694a660
```

That JSON hash equals the Phase 6 frozen report and equals what both staged artifacts produced.
**Zero scientific drift across the publish boundary; no rule, schema or manifest semantics were
touched to get there.**

## 6. Quality gates on the released commit

CI run 36405342890 and the tag-push run 36427861659 both `completed / success` for
`gates (3.11)` and `gates (3.13)`. Locally on the clean checkout of the same commit:
170 passed (pilot present, no extra skips) · ruff `All checks passed!` · `28 files already formatted`
· mypy `Success: no issues found in 14 source files`.

## 7. Defect ledger at release time

```text
P0  0
P1  0 project defects. The one outstanding item (PyPI pending trusted publisher) was closed by the
    account owner and is no longer open.
P2  3 - unchanged, deliberately NOT fixed in a release round:
      (1) four sdist test files carry F:\MLResearch default paths,
      (2) sdist ships tests/ but not tests/generic_fixtures,
      (3) table layout degrades on width-less terminals.
P3  5 - unchanged: egg-info inside sdist · CHANGELOG not in sdist · `pip show` legacy License field
      empty while License-Expression carries the value · README's internal phase-report pointer ·
      PILOT_CHECKOUT.md calls the local dir a ~13 MB sparse checkout while the recipe yields ~167 MB.
```

## 8. Two facts a future reader should not lose

- **Commit/tag authorship is public.** `bec3ab9` was authored with the machine's default git identity
  (`beihai <3796320131@qq.com>`), and the annotated tag carries the same address. Fixing either would
  require rewriting published history and moving a released tag - both forbidden. Observation, not defect.
- One credential-hygiene item from an earlier round is still open. It is deliberately recorded in a
  local note rather than in this published file; the affected credential should be rotated.

## 9. Workspace cleanup

```text
Staging worktree   F:/MLResearch/.rd-staging/bec3ab9   (167 MB materialised pilot + staged dist/)
Verify venv        F:/MLResearch/.rd-verify/            (pypi-venv, downloaded artifacts, report json)
Pilot .git backup  F:/MLResearch/result-doctor-pilot-git-backup/git
Remove with:
  git -C F:/MLResearch/result-doctor worktree remove F:/MLResearch/.rd-staging/bec3ab9
  rm -rf F:/MLResearch/.rd-staging F:/MLResearch/.rd-verify
```

## 10. What is explicitly NOT happening next

0.1.0 is the release. No 0.1.1, no P2/P3 sweep, no v1.0 work, no Paper Doctor. Any further change to
this repository requires a new version and a new round.
