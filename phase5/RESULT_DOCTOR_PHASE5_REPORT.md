# Result Doctor Phase 5 — Generic UX Simplification

冻结状态：Phase 0/1/2/3/4 全部 CLOSED。本轮唯一授权范围：UX1（成员 identity 重复）、UX2（`_size`
companion 写法）、G1 与 G2 两类静默误判、以及 §12 三条错误文本 + §13 最小使用说明。
验收物唯一：Phase 4 的真实项目 `yandex-research/rtdl-revisiting-models`（commit `e3ed46c`）。

---

## 1. Executive result

| 判据 | 结果 |
|---|---|
| Phase 4 manifest 逻辑行 | **110 → 98**（−12，−10.9%），达到 ≤100 |
| 删除的 evidence / member / UNKNOWN / SourceRef | **0**（grade 普查前后完全相同：DIRECT 69 / DECLARED 7 / UNKNOWN 17） |
| schema 改动 | 0（`schema.py` 未触碰） |
| RD001–RD008 语义改动 | 0（`rules.py`/`compute.py`/`status.py` 未触碰） |
| 新增自动发现 | 0（无 glob / 目录扫描 / 通配成员 / 自动 seed / 自动行身份） |
| 新增错误码 | 0（26 码冻结集合仍是 26 码，见 `test_the_error_vocabulary_is_exactly_the_documented_one`） |
| 成员 identity 语法糖 | 生效，且与显式写 identity 的 Bundle **逐字段等价** |
| `_size` companion 写法 | 生效，旧合法写法继续可用且 lowering 结果不变 |
| G1（整行 ⇒ 假 RD001/RD006 FAIL） | 覆盖用例已不可能静默发生：加载期 `E_LOCATOR_TEXT` |
| G2（quantity 缺行身份 ⇒ 假 RD008 FAIL） | 覆盖用例已不可能静默发生：加载期 `E_MISSING_FIELD` |
| 旧 manifest 仍可用 | 是（110 行快照加载成功，16 条 finding 状态向量与 Phase 4 完全一致） |
| 科学结论等价 | 16/16 状态一致；8 对象 38 个实例中**只有 1 个字段**不同，且该差异是「多了一条被旧写法丢掉的 provenance 文本」 |
| 门禁 | pytest **161 passed**（148 + 13 新增）、Phase 1 子集 76 passed、ruff check 绿、`ruff format --check` 绿、mypy 绿 |
| Blockers | **0** |

一句话：manifest 变短了、更难写错，但**一点都不更会猜** —— 两处新校验都是拒绝，不是补全。

### 改动清单（全部改动，无遗漏）

| 文件 | 改动 |
|---|---|
| `src/result_doctor/manifest.py` | 5 处：`_Manifest.__init__` 加 `self.quantities`；`_size` companion 识别（UX2）；`_size` 缺 `value` 的定向错误文本；`_cell_field` G1 守卫；`_inherit_member_path` + `_members` 一处调用（UX1）；`_check_quantity_identity` + `_cells` 一处调用（G2）；模块 docstring 增加 §13 六条作者面说明 |
| `tests/test_phase5_ux.py` | 新增，13 个用例（T1–T6） |
| `pyproject.toml` | `[tool.ruff] extend-exclude` 增加 `"phase*"`（见 §10 说明） |
| `phase4/rtdl-revisiting-models/result-doctor.yml` | 110 → 98 逻辑行（本轮验收物） |
| `phase5/rtdl-revisiting-models/result-doctor.phase4-before.yml` | 新增：Phase 4 manifest 原样快照（仅 `root:` 改为指向试点 checkout），供 T2/T6 对照 |
| `phase5/trapcheck/g1.yml`、`g2.yml` | 新增：两个静默误判在真实项目上的复现物（现均为加载期拒绝） |
| `phase5/RESULT_DOCTOR_PHASE5_REPORT.md` | 本报告 |

**未改动**：`schema.py`、`rules.py`、`status.py`、`compute.py`、`evidence.py`、`bundle.py`、`audit.py`、
两个冻结 adapter loader（`loaders/gmmvi.py`、`loaders/torchssl.py`）、`tests/` 下任何既有用例与 fixture。
Phase 5 未新增 `loaders/<project>.py`，未新增错误码，未新增 locator family。

---

## 2. Phase 4 摩擦的处置对照

| Phase 4 实测摩擦 | 本轮处置 | 证据 |
|---|---|---|
| 30 个成员的路径被写两遍（`path:` 出现 73 次，其中 60 次是成员身份重复） | UX1：identity 门内可省 `path:`，确定性地读成员自身文件 | `path:` 73 → **43**（正好少 30）；成员行均长 233 → **182** 字符 |
| `_size` 外层 `{value, statement}` 与门内形状互不可见，带 `note` 直接 `E_BAD_FIELD`（B1/G4） | UX2：`note` / `supported_by` / `via` 识别为 companion，不再是「第二扇门」 | `declared_size` 5 行 → 1 行；`surviving_size` 不再需要把 `1` 写两遍 |
| `{path, line}` 读回整行 ⇒ `reported_center='adult   0.852'` ⇒ RD001 假 FAIL + RD006 假 INCONCLUSIVE | G1：打印单元格的 value 定位符缺 `text:` ⇒ 加载期拒绝，并给最小期望形状 | §4 |
| `quantity` 不带行身份 ⇒ 两行进同一 RD008 locus ⇒ 假 FAIL | G2：同一 quantity key 被同一 (artifact, table) 的两个 cell 声明 ⇒ 加载期拒绝 | §5 |
| 错误文本只说 `E_BAD_FIELD`，不说哪一栏、为什么、期望什么 | §12 三条文本重写（G1、G2、尺寸缺 `value`） | §6 |
| 文档没有「aggregate vs cell-level」「行 vs 片段」「quantity 行身份」的说明 | §13：`manifest.py` 模块 docstring 增加 6 条作者面说明（约 20 行，非教程） | §7 |

未处置（明确保持登记）：G3–G9 中除 G1/G2/G4 之外的全部条目，见 §11。

---

## 3. 已实现的作者面语法糖

### 3.1 UX1：成员 identity 的路径继承

`src/result_doctor/manifest.py::_inherit_member_path`（+ `_members` 一处调用）：

```yaml
# 之前：同一个文件路径写两遍
- {name: seed-0, path: output/adult/mlp/tuned/0/stats.json, key: /metrics/test/score,
   identity: {observed: {path: output/adult/mlp/tuned/0/stats.json, key: /config/seed}}, ...}
# 之后：identity 门内不再重复 path
- {name: seed-0, path: output/adult/mlp/tuned/0/stats.json, key: /metrics/test/score,
   identity: {observed: {key: /config/seed}}, ...}
```

规则（全部可确定，无推断）：

- 仅当 identity 的**门体内部**（`observed:` / `declared:` / `supported_by:`）没有 `path:`
  但带了其它定位键（`column/row/key/line/text`）时，才补成员自己的 `path:`；
- `unknown:` 永不补（缺身份就是缺身份）；成员本身没有 `path:`（inline `value:` 成员）时不补，
  于是照旧走 `read_locator` 的 `E_MISSING_FIELD`；
- 不从目录名/文件名读任何科学语义；补的只是一个已经写在同一行的文件引用。

**等价性是被测出来的，不是被论证的**：`test_an_identity_without_a_path_is_read_against_the_members_own_file`
比较 identity 的 `value / grade / SourceRef(path,line,key,note)` 四元组与 `evaluate()` 全量 finding 的
`canonical_json`，显式写法与糖衣写法完全相同；真实 manifest 的 30 个成员在前后两版 Bundle 中逐字段一致。

### 3.2 与简报 §1 字面表述的偏差（必须记录）

简报 §1 写的字面方向是「identity omitted → deterministically use the member's own file」，
即**整条 `identity:` 键可以省略**。本轮**没有**实现这个字面语义，原因是一条 Phase 3 已冻结的防火墙断言：

```text
tests/test_generic_firewall.py::test_row4_a_file_name_carries_no_provenance
    assert member.run_ref.external_id.grade is Grade.UNKNOWN
```

该用例的成员带 `path:` 而不写 `identity:`。若「省略 identity 就默认取自身文件」，这条断言会翻成
DIRECT —— 那正是简报 §9「不能因为'默认'就变成 DIRECT」和 §10「不新增自动发现」禁止的事，
也是 Phase 1 §8「文件名不携带 provenance」纪律的本体。

因此本轮实现的是**同一目标的最弱安全形式**：重复声明可以省，显式声明不能省。
可省的是「把已经写过的路径再抄一遍」，不可省的是「声明这个成员有身份」这个动作本身。
G3（成员身份完全默认化）继续保持登记状态，未被本轮悄悄解决。

### 3.3 UX2：`_size` 的 companion 写法

`_size` 现在接受 `{value, statement, note?, supported_by?, via?}`：companion 键描述那个数字，不再被
`door_of` 误当成「一扇非空的门」（Phase 4 B1 的根因）。缺门时确定性合成 `declared:` 体，
grade 仍是 DECLARED，绝不升级。旧的两类合法写法（`{value, statement}` 与显式门 + `supported_by`）
保持原语义，`test_the_old_size_doors_still_mean_the_same_thing` 钉住了这点。
`_size` 未被扩成通用 metadata object：只有 `value` 是数字，其余仍是既有 companion。

---

## 4. G1：整行文本 ⇒ 假 FAIL，已被前移为作者错误

`_cell_field` 在把 `value:` 交给通用 `field()` 之前加一条判定：门体是 mapping、含 `line`、且不含
`text` ⇒ 直接拒绝。真实项目上的复现物留在 `phase5/trapcheck/g1.yml`（把最终 manifest 的第 1 个 cell
的 value 改回整行写法），现在加载即报：

```text
E_LOCATOR_TEXT at reported_results[0]/value/observed: a printed cell is one fragment, not the whole
line it sits on: add text: "<the printed value>" to {path: 'README.md', line: 80}. Without it the row
label would enter the recomputation comparison.
```

三条要求逐条满足：说清哪一栏（`reported_results[0]/value/observed`）、为什么（行标签会进入重算比较）、
最小期望形状（`text: "<the printed value>"` + 原 `{path, line}`）。

**没有做的事**：不 regex 找数字、不猜哪个数字是 reported value、不新增 substring/regex locator、
不在读不到时降级为 PASS 或 INCONCLUSIVE。工具依旧只会读整行或读被引用的片段，只是不再允许
「把整行当成一个打印数值」这种语义误用。`{path, line}` 在 `wording:`、`supported_by:` 等
需要整行文本的地方继续正常工作（G1 只作用于打印单元格）。

---

## 5. G2：quantity 缺行身份 ⇒ 假 RD008 FAIL，已被前移为作者错误

`_check_quantity_identity`（由 `_cells` 在 `bundle.add` 之前调用）：非空 `quantity` key 一旦被
同一 `(artifact, table)` 的两个 cell 声明 ⇒ 拒绝。RD008 的分组键就是 `locus.quantity_key` 本身
（`rules.py::rd008`：`groups.setdefault(key, ...)`），所以两行共用一个 key 必然被读成
「同一个量在两个产物里印成两个值」。复现物 `phase5/trapcheck/g2.yml`（把两个 cell 的 key 都改回
`metrics.test.score`）现在加载即报：

```text
E_MISSING_FIELD at reported_results[1]/quantity: quantity 'metrics.test.score' is claimed by two cells
of README.md (table README metrics snippet), row 'adult' and row 'california_housing'. RD008 groups
cells by quantity key alone, so it would compare those two rows and report the difference as a
conflict. Make the key identify one cell, e.g. metrics.test.score/california_housing.
```

边界（刻意的，防过严）：

- **跨产物同 key 仍然合法** —— 那正是 RD008 要审的东西；`test_row_scoped_quantities_load_and_a_cross_product_key_is_still_allowed`
  用 `artifact: ckpt/r1/val.json` 与 `paper/t.txt` 共用 `acc` 钉住这一侧；
- `quantity` 缺省（空 key）不报错，RD008 自己按既有逻辑跳过空键 ⇒ 保持 UNKNOWN/NOT_RUN 的 audit 路径不变；
- **RD008 内部零改动**：不猜 dataset、不从 path 补 row、不从 metric 名猜 locus。修的是作者面，不是规则。

§15 的分区没有被破坏：本轮新增的两条拒绝都是 authoring invalid（结构不充分的定位符 / 不唯一的行身份），
`universe unknown`、`selection policy unknown`、`comparison artifact inaccessible` 依旧照常进入 audit
并给出 INCONCLUSIVE / NOT_RUN —— 16 条 finding 的向量与 Phase 4 完全一致就是这一条的证据。

---

## 6. Manifest before / after（§7 统计纪律）

逻辑行方法沿用 Phase 4：文件总行 − 纯注释行 − 空行。

| | before（Phase 4 原样） | after（Phase 5 简化） |
|---|---|---|
| 文件总行数 | 118 | 105 |
| 纯注释 / 空行 | 1 / 7 | 1 / 6 |
| **逻辑行数** | **110** | **98** |
| `path:` 出现次数 | 73 | **43** |
| 成员行平均字符 | 233 | **182** |
| 最长一行字符 | 247 | **207** |
| 引用的不同文件 | 34 | 34（未变） |
| 成员数 / cell 数 / UNKNOWN 字段数 | 30 / 2 / 17 | 30 / 2 / 17 |

分节归因（每一个减掉的行都能指认来源）：

| section | before | after | Δ | 来自 |
|---|---|---|---|---|
| header | 3 | 3 | 0 | — |
| evidence | 7 | 6 | −1 | 删掉 `value: best`：它与 30 个成员各自写的 `kind: best` 是同一个事实的第三次书写；Bundle 内该字段的 value 由 statement 提供、grade 不变（69/7/17 普查不变即为证） |
| transformations | 10 | 5 | −5 | **纯排版**：单步 `format` 链由 6 行 block 改成 1 行 flow，与本文件 30 个成员、`printed_in`、`criterion` 一直在用的 flow 风格一致 |
| candidate_sets | 15 | 11 | −4 | **UX2**：`declared_size` 由「外层 value/statement + 门内再写一遍 + supported_by」5 行合成 1 行；`surviving_size` 不再需要把数字 `1` 写两遍（行数不变，去掉一次重复声明） |
| selection_events | 23 | 23 | 0 | 未动 |
| reported_results | 52 | 50 | −2 | **纯排版**：两个 `aggregate:` 由 2 行改 1 行 flow |
| 合计 | **110** | **98** | **−12** | 语法糖 5 行（UX2 4 + 去重 1）、排版 7 行、**删除的 evidence 0** |

诚实结论：`≤100` 是「4 行语法糖 + 1 行去重 + 7 行排版」换来的，其中 30 行成员枚举**一行都没有少**，
因为消除它只能靠通配/目录扫描，而那被 §10 禁止。若不允许排版折算，纯语法糖只到 105 行。
这条 measurement 本身就是下一轮判断依据：**YAML 已经不是主要成本，重复枚举才是**。

未作弊声明：成员 30→30、cell 2→2、`unknown:` 17→17、SourceRef 逐字段（除 §8 那 1 处新增文本）不变、
`evidence:` 条目 1→1、`comparisons:` 依旧不写（RD007 依旧 NOT_RUN）。

---

## 7. Bundle 与科学结论等价性（§8）

对照对象：`phase5/rtdl-revisiting-models/result-doctor.phase4-before.yml`（Phase 4 manifest 原样快照，
仅 `root:` 指向试点 checkout）与 `phase4/rtdl-revisiting-models/result-doctor.yml`（简化版）。

- 8 对象 populations：`reported_results 2 / aggregations 2 / members 30 / artifacts 0 / transformations 1 /
  candidate_sets 2 / selection_events 2 / comparison_sets 0` —— **两侧完全相同**；
- 成员事实（identity 值、selector kind、observed value、artifact_ref）：相同；
- cell 事实（value、spread、quantity key、aggregation_ref、transformation_refs、selection_refs）：相同；
- transformations / candidate_sets / selection_events：相同；
- **逐字段 diff 全量结果：38 个对象实例中只有 1 个字段不同**：

```text
candidate_sets[cand:adult-tuning-trials].surviving_size.sources
  before: SourceRef(note="")                                     # 旧门 workaround 把句子里多写的说明丢掉了
  after:  SourceRef(note="only best.toml is kept in the repository")
```

方向是 provenance **增加**：Phase 4 那句「仓库里只留下 best.toml」写在 `declared.statement` 里，
经 `field()/_declared()` lowering 后根本没进 Bundle；UX2 之后它作为 companion `note` 正常落地。
因此本轮不存在任何静默的语义缩减。

- `audit_manifest()` 16 条 finding：状态向量与 Phase 4 记录的 16 条**逐 target 相同**
  （PASS ×6、INCONCLUSIVE ×6、NOT_APPLICABLE ×3、NOT_RUN ×1；RD001 两格仍 PASS，RD008 两格仍各 INCONCLUSIVE）；
- 全量 projection（rule / target / status / measurements / evidence 五元 path+line+key+artifact_id+note）
  比较：**只有 `RD004 / candidates:cand:adult-tuning-trials` 的 1 条 evidence note 由空变有文本**，
  其余 15 条连 evidence 文本都逐字节相同。这条断言写死在
  `test_the_simplified_manifest_is_shorter_and_says_the_same_things`，未来任何人改坏都会被拒。

---

## 8. Backward compatibility（§14）

- Phase 3 全部既有测试未修改、全部通过：`148 → 161`，其中 148 是原数量、13 是本轮新增；
- Phase 4 的 110 行 manifest 原样加载并产出同一 16 条 finding（T2 已固化为测试，缺失试点 checkout 时
  按 Phase 3 对归档的同款做法 `skipif` 跳过）；
- 旧 `_size` 两类写法、旧 `{path, line}`（用于 `wording:` 等整行文本处）、旧显式 identity 写法全部继续合法；
- 唯一有意破坏的旧行为：**把整行文本当打印单元格数值**、以及**一个 quantity key 覆盖同一表格两行**。
  这两者在本轮之前会加载成功并产出**错误的科学结论**，现在加载期即拒绝 —— 这正是本轮的目的，
  不属于 §14 保护的「合法 manifest」范畴（Phase 3/4 的 fixtures 中不存在这种写法，已实测：无 fixture 受影响）。

---

## 9. Tests（§16 的 T1–T6）

新增 `tests/test_phase5_ux.py`，13 个用例：

| 要求 | 用例 |
|---|---|
| T1 identity 默认等价 | `test_an_identity_without_a_path_is_read_against_the_members_own_file`（四元组 + `canonical_json(evaluate(...))` 相同）、`test_an_identity_sugar_never_upgrades_a_missing_identity`（省略仍 UNKNOWN、糖衣是 DIRECT）、`test_an_identity_without_a_path_still_needs_a_member_path`（inline 成员无文件可继承 ⇒ `E_MISSING_FIELD`） |
| T2 旧语法兼容 | `test_the_phase4_manifest_still_loads_and_still_judges_the_same_way`（16 target 状态向量硬编码）、`test_the_old_size_doors_still_mean_the_same_thing` |
| T3 `_size` companion | `test_a_size_can_carry_its_prose_as_a_companion`（新写法 ⇒ DECLARED、value 数字、note 落位）、`test_a_size_that_declares_no_number_is_refused_with_the_shape_it_wants`（三种非法写法各自错误码 + 文本点名 `value: <integer>`） |
| T4 G1 | `test_a_line_locator_without_a_quoted_fragment_cannot_be_a_printed_cell`（整行 ⇒ `E_LOCATOR_TEXT`；带 `text` ⇒ DIRECT 且值就是片段）、`test_the_G1_refusal_names_the_field_the_problem_and_the_shape` |
| T5 G2 | `test_one_quantity_key_cannot_name_two_rows_of_one_table`（⇒ `E_MISSING_FIELD`，不是 RD008 FAIL）、`test_the_G2_refusal_says_which_two_rows_and_the_minimal_fix`、`test_row_scoped_quantities_load_and_a_cross_product_key_is_still_allowed`（跨产物同键仍合法） |
| T6 真实验收 | `test_the_simplified_manifest_is_shorter_and_says_the_same_things`（110 → ≤100 + 全量 projection 等价） |

未新增工具、未为覆盖率补测试；26 错误码冻结集合与「generic path 绝不产出 INFERRED/DERIVED」两条
既有防火墙断言均在新代码下继续通过。

---

## 10. Quality gates

```text
python -m pytest -q                      -> 161 passed in 28.19s
python -m pytest -q -k "not generic and not phase5" -> 76 passed, 85 deselected   (Phase 1 子集)
python -m ruff check .                   -> All checks passed!
python -m ruff format --check .          -> 21 files already formatted
python -m mypy                           -> Success: no issues found in 12 source files
```

配置侧唯一改动：`[tool.ruff] extend-exclude` 增加 `"phase*"`。原因是 Phase 4 把第三方试点 checkout
（`phase4/rtdl-revisiting-models/lib/*.py` 等）vendor 进了同一棵树，`ruff check .` 会去 lint 上游代码
（57 条上游告警）。这些目录是**证据数据**，与 `tests/generic_fixtures` 同类：manifest 引用的正是它们的
行号，格式化会直接破坏 locator。`src/` 与 `tests/` 全量通过，未放宽任何规则。

---

## 11. Deferred：G3–G9 保持登记

| # | 状态 | 本轮为什么不动 |
|---|---|---|
| G3 | 部分处置，**仍登记** | 只允许「已声明 identity 的门体内省一次 path」；整条 identity 默认化会违反 §9/§10 与 Phase 3 防火墙 row 4（见 §3.2） |
| G5 | 仍登记 | `E_UNKNOWN_KEY at .../aggregate` 未说出 members 的正确层级；本轮只重写真实踩到的三条文本，未顺手扩 |
| G6 | 仍登记 | TOML 数值宣称仍只能 DECLARED（`n_trials = 100` 经 `{path,line,text}` 引证），未新增 locator family |
| G7 | 仍登记 | selection 仍只能绑 cell；per-member epoch 选择仍写成一个不绑 cell 的事件 |
| G8 | 仍登记 | `round` vs `format` 的指引仍要先撞上报错 |
| G9 | 仍登记 | 论文/PDF 侧打印物仍完全不可达；本轮 README 假 FAIL 的修法是把片段写进 `text:`，不是让工具读 PDF |
| B2 | 已由 G1 处置 | `{path,line}` 与 `{path,line,text}` 的差异现在在打印单元格处被强制说明 |
| B3 | 仍登记（**新增关注**） | 见 §12：糖衣让「identity 跨文件」更易被误用，但语法上仍无阻拦 |

---

## 12. Known limitations

1. **G3 未解**：作者仍必须逐个写 30 个成员（30 行 = 全文 30.6%）。这是契约自己的防火墙，不是本轮疏漏。
2. **identity 门体仍可跨文件**：糖衣只在「门体内不写 path」时补成员自身路径；显式写另一个文件的 path
   仍被允许，其 provenance 仍然是那另一个文件的 DIRECT 引用。Phase 4 B3 的怀疑本轮仍未构造用例钉住。
3. **引文挖掘仍未被证明**：`text: "maximize"` 只证明该行含此片段，不证明它是 `direction=` 的值 —— 与本轮无关，
   但仍是 generic path 的固有强度上限。
4. **G1 只覆盖打印单元格 value**：`spread` 与 value 同源（`_cell_field` 一次切分）故同时覆盖；
   `wording:` / `supported_by:` 处整行文本仍是有用写法，未收紧。
5. **G2 是「同 (artifact, table) 键唯一」**：若作者给两行写了相同 key 但声明了不同 `table`，加载器看不见
   它们的真实冲突，仍会交给 RD008。table 名字本身是作者声明，工具无从判断两张表是否是同一批行。
6. **≤100 行有 7 行来自排版**：见 §6 归因表；逻辑成本（成员枚举）没有下降，本轮也禁止它下降。
7. 试点 checkout 与两个 trap 复现物以只读方式存在于 `phase4/`、`phase5/`；换机器跑时相关用例 `skipif` 跳过
   （与 Phase 3 对冻结归档的处理一致）。

---

## 13. Phase 5 verdict

全部 16 条 CLOSED 判据逐条满足（§22），blockers = 0：

```text
Phase 5 verdict: CLOSED
```

判定依据中最强的两条不是「行数达标」，而是：
(i) 8 对象 38 实例逐字段 diff 只剩 1 个字段，且该字段是 provenance 增加；
(ii) 两个静默误判在**真实项目 manifest 的最小改写形式**上稳定复现为加载期拒绝，
而不是靠新增推断把 FAIL 变成 PASS。

本轮不做下一轮的事：UX 简化到此为止。行数已经达标，而继续压 YAML 只能买自动发现，
那会重新打开 candidate/membership provenance 问题。

---

## 14. Unique next step

`phase4/rtdl-revisiting-models/` 里那份 98 行 manifest 现在能在测试里被加载、审计、比较，
但**没有任何人能用一条命令自己跑它**：入口至今是 `python -c "from result_doctor.audit import audit_manifest; ..."`
加 `PYTHONPATH` 拼接（本轮全部测量都是这么做的）。

```text
唯一下一步: CLI / distribution / fresh-user workflow
```

即：`pip install -e .` 之后的 `result-doctor audit <dir>`，输出 16 条 finding 的稳定文本形式，
并用一次真实「新人从零跑通 README 那一格」的操作记录来 measurement 下一个摩擦点 —— 而不是再压 YAML。
