# Result Doctor — Phase 3 Generic Loader 实现关闭报告

- 日期：2026-09-28
- 上游权威：`phase2/RESULT_DOCTOR_PHASE2_DESIGN.md`（Phase 2 / Design：CLOSED）；`phase1/RESULT_DOCTOR_PHASE1_REPORT.md`（冻结语义）
- 本轮性质：**实现** Phase 2 已冻结的 generic contract，不重新设计
- 状态：**Phase 3 CLOSED**（§31 判据逐条通过，见 §16）
- 代码位置：`F:\MLResearch\result-doctor\{src/result_doctor,tests,pyproject.toml}`

---

## 1. Executive result

一个 Result Doctor 从未见过的项目，现在只写一个 `result-doctor.yml`（本项目最大示例 86 行）就能进入 RD001–RD008：

```text
result-doctor.yml → bundle_from_manifest() → 同一套 8 对象 Bundle → evaluate() → 入口层补 NOT_RUN → 状态向量
```

三个可检验的事实：

1. **能证明的证明了**：G1（Example A）里 RD001/RD002/RD005/RD006 全部 PASS，且 PASS 是被**复算**出来的
   （成员值由 `runs/{a,b,c}/log.csv` 的 `column: test_acc, row: last` 读回，94.12 与 0.24 都由
   `compute.center/dispersion/render` 重算命中）；Example B 里同一个入口给出 **RD001 FAIL**
   ——声明的 91.4 与成员复算的 91.5 不自洽，evidence 指向 manifest 自身。
2. **证据不足的地方没有编造**：G2（去掉 `member_rule`/`wording`、成员值改为内联声明）8 份 finding
   里没有一个 PASS 也没有一个 FAIL；G5 的不可访问外部基线**不进入 bundle**，缺口由 RD007 的
   `peer_values_recoverable=False` 与 RD008 的 `n_loci=1` 定位，而不是被猜测或被判 FAIL。
3. **输入结构错误与科学不确定性没有混淆**：34 个「不能当作合同读」的 manifest 全部以 `E_*` 码拒绝
   （26 个码，不多不少，测试逐字钉死码集合）；而「不知道选择政策 / 不知道全集 / 缺证据」这四类
   **必须加载成功**并以 INCONCLUSIVE / NOT_APPLICABLE / NOT_RUN 收尾，`test_a_thin_manifest_audits_and_never_raises` 钉住这条通道。

Phase 1 零回归：76 个旧测试全绿且未改一行规则语义；两个冻结归档经 `audit_bundle()` 的输出
`canonical_json` **字节不变**（538 与 31 份 finding，NOT_RUN 追加数为 0）。

---

## 2. Implemented scope

| 文件 | 行数 | 本轮职责 |
|---|---|---|
| `src/result_doctor/manifest.py` | 1244 | manifest 合同（8 section 的作者面）、两门解析、4 种 locator、lowering 到 8 对象、26 个 `E_*` 码 |
| `src/result_doctor/audit.py` | 82 | 入口层：`DRIVING_CLASS` + `not_run_findings()` + `audit_bundle()` + `audit_manifest()` |
| `src/result_doctor/__init__.py` | 26 | 追加导出 `ManifestError / bundle_from_manifest / audit_bundle / audit_manifest` |
| `tests/generic_fixtures/{g1,g2,g3,g4,g5,example_b}/` | 282（6 份 manifest）+ 27 个产物文件 | §23 六个用例的真实输入 |
| `tests/test_generic_acceptance.py` | 223 | G0–G5 状态向量 oracle（整向量相等）+ 每条反向不变式，15 个测试 |
| `tests/test_generic_firewall.py` | 587 | §21 十一行防火墙 + 结构闸 + §12 错误表（34 例参数化），57 个测试 |

未修改（本轮禁止面，全部经 git-外比对确认只读）：`rules.py`(834) / `schema.py`(312) / `compute.py`(98) /
`evidence.py`(76) / `status.py`(66) / `bundle.py`(73) / `loaders/gmmvi.py`(760) / `loaders/torchssl.py`(368) /
Phase 1 的 5 个测试文件 / Experiment Doctor 全仓。

**唯一一处配置改动**：`pyproject.toml` 的 `[tool.ruff]` 加 `extend-exclude = ["tests/generic_fixtures"]`。
理由不是风格：`example_b/train.py` 是「训练脚本摘录」，第 88/96/97 行的**物理行号就是被 manifest 引用的 locator**，
且它本身不是合法 Python（正文前是注释填充行）。不排除则 `ruff check` 直接语法报错、`ruff format` 会移动被引用的行。
登记为 D15。

未创建（§27/§33）：plugin / server / api / database / agent / scanner / GUI / PDF 解析 / W&B-MLflow-Hydra 连接器 /
LLM judge / trust score / RD009 / README-PyPI 营销 / 依赖安全审计 / 第三个真实项目。

---

## 3. Generic manifest（作者面合同）

顶层只有 `schema_version / project / root` 三个标量 + 8 个 section，与 Phase 2 §7 一一对应：

```text
artifacts / evidence / transformations / aggregations / candidate_sets
selection_events / reported_results / comparisons
```

作者面被压缩的三条实现方式：

- **id 一律由 loader 生成**：`agg:<label|id>`、`<agg_id>/<member name>`、`t:<chain>:<i>`、`cand:`、`sel:`、`cmp:`、
  `quantity:`、`rule:RDxxx`。用户只在需要多处复用时写 `id:`，嵌套值记录（`Locus`/`RunRef`/`MemberRule`/
  `SelectionCriterion`/…）从不暴露给用户寻址。
- **成员、变换步、准则内联在 cell 里**（`reported_results[].members/steps`、`selection_events[].criterion`），
  只有被多个 cell 复用才升级成顶层 `aggregations` / `transformations`（经 `{ref: <id>}` 或 `steps: {ref:}`）。
- **`evidence:` 登记表**只为「同一条证据被多处引用」而存在：条目带 `id`，任何字段可用 `{via: <id>}` 引用；
  引用不存在的 id ⇒ `E_UNRESOLVED_REF`。引用**不会**提升等级（被引用的门是什么就是什么）。

前向引用被支持：cell 的 `comparison:` 可以在 `comparisons:` 之前写（`_collect_ids()` 先扫 id，
集合本身仍在自己的条目里构建）。这不是「灵活」，而是 §7 的 section 顺序不强迫作者拓扑排序。

一个 cell 最少写 4 行也能审计（`label` + `value` + `aggregate.center` + `members`），
此时它**只**能得出 INCONCLUSIVE/NOT_APPLICABLE/NOT_RUN——这是设计，不是缺陷。

---

## 4. Two-door implementation

`observed: / declared: / unknown:` 是三扇门，不是三种写法（`field()` 单点实现，全模块共用）：

| 门 | 落进 bundle | 允许出现在哪 |
|---|---|---|
| `observed:` | `Grade.DIRECT` + 该次读的唯一 `SourceRef` | 必须是 root 内可确定性重放的读法（见 §6） |
| `declared:` | `Grade.DECLARED` + `SourceRef(path="result-doctor.yml#<section>[i]/<field>", key="declared:<name>", note=<by>)` | 任何字段 |
| `unknown:` | `Grade.UNKNOWN`，value=None，note 保留用户写的原因 | 任何字段 |
| 字段缺失 | `Grade.UNKNOWN`，note=`no <name> is declared` | — |

三条硬结果（防火墙测试逐条钉死）：

1. **INFERRED / DERIVED 从不被 generic loader 写出**：`grades_of(bundle)`（递归遍历 8 个 dict 里的每个
   `EvidenceField`）在 G1/G2/G5/Example B/BASE 上恒为 `{"DIRECT","DECLARED","UNKNOWN"}` 的子集。
2. **两扇门同时写 ⇒ `E_BAD_FIELD`**（`len(doors) != 1`），不是「取强的那扇」。
3. **`inferred:` 作为门名根本不存在**：写 `value: {inferred: {...}}` ⇒ `E_UNKNOWN_KEY`。
   防火墙不依赖「我们记得别写 INFERRED」，而是不认识这个词。

`declared` 的天花板（Phase 2 §9）实现为纯 lowering：`declared:` 只写进 `EvidenceField.grade`，
**从不**把 `AggregationMember.observed_value` 升成 DIRECT；用户只想写数字时该成员值记为 DECLARED，
RD001 仍在复算（比较声明模型与声明数字是否自洽），只是 finding 的 evidence 指向 manifest。
Example B 的两个 cell 正好是天花板的两侧：
`acc/x` 成员值 OBSERVED（`ckpt/r*/test_acc.txt` 第 1 行）而 printed cell 是 DECLARED 的 91.4，
复算得 91.5 ⇒ **FAIL**；`acc/y` 连成员值都是 DECLARED（90.6/90.9/91.0），复算得 90.8 ⇒ **PASS**——
「声明不保证一致」与「声明照样能被判定」同时成立，规则函数与 reason 模板一字未动。

---

## 5. Loader validation（错误 vs 未知）

26 个错误码，`test_the_error_vocabulary_is_exactly_the_documented_one` 断言模块内 `E_*` 常量集合
**等于**测试里登记的 26 元集合（多一个码、少一个码都过不了）。

| 类别 | 码 |
|---|---|
| 文件/形状 | `E_YAML E_TOP_LEVEL E_SCHEMA_VERSION E_ROOT E_TYPE` |
| 合同键 | `E_UNKNOWN_KEY E_MISSING_FIELD` |
| 身份/引用 | `E_DUPLICATE_ID E_UNRESOLVED_REF E_CONFLICTING_REF` |
| 枚举与取值 | `E_BAD_ENUM E_BAD_FIELD E_NOT_A_NUMBER E_BAD_DIRECTION` |
| root 与 locator | `E_PATH_OUTSIDE_ROOT E_ARTIFACT_MISSING E_LOCATOR_KEYS E_LOCATOR_LINE E_LOCATOR_TEXT E_LOCATOR_COLUMN E_LOCATOR_ROW E_LOCATOR_KEY` |
| 变换 | `E_STEP_NOT_APPLIED E_RENDER_STEP` |
| 科学宣称的结构前提 | `E_UNIVERSE_EVIDENCE E_MARK_DERIVATION` |

**错误**（拒绝加载）：非法 YAML/顶层非 mapping/`schema_version≠1`/未知 section 键/未知 object ref/重复 id/
非法 enum/非法 direction/path 越界/locator 无法解析/数值类型非法/禁止的 transformation 步/
`universe: unrecoverable` 无证据/`marks` 无 `marks_derivation`/一个 cell 绑两个比较集/section 写成 mapping。

**非错误**（成功加载，交给状态）：不知道 selection policy、不知道完整 candidate universe、
不知道 exclusion reason、不知道 comparison artifact、任何 scientific evidence 缺失。
这些情形在测试里的判据是「不 raise 且不出现 PASS/FAIL」，而不是断言某个具体状态——把状态写死会让
「缺字段」看起来像被计算出来的结论。

错误消息格式固定为 `{code} at {where}: {problem}`（§26），`where` 是 section 路径，
`problem` 带被拒绝的字面值与允许集合：

```text
E_BAD_ENUM at reported_results[0]/aggregate: center='trimmed_mean' is not one of ['mean', 'median']
```

诊断框架没有加：`ManifestError` 是 `ValueError` 子类，三个字段，`str()` 即上式。

---

## 6. Path / locator handling

**root 边界**（§11，只到「不越界」为止）：拒绝空 path、绝对 path（含 `X:` 盘符与 `~`）、
`..` 段、以及 `resolve()` 后落在 root 之外的**符号链接**目标；文件不存在 ⇒ `E_ARTIFACT_MISSING`。
没有 sandbox、没有 ACL、没有路径策略语言。

**locator 只有四种读法**，且每种都是「重放即得同一值」：

| 写法 | 读法 | `SourceRef` 落法 |
|---|---|---|
| `{path, column, row}` | CSV `DictReader`；`row` 为数据行 1-based 或 `last` | `key="column:<名>"`、`line=` 该行序 |
| `{path, key}` | JSON pointer（`/a/b`，支持列表下标）；不可解析 ⇒ `E_LOCATOR_KEY` | `key="key:<pointer>"` |
| `{path, line[, text]}` | 第 N 行（越界 ⇒ `E_LOCATOR_LINE`）；带 `text` 时该片段必须在这一行内 ⇒ 否则 `E_LOCATOR_TEXT` | 有 `text` ⇒ `key='text:"原文"'` + `line`；无 ⇒ 仅 `line` |
| `{path, text}` | 整文件包含该字面片段 ⇒ 否则 `E_LOCATOR_TEXT` | `key='text:"原文"'` |

没有 regex、没有 stdout 解析、没有 XPath、没有 Python 表达式。

一个额外的确定性读：**CSV 表头**。`artifacts:` 条目声明 `columns` 时，loader 真的打开文件读表头，
声明与读到的集合不一致 ⇒ `E_TYPE`（列名是唯一「能被文件否决」的作者声明，因为它可被确定性重放）；
未声明 `columns` 时直接采用读到的表头（Phase 2 §8 表格里 `ResultArtifact{path,columns}` 的 OBSERVED 行）。

`ResultArtifact.sha256 / size` **不计算**：Phase 2 §6 已判定这两个字段「无规则读取 ⇒ 删（仅可作 evidence 文本）」。
本轮不实现等于不实现，不新增字段、不做「顺手算个 hash」。

**printed cell 的拆分**不做任何文本语义：只在 `±` 与 `+/-` 两个分隔符上切 center/spread（Phase 0 见过两种拼法）。
写成 `94.12 (0.31)` 的单元格 ⇒ spread 保持 UNKNOWN，工具不去猜括号是什么。

---

## 7. CandidateSet / SelectionEvent

**CandidateSet**：`universe` 取 `unknown|complete|recovered|partial|declared_only|unrecoverable`，
映射到既有 `UniverseStatus`（**不新增 `COMPLETE`**，`complete` 由 `RECOVERED` 承担）；
`complete/recovered` 必须带可解析的 `universe_evidence`，否则**降级**为 `DECLARED_ONLY`——
这是 §15 的实现形状：宣称全集是断言，断言没有 locator 就不配 RECOVERED。
`unrecoverable` 必须带 `unobservable: [{reason, <门>[, supported_by]}]`，否则 `E_UNIVERSE_EVIDENCE`
（「没找到」不升级为「不可恢复」）。
`declared_size` / `surviving_size` 保持两个独立证据字段，各自可带 `statement` 作为单位说明；
**成员清单的长度绝不写成宇宙大小**：只有当用户没写 `declared_size` 时，loader 才把「列了几条」记为
DECLARED 的 `listed candidates`（note 明确写 listed，RD004 不与 surviving 比较）。
G1 反向不变式因此断言 `bundle.candidate_sets == {}`，「三个成员不是三个候选」。

**SelectionEvent**：`over` 地址候选集（index 或 id）；六个准则字段 `metric/split/direction/scope/tie_break/timing`
各自独立走三扇门，缺 ⇒ UNKNOWN ⇒ RD003 至多 INCONCLUSIVE。
`direction` 的值必须字面以 `min`/`max` 开头，否则 `E_BAD_DIRECTION`——
Example B 里 Phase 2 原文写的 `text:"if val_acc > best"` 因此被拆成两处：
direction 是 `declared: maximize`，代码比较留在 `supported_by`（登记 D6）。
`values` 是「声明还是观察」的分水岭：`chosen` 可由产物路径 OBSERVED，但「它被这个准则选中」必须 DECLARED。
**不强迫用户伪造 policy**：无 policy 的 cell 上 RD003 自己发 `NOT_APPLICABLE`（Example B 的 `acc/x`、`acc/y`），
selection event 本身则 `INCONCLUSIVE`。
文件名 `best.pt` 不产生 selection event（G3/§21 row4：`selection_events == {}`）。

---

## 8. Transformation whitelist

可写的步：`scale(factor) · sign_flip · sum_of_part(parts) · format(mode, digits) · identity`，
`stage ∈ member|center|dispersion|render`，`applied_at ∈ code|script|manual|unknown`（缺省 UNKNOWN）。

拒绝表（全部是「manifest 声称执行了 runtime 没做的事」这一类）：

| 情形 | 结果 |
|---|---|
| `round / delta / best_of_n / truncate_window` 出现在任何 stage | `E_STEP_NOT_APPLIED`（`compute.apply_stage` 对它们是 `continue`） |
| 非 `format` 的步出现在 `render` | `E_RENDER_STEP`（render 阶段唯一有语义的步是 format） |
| `format` 出现在非 `render` | `E_RENDER_STEP`（同上类的反向谎：声称做了一次 runtime 不做的舍入） |

第三行是本轮在 Phase 2 §17 的拒绝表之外补的一条，登记为 D3。

聚合只走 Phase 1 已有的封闭枚举：`center ∈ {mean, median}`、`spread.kind ∈ {none, std, sem, k_sem}`、
`ddof`、`k`；**n 一律由成员数派生，不接受用户声明 n**。
`eval()`、Python 片段、符号表达式、NumPy 执行器：不存在。

`applied_at` 缺省 UNKNOWN ⇒ RD006 判 INCONCLUSIVE。这条不是推测：把 Example B 的两处 `applied_at` 抹掉后，
`acc/y` 从 PASS 变成 INCONCLUSIVE，reason 变为「which branch produced this cell is not recoverable: ['t:acc/y:0']」。
而标注齐全的 `acc/x` 的 INCONCLUSIVE 说的是另一件事——链逐段施加得 91.5、列印 91.4，
「the recorded chain does not yield the printed cell; an unrecorded step cannot be excluded」。
两条都在 D11 里登记。

---

## 9. NOT_RUN wrapper

入口层只做一件规则无法为自己说的事：**整类对象从未被提供**。

```python
DRIVING_CLASS = {RD001: reported_results, RD002: aggregations, RD003: selection_events,
                 RD004: candidate_sets, RD005/006/008: reported_results, RD007: comparison_sets}
```

- 判据是「该 rule 在 `evaluate()` 的输出里一条 finding 都没有」，不是「我以为它没跑」。
- 追加的 `RuleFinding`：`target = rule:RDxxx`、`evidence = ()`（NOT_RUN 不宣称任何事实，所以不引用任何东西）、
  `measurements = {driving_object_class, n_objects, n_targets}`、`reason` 分两种写法：
  类为空 ⇒「no target of this class was supplied (candidate_sets is empty)」；
  类非空但无 target ⇒「…is populated, but nothing in it carries the key RD008 reads」（Example B 的 RD008）。
- **不把科学不确定性偷换成 NOT_RUN**：`n_objects>0` 时那句话本身就说明「对象给了，只是没有该规则读的键」，
  与「没给对象」在 reason 与 measurements 上都可区分。
- 排序：`audit_bundle()` 只做 `sorted(key=(rule_id, target))`，不改任何 finding 内容。
- 遗留适配路径**从不经过** `audit.py`：`rules.evaluate()` 的字节与调用签名不变，
  因此 GMMVI/TorchSSL 输出恒等（§12）。

---

## 10. G0–G5 results（状态向量逐位相等）

oracle 形式：`{(rule_id, target): status}` **整字典相等**，另断言 finding 总数——
「某条规则悄悄多/少一个 target」过不了这一关。

| 用例 | 输入 | 向量（本轮实测） | 反向不变式（测试名） |
|---|---|---|---|
| **G1** | Example A | RD001 PASS · RD002 PASS · RD003 NOT_APPLICABLE · RD004 **NOT_RUN** · RD005 PASS · RD006 PASS · RD007 **NOT_RUN** · RD008 INCONCLUSIVE（8 份） | `test_g1_invents_no_selection_or_candidate_target`：无 `selection:/candidates:/comparison:` target，三类对象 dict 为空，NOT_RUN 的 `evidence==()`；`test_g1_does_not_read_universe_size_from_the_member_count`：`n==3` 是成员数，`candidate_sets=={}` |
| **G2** | A 去掉 `member_rule`/`wording`，成员值改内联 | 8 份里 **0 PASS / 0 FAIL**：RD001/002/005/006/008 INCONCLUSIVE · RD003 NOT_APPLICABLE · RD004/007 NOT_RUN | `test_g2_loads_and_abstains_rather_than_failing`：不 raise；reason 精确到「member rule is not declared」/「no wording declares」 |
| **G3** | A 原样 + 同目录放 `best.pt`、`seed_42/log.csv`(99.99)、`final/mean.csv`(99.99)、`results.csv`、`wandb_group_a/` | `canonical_json(findings(G3)) == canonical_json(findings(G1))`（字节相等） | `test_g3_file_names_change_nothing_in_the_bundle_or_the_output`：`best.pt/seed_42/final/mean.csv/results.csv/wandb_group_a/99.99` 七个串在输出+成员 id+section keys 拼成的文本里**一次都不出现**；成员数仍为 3，来源路径恰为 `{runs/a,runs/b,runs/c}/log.csv` |
| **G4** | 措辞声明 standard error，而只有 ddof=0 的 std 能复现打印值 | RD005 **FAIL**，RD001 **PASS**、RD006 PASS | `test_g4_wording_neither_upgrades_nor_downgrades_the_recomputation`：RD001/RD006 与 G1 完全同状态（措辞声明不参与复算判定），`spread_label_grade=DECLARED`、`families_matching_published_spread=["std_ddof0"]` |
| **G5** | 自有 cell + 外部基线 `external/eqnet`（`origin: unknown`，路径未被引用） | RD007 INCONCLUSIVE、RD008 INCONCLUSIVE，其余同 G1 形态、**无 FAIL** | `test_g5_keeps_the_external_baseline_outside_the_bundle`：`external/eqnet` 不在 `reported_results`，`n_members==2` 而 bundle 只有 1 个 cell，`peer_values_recoverable=False`、`external_origin_grade=UNKNOWN`、`n_loci=1` |
| **G0** | Phase 1 全套 + 两归档经 `audit_bundle()` | 148 passed；`canonical_json(audit_bundle)==canonical_json(evaluate)`（gmmvi 538、torchssl 31），NOT_RUN 追加数 0 | `test_g0_example_a_and_b_are_loadable_without_adaptation_files`：同一 manifest 解析两次输出字节相等（fixtures 不带生成状态） |
| **Example B** | §20 第二个示例（ckpt selection + candidate + comparison） | RD001 **FAIL**(acc/x)/PASS(acc/y) · RD002 PASS×2 · RD003 NOT_APPLICABLE×2 + INCONCLUSIVE(sel) · RD004 **PASS**(universe 声明 + 代码 locator) · RD005 NOT_APPLICABLE×2（cell 无 ±）· RD006 INCONCLUSIVE/PASS · RD007 INCONCLUSIVE · RD008 NOT_RUN（14 份） | 同 `test_the_status_vector_is_exactly_the_oracle`（14 个 target 逐一相等） |

Phase 2 §23 的两处预期与冻结语义相撞（G1 的 RD003 应为 NOT_APPLICABLE、G5 的 RD008 无法凭空多一个 target），
按 §32 优先级处理并登记为 D2 / D7。

---

## 11. Firewall results（§21 十一行 + 结构闸）

| # | 混淆 | 钉死它的断言 | 测试 |
|---|---|---|---|
| 1 | missing field ≠ false fact | 稀疏 manifest 全部 UNKNOWN、无 PASS/FAIL；`center` 不默认 ⇒ `E_MISSING_FIELD`，`UNKNOWN` 字面量 ⇒ `E_BAD_ENUM` | `test_row1_*`(2) |
| 2 | listed candidates ≠ complete universe | `universe_status=UNKNOWN`；`declared_size` 只写「listed candidates」；RD004 INCONCLUSIVE 且 `universe_size` 不在 measurements；无证据的 `complete` 降 `DECLARED_ONLY`；同单位两 size 才可比（PASS） | `test_row2_*`(3) |
| 3 | declared evidence ≠ direct observation | 同一数字 93.85：G2 内联 ⇒ DECLARED 且 source 指向 manifest，G1 locator ⇒ DIRECT 且 source 指向 `runs/a/log.csv`+`column:test_acc` | `test_row3_*` |
| 4 | best filename ≠ best-checkpoint provenance | `best_final_mean.csv` 只贡献被 `row: last` 读到的 0.80；selector 是 manifest 自己写的 `last_row`(DECLARED)，不是 best/mean/final；`external_id` UNKNOWN；`selection_events=={}`。Example B 的 `best` 只能是 DECLARED 宣称 | `test_row4_*`(2) |
| 5 | same directory ≠ same aggregation | 同一 CSV 上两个 aggregation 成员集合互不相关，`n_members` 分别 2 / 1 | `test_row5_*` |
| 6 | same group ≠ same candidate universe | 重复 `grid_a` 只登记为 `IdentityCollision{collision_count:1, samples:[{ref,listed_times}]}`，note 写「not determined here」；RD004 的 reason 不含 same grid/unrelated/confuse/duplicate | `test_row6_*` |
| 7 | successful parse ≠ scientific completeness | G2 解析成功、8 份 finding、状态集合 ⊆ {INCONCLUSIVE, NOT_APPLICABLE, NOT_RUN} | `test_row7_*` |
| 8 | declared identity ≠ observed identity | Example B 成员身份 DECLARED ⇒ RD001 取得 FAIL 资格（复算 91.5 vs 声明 91.4）；G2 未声明身份 ⇒ 同一比较被封顶成 INCONCLUSIVE | `test_row8_*` |
| 9 | declared marks ≠ recomputed marks | `marks_recovered_from=DECLARED`，reason 不提 rule；marks 的 source 前条是 manifest 声明处、末条是被引用的 `paper/table4.txt`；写 `marks: {observed:}` ⇒ `E_BAD_FIELD` | `test_row9_*` |
| 10 | unapplied step ≠ applied step | 四个不参与复算的步 ⇒ `E_STEP_NOT_APPLIED`；render 只容 `format`；`format` 离开 render ⇒ `E_RENDER_STEP` | `test_row10_*` |
| 11 | inline value ≠ artifact cell value | 内联 2.0 ⇒ DECLARED、`artifact_ref=""`、`bundle.artifacts=={}`；而 RD001 仍据实复算并 PASS（等级低≠不判定） | `test_row11_*` |

结构闸（延续 Phase 1）：无 INFERRED/DERIVED；`BANNED` 词表（复用 `tests/test_firewall.py` 的同一份）在四条 generic 路径的
每条 finding 的 `reason+measurements+target` 里零命中；输出无任何 score/verdict/trust/ranking 键；
bundle 只含 8 个冻结 dataclass（`type(v) is cls`，generic 没有第二套 schema）；入口层只追加 NOT_RUN 且从不重述已发言的规则。

---

## 12. Phase 1 zero-regression

- `python -X utf8 -m pytest tests -q -k "not generic"` ⇒ **76 passed**（Phase 1 的 5 个测试文件，一字未动）。
- G0：`canonical_json(audit_bundle(bundle)) == canonical_json(evaluate(bundle))` 对两归档成立；
  `not_run_findings()` 在两归档上返回 `[]`（8 条规则全部有 finding）。
  分规则条数未变：gmmvi RD001 59 / RD002 46 / RD003 157 / RD004 100 / RD005 59 / RD006 59 / RD007 5 / RD008 53 = 538；
  torchssl 3/2/7/7/3/3/3/3 = 31。
- 规则语义未改：`rules.py`、`schema.py`、`compute.py`、`evidence.py`、`status.py`、`bundle.py`、
  `loaders/gmmvi.py`、`loaders/torchssl.py` 本轮零写入（§21 的「确定性 bug 才允许单独修」通道未被触发使用——
  G0–G5 没有暴露任何 Phase 1 规则 bug；两处 Phase 2 oracle 与冻结语义的相撞按 §32 归为设计侧偏差 D2/D7，不动规则）。

---

## 13. Deviations from Phase 2（登记册）

格式：original design / contradiction / evidence / minimal correction / semantic impact / oracle impact。
按 §32 优先级判定，均为最小修正，未扩大范围。

**D1 — 每个成员必须声明身份（Example A/B）**
- original design：§20 的 `members: [{path, column, row}]` 无 identity 字段。
- contradiction：Phase 1 冻结门 `_identity_indeterminate`（member_rule 未声明 / `external_id` UNKNOWN / producer UNKNOWN）
  把 RD001 的 FAIL 资格封成 INCONCLUSIVE，且 RD002 的 PASS 需要成员可绑定。
- evidence：G2 的 RD001 停在 INCONCLUSIVE 且 reason 为「identity is not determined」；G1 补 `identity: {declared:}` 后 PASS。
- minimal correction：示例 manifest 每成员加一行 `identity: {declared: {value: run-x, by: author}}`。
- semantic impact：无（DECLARED 身份只解锁判定，不改变证据强度）。
- oracle impact：G1 的 RD001/RD002 可达 PASS；Example B 的 FAIL 可达。

**D2 — G1 的 RD003 是 NOT_APPLICABLE，不是 NOT_RUN**
- original design：§23「RD003/004/007 = NOT_RUN」。
- contradiction：冻结 RD003 对每个缺 `selection_refs` 的 cell **自发** NOT_APPLICABLE，规则因此「已发言」。
- evidence：`audit_manifest(g1)` 里 RD003 有一条 `reported:acc/cifar-resnet20` 的 NOT_APPLICABLE。
- minimal correction：入口层判据保持「零 finding 才补 NOT_RUN」，oracle 写 RD003 NOT_APPLICABLE。
- semantic impact：无；NOT_RUN 的定义更严格（整类缺席），语义更好。
- oracle impact：G1 向量第 3 位改为 NOT_APPLICABLE，finding 总数仍 8。

**D3 — `format` 只允许在 `render` stage（新增拒绝）**
- original design：§17 只规定「render 阶段只允许 format」，未规定 format 出现在别处的后果。
- contradiction：`compute.apply_stage` 对 format 是 `continue`，非 render 阶段的 format 步等于「声称执行了一次 runtime 不做的舍入」——正是 §13 禁止的那类谎。
- evidence：G1/Example B 的 RD001 全靠 render 阶段 format 命中；同一步挪到 member 即失效但仍被接受。
- minimal correction：新增 `E_RENDER_STEP`（复用已有码，不加新码）。
- semantic impact：generic 作者面收窄一步，判定不变。
- oracle impact：G0–G5 无影响；防火墙 row10 多一条断言。

**D4 — `selector: best` 必须是门（Example B）**
- original design：`members: [{path: …, selector: best}]`。
- contradiction：§8 的裸 token 无门 ⇒ 要么默认 DIRECT（用户手写等级，§22 已否决），要么 UNKNOWN（丢掉宣称）。
- evidence：G3/row4 需要区分「文件名/目录里的 best」与「作者宣称的 best」。
- minimal correction：`selector: {kind: best, declared: {by: author}}`；`row: last` 则自动记 `last_row` 且 grade=DECLARED（它是 manifest 自己写的读法）。
- semantic impact：selector 宣称恒为 DECLARED，永不 DIRECT。
- oracle impact：无（G3 断言 `selection_events=={}` 仍成立）。

**D5 — `marks` 不能 OBSERVED（Example B）**
- original design：`marks: {observed: {path: paper/table1.txt, line: 5, …}}`。
- contradiction：§18 自己规定「工具复算了加粗」不可读；locator 只证明片段存在，不证明它标记了哪个成员。
- evidence：`_mark_field` 对 DIRECT 门抛 `E_BAD_FIELD`，G5/Example B 用 `declared: [...] + supported_by: <locator>`。
- minimal correction：marks 走「声明 + 旁证」两件套，PASS 语义 = 两处声明一致。
- semantic impact：RD007 在 generic path 的 PASS 永远不表示「工具自行复算」。
- oracle impact：G5 的 RD007 为 INCONCLUSIVE（peer 值不可恢复），Example B 的 RD007 INCONCLUSIVE。

**D6 — `direction` 必须是 min*/max* 词元（Example B）**
- original design：direction 直接 observed 代码片段 `if val_acc > best`。
- contradiction：§16「direction 必须字面以 min/max 开头；其他写法 = 输入错误，不做语义猜测」。
- evidence：G0–G5 若允许比较式即等于引入符号语义推断。
- minimal correction：`direction: {declared: {value: maximize}}` + `supported_by: {path: train.py, line: 97}`。
- semantic impact：无。
- oracle impact：RD003 保持 INCONCLUSIVE（`split/scope` DECLARED、`tie_break` UNKNOWN）。

**D7 — G5 的外部缺口不新增 RD008 target**
- original design：§23「RD008 定位到缺 locus」。
- contradiction：冻结 RD008 按 `quantity_key` 在**已声明 cell** 分组；为未命名的外部基线造 target 需要改规则。
- evidence：G5 的 RD008 = INCONCLUSIVE(`quantity:acc/ours`, `n_loci=1`)，缺口本身在 RD007 的 measurements 里。
- minimal correction：缺口由 RD007 `peer_values_recoverable=False` + `external_origin_grade=UNKNOWN` 与 RD008 `n_loci` 联合表达。
- semantic impact：外部产物不进 bundle 这条更硬。
- oracle impact：G5 向量与反向不变式如上。

**D8 — `key: "text:\"…\""` 变成独立 locator 键**
- original design：§19 的示意写法把 locator 塞进 `key:` 字符串。
- contradiction：`key:` 是 JSON pointer 读法；把两种读法复用一个键需要字符串前缀解析。
- evidence：`read_locator()` 的分支是 locator **键集合**，不是前缀。
- minimal correction：`text:` 成为第四个 locator 键，`SourceRef.key` 仍写成 `text:"<原文>"`（Phase 1 值形不变）。
- semantic impact：无，重放路径更短。
- oracle impact：G1/G4 用 `{path, line, text}` 读回打印单元格。

**D9 — Example A 的 `± 0.31` 改为可复现的 `± 0.24`**
- original design：§20 Example A 印 `94.12 ± 0.31`。
- contradiction：0.31 不由任何族（std/sem/k_sem × ddof∈{0,1}）从 93.85/94.20/94.31 复现 ⇒ RD005 必 FAIL，G1 就变成「示例自带失败」。
- evidence：mean=94.12，ddof=1 ⇒ 0.2402→"0.24"；ddof=0 ⇒ 0.1961→"0.20"（后者正是 G4 用的对偶）。
- minimal correction：G1 打印 `94.12 ± 0.24`；把「打印值与复现族矛盾」这条通道交给 G4（RD005 FAIL）与 Example B（RD001 FAIL）。
- semantic impact：无。
- oracle impact：G1 RD005=PASS。

**D10 — 无 ± 的 cell 上 RD007 先于 §18 一致性检查而弃权（Example B）**
- original design：§20 Example B 预期 RD007 走「两处声明一致」。
- contradiction：冻结 RD007 的 `recomputable` 门要求每个 peer 同时有 value 与 spread；Example B 两个 cell 都无 ±。
- evidence：`audit_manifest(example_b)` 的 RD007 reason 是「not every peer value of this comparison set is recoverable」。
- minimal correction：§18 语义由 G5（有 ±、marks 两件套）演示，Example B 保留 INCONCLUSIVE。
- semantic impact：无。
- oracle impact：Example B 向量 RD007=INCONCLUSIVE。

**D11 — `applied_at` 必须在 manifest 里写出**
- original design：§20 的 `steps` 未写 `applied_at`。
- contradiction：§9「字段缺失 ⇒ UNKNOWN」，而冻结 RD006 把 `applied_at: unknown` 当作未定分支 ⇒ INCONCLUSIVE；
  示例若原样落地，Example B 的 `acc/y` 就演示不出「链逐段施加得到列印单元格」这条 PASS。
- evidence：抹掉 `applied_at` 的 Example B 副本里 `reported:acc/y` = INCONCLUSIVE，
  reason「which branch produced this cell is not recoverable: ['t:acc/y:0']」；写回后 PASS。
- minimal correction：fixture 的两条 format/scale 步各写 `applied_at: manual|script`（缺省仍为 UNKNOWN，不改 loader）。
- semantic impact：无；作者面多一列必填式的自觉。
- oracle impact：Example B 的 RD006 由「两条都 INCONCLUSIVE」变为 INCONCLUSIVE(`acc/x`，链与单元格不符) + PASS(`acc/y`)。

**D12 — `unrecoverable/champion/tie` 等作者面键名对齐 Phase 1 字段名**
- original design：§7 的 `unrecoverable?{reason,evidence}`、`champion?`、`criterion{…,tie,…}`。
- contradiction：lowering 目标分别是 `CandidateSet.unobservable_sources`、`promotion_evidence`、`SelectionCriterion.tie_break`；再造一套别名不会带来新判定能力。
- evidence：`_candidate_sets()`/`_selection_events()` 直接以 schema 字段名为键。
- minimal correction：作者面统一为 `unobservable / promotion / tie_break`，`statement` 保留为人读说明位。
- semantic impact：无。
- oracle impact：无。

**D13 — `SourceRef.artifact_id` 未启用**
- original design：§19「Phase 1 未使用，generic path 启用它」。
- contradiction：generic 路径每条 SourceRef 要么是产物文件（`path` 已是唯一寻址键），要么是 `result-doctor.yml#section[i]/field`；再填一个 id 不区分任何东西，且没有任何规则读它。
- evidence：`grep artifact_id src/result_doctor/manifest.py` 无命中；G0–G5 全部断言均基于 path/line/key。
- minimal correction：保持未启用（与 §6 对 `sha256/size` 的「无规则读取 ⇒ 不作字段」判定同类）。
- semantic impact：证据引用面收窄一处，无判定影响。
- oracle impact：无。

**D14 — 打印单元格必须由 `value:` 给出**
- original design：§20 用 `value: {observed: {path, line, key: "text:\"94.12 ± 0.31\""}}`，`printed_in.quoted_text` 另写。
- contradiction：从散文里抠数字需要文本语义（§12 禁止）；`_split_cell` 只切分隔符。
- evidence：G1 的 `value:` 走 `{path, line, text}` ⇒ DIRECT；`printed_in` 只填 locus 描述位。
- minimal correction：单元格内容 = `value:`（可 OBSERVED 可 DECLARED），`quoted_text` 仅作 locus 记录。
- semantic impact：无（等级由门决定，不由 `printed_in` 决定）。
- oracle impact：G1 RD001 的 evidence 指向 `paper/table2.txt:7`。

**D15 — `pyproject.toml` 增加 ruff `extend-exclude`**
- original design：§29 沿用现有门禁；§27 保持项目结构。
- contradiction：`tests/generic_fixtures/example_b/train.py` 是被 manifest 按物理行号引用的**摘录数据**（含未定义名、正文前是注释填充），纳入 lint/format 会直接报错或被格式化改掉行号。
- evidence：`ruff check` 在该文件报语法错；`ruff format --diff` 失败于第 88 行缩进。
- minimal correction：`extend-exclude = ["tests/generic_fixtures"]` 一行，工具与规则集合不变。
- semantic impact：无。
- oracle impact：无（G3 的 `best.pt` 等 fixture 仍被 loader 视为不可见）。

---

## 14. Test / ruff / format / mypy

```text
python -X utf8 -m pytest tests -q            → 148 passed（Phase 1 76 + 本轮 72），43s
python -X utf8 -m ruff check src tests       → All checks passed!
python -X utf8 -m ruff format --check src tests → 20 files already formatted
python -X utf8 -m mypy                        → Success: no issues found in 12 source files
```

本轮新增 72 个测试 = 15（acceptance：6 向量 + 6 反向不变式 + 2 个 G0 + 1 个幂等）+ 57（firewall：11 行 16 个
+ 5 结构闸 + 1 错误码集合 + 34 错误参数化 + 2 消息/通道）。质量工具零新增，依赖零新增（PyYAML 仍是唯一第三方运行时依赖），
`rules.py` 等 Phase 1 文件零格式化 churn（`ruff format` 仅改动本轮两个文件）。

---

## 15. Known limitations

1. **generic 路径的 RD007 不能自行复算呈现标记**（Phase 2 §18 的诚实边界）：PASS 只意味着「`marks` 与
   `marks_derivation` 两处声明一致」。若项目真有机器可读标记（表格列带 `**`、或有生成脚本），那是 adapter 的工作。
2. **没有仓库扫描**：新文件放进 root 不会让任何 finding 改变（G3 正是这一条的正向证据）。进入审计的唯一途径是写进 manifest。
3. **locator 四种读法之外一切不支持**：PDF 文本层、Excel、LaTeX 宏、stdout、TensorBoard 事件文件都不读。
4. **`evidence:` 登记表不提供传递强化**：`via:` 引用永远不改变等级。
5. **一个 cell 只能属于一个比较集**（`E_CONFLICTING_REF`）；跨表复用同一数字需要两个 label。
6. **aggregation 的 `center` 只认 mean/median**，`spread.kind` 只认四族；IQR / 分位数 / 加权平均会被判 `E_BAD_ENUM` 而不是被近似。
7. **G4/G5 是合成项目**：本轮没有第三个真实项目（§33 禁止），因此 generic 路径的上界由合成用例、
   下界由 GMMVI/TorchSSL 的既有取证事实共同钉住——「两扇门都能走通」已被证明，「真实作者会怎么写」未被证明。
8. **`ManifestError` 不聚合**：一次只报第一个结构问题。§26 明确不要大型 diagnostic 框架，因此未做批量报错。

---

## 16. Phase 3 verdict

**CLOSED**。逐条对照 §31：

```text
1  generic loader 存在且唯一入口是 result-doctor.yml            ✔ manifest.py / bundle_from_manifest()
2  只落到既有 8 对象，无第二套 schema                            ✔ type(v) is cls × 8
3  两扇门 + UNKNOWN，INFERRED 不产生                             ✔ grades_of ⊆ {DIRECT,DECLARED,UNKNOWN}
4  inline 恒 DECLARED，永不升级                                  ✔ row3 / row11 / §9
5  OBSERVED 仅来自确定性读（存在性/显式路径/列行/key/line/text）  ✔ §6 四种读法
6  不从文件名/目录名/group/计数生成 provenance                   ✔ row2 / row4 / row6 / G3 字节相等
7  字段缺失 ⇒ UNKNOWN，不补默认 scientific fact                  ✔ row1（含 center 不默认）
8  结构错误 ⇒ 带码 ManifestError；证据不足 ⇒ 成功加载            ✔ 26 码 / 34 参数化 / thin-manifest 通道
9  路径限制在 root 内，拒绝 ../绝对/符号链接越界，无安全框架      ✔ under_root() 四类判据
10 transformation 只支持已实现的步，未施加的步判输入错误          ✔ E_STEP_NOT_APPLIED / E_RENDER_STEP×2
11 listed ≠ universe，禁止目录扫描定 universe                     ✔ row2 / G1 / G3
12 direction 非 min*/max* ⇒ validation error                      ✔ E_BAD_DIRECTION
13 NOT_RUN 在入口层，规则内部无 generic 分支                      ✔ audit.py 82 行 / rules.py 未改
14 G0–G5 全过且整向量相等 + 反向不变式                            ✔ §10 表
15 §21 十一行防火墙 + 结构闸全过                                  ✔ §11 表
16 Phase 1 零回归（76 passed + 两归档 canonical_json 字节不变）    ✔ §12
17 §20 两个 YAML 示例成为真实测试输入，差异已登记                  ✔ g1/ + example_b/ + D1–D15
18 四项质量门禁全绿，无新工具、无大规模重构                        ✔ §14
```

未越界清单（§33）逐项确认未做：Table 8 的 6 格、第三个项目、PDF/repo scanner、W&B/MLflow/Hydra、
GUI/server/database/agent、LLM judge、trust score、RD009、PyPI/README、依赖安全审计、benchmark。
