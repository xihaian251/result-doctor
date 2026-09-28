# Result Doctor — Phase 2 / Generalization Design

- 日期：2026-09-28
- 上游权威：`phase0/RESULT_DOCTOR_PHASE0_REPORT.md`（Design CLOSED）、`phase1/RESULT_DOCTOR_PHASE1_REPORT.md`（Implementation CLOSED，76 tests / ruff / format / mypy 全绿）
- 本阶段性质：**Design only。未编码，未改 Phase 1 schema，未加 RD009+，未找第三个项目。**
- 依据材料：`src/result_doctor/{schema.py,rules.py,compute.py,bundle.py,evidence.py}` 的实际字段访问与分支条件、
  `tests/synthetic_fixtures.py`、两个 frozen loader、Phase 1 §9 偏差登记。

---

## 1. Executive conclusion

陌生项目可以通过**一份 YAML manifest + 它自己指向的产物文件**进入现有体系：

```text
result-doctor.yml（用户写）+ 项目内产物（工具按 locator 读）
  → 8-object schema（不变）
  → RD001–RD008（不变）
```

支撑它的是三条冻结约束：

1. **Two-Door Provenance Model**：一个事实只有 OBSERVED（locator 可解析并确定性读出）与 DECLARED（用户显式断言）
   两种来源，否则 UNKNOWN。**generic ≠ automatic inference**：不存在第三条门，`INFERRED` 在 generic path 永不被产出。
2. **Declaration 提供 provenance，不提供 consistency**：声明能把字段从 UNKNOWN 提升为可判定，
   但复算仍是 PASS/FAIL 的仲裁者；声明也**不能**把工具没读到的东西变成 DIRECT。
3. **Partial audit 是一等能力**：证据不足产生状态，不产生 parser error；
   只有 manifest 自身结构无法解析才是输入错误。

需要新增的东西只有一个：**generic manifest loader**（+ 入口层的 NOT_RUN 记录 + 输入校验错误）。
Phase 1 的 schema、规则函数、compute 层与两个 adapter 均不需要修改。

一个此前未被记录的 Phase 1 事实决定了本阶段一半的设计：`ComparisonSet.recomputed_marks`
在 Phase 1 中**从来不是被计算的**（`grep recomputed_marks src/` 只命中 schema 与 rules 的读取处，两个 loader 都不写它，
GMMVI 的 4 个比较集因此全部停在 INCONCLUSIVE；S1 fixture 是直接手写该字段）。
即 **RD007 的「可复算」目前是一项被声明的输入，而不是工具能力**。Phase 2 不掩盖这一点（§7、§18）。

---

## 2. Phase 2 problem

Phase 1 证明的是：给定**已经取证好的**证据，RD001–RD008 能稳定跑。
它刻意回避了接入问题——两个 loader 是「证据映射器」，把 Phase 0 手工取证结果誊进 schema，不发现任何事实。

Phase 2 要回答：面对没见过的项目，**用户最少写什么**，工具才能
（a）跑起来，（b）不把猜测伪装成 provenance，（c）不把「没提供」误报成「有问题」。

---

## 3. Phase 1 实际输入需求（内部映射，来自代码而非叙述）

规则函数只读 `Bundle` 的六个索引 + `Transformation` 表；下表列出**每条规则真正访问的字段**（`?` = 该字段缺失时规则仍运行，但状态被封顶）。

| 规则 | 驱动对象（iterate 目标） | REQUIRED（缺则无 finding 或非判定态） | UNKNOWN-ALLOWED（封顶状态） | 实际封顶效果 |
|---|---|---|---|---|
| RD001 | `ReportedResult` ×1 | `aggregation_ref`、`Aggregation.center`、`SpreadForm.kind/ddof/k`、成员 `observed_value`、`format` 步（`mode`/`digits`） | `member_rule.kind=undeclared`、`run_ref.external_id` UNKNOWN、`produced_by.grade` UNKNOWN、`required_columns` 缺失 | 复现成功仍可 PASS；不符时若上述任一未定 ⇒ INCONCLUSIVE 而非 FAIL |
| RD002 | `Aggregation` ×1 | `member_ids` 与 `members` 的绑定、`member_rule.kind` | `Exclusion.listed` UNKNOWN、`criterion_recomputable=False`、`external_id` UNKNOWN、`observed_value` UNKNOWN | 存在未绑定排除项或「未声明门槛+有排除项」⇒ FAIL；其余匿名/不可重算 ⇒ INCONCLUSIVE |
| RD003 | `SelectionEvent` ×1；另对无 `selection_refs` 的 cell 发 NOT_APPLICABLE | `criterion` 六字段对象存在、`kind` | 六字段任一非 DIRECT、`declared_policy` UNKNOWN、`candidate_values` 空、`promoted_ref` 空 | 六字段全 DIRECT 且政策不被违反才 PASS；无政策 ⇒ INCONCLUSIVE；提升项绑不上 ⇒ INCONCLUSIVE |
| RD004 | `CandidateSet` ×1 | `kind`、`universe_status` | `declared_size`/`surviving_size` 未知、`promotion_evidence` 未知、`identity_collision=None` | 同单位两处矛盾才 FAIL；碰撞或 PARTIAL/UNRECOVERABLE/UNKNOWN ⇒ INCONCLUSIVE；仅 RECOVERED ⇒ PASS |
| RD005 | `ReportedResult` ×1 | `spread.value`、成员值可取、`spread_form` | `spread_label` UNKNOWN、`transformation_refs` 空（成员级变换缺省即恒等） | 无措辞 ⇒ INCONCLUSIVE；n=1 ⇒ INCONCLUSIVE（族重合）；六族都不复现 ⇒ FAIL；措辞与复现族冲突 ⇒ FAIL |
| RD006 | `ReportedResult` ×1 | `transformation_refs` 可解析、`applied_at`、`condition` | 链条为空、`conditional=True` 而条件 UNKNOWN、`declared_source≠observed_source` | 冲突 ⇒ FAIL；链空 ⇒ INCONCLUSIVE（恒等需证据）；纯 identity 链 ⇒ NOT_APPLICABLE |
| RD007 | `ComparisonSet` ×1 | `presentation_rule` 存在（None ⇒ NOT_APPLICABLE） | `observed_marks` UNKNOWN、`external_origin` UNKNOWN、`recomputed_marks` 空 | 同伴值不齐或未恢复标记 ⇒ INCONCLUSIVE；标记集相等 ⇒ PASS；非对称算子使差异两义 ⇒ INCONCLUSIVE |
| RD008 | `ReportedResult` 按 `quantity_key` 分组 + 带 `required_columns` 的 `ResultArtifact` | 分组需 ≥2 个同 `quantity_key` 的 cell；产物检查需 `required_columns` + `columns` | `quantity_key` 为空 ⇒ 该 cell 不进入任何 RD008 target | 单 locus ⇒ INCONCLUSIVE；取值不同 ⇒ FAIL（不猜成因）；缺列 ⇒ FAIL 并点名「存活产物非生产者」 |

未被任何规则读取的字段（Phase 1 现状，generic contract 因此**不必**表达它们）：
`ResultArtifact.sha256/size/note`、`Aggregation.dispersion_expression/parent_aggregation_ref/output_ref`、
`CandidateSet.superseded_by/generation`（仅进 measurements）、`SelectionEvent.effect_on_report`、
`Exclusion.reason_grade/note`、`SourceRef.artifact_id`。这些是 Phase 0 为「可诊断性」保留的记录位，不是判据输入。

---

## 4. RD001–RD008 最小输入矩阵（用户视角）

`REQUIRED` = 不写则该规则无法给出任何有内容的答案；`OPTIONAL` = 提升结论强度；`UNKNOWN-ALLOWED` = 允许不写且不报错；`NOT-USED` = 该规则不读。

| 输入 | RD001 | RD002 | RD003 | RD004 | RD005 | RD006 | RD007 | RD008 |
|---|---|---|---|---|---|---|---|---|
| reported value（+ ± 字符串） | REQUIRED | NOT-USED | NOT-USED | NOT-USED | REQUIRED | REQUIRED | OPTIONAL | REQUIRED |
| members + 每个成员取值 | REQUIRED | REQUIRED | NOT-USED | NOT-USED | REQUIRED | REQUIRED | NOT-USED | NOT-USED |
| center / spread 公式（kind,ddof,k） | REQUIRED | NOT-USED | NOT-USED | NOT-USED | REQUIRED | NOT-USED | NOT-USED | NOT-USED |
| member rule（enumerated / by pattern / by query） | OPTIONAL（封顶 FAIL→INC） | REQUIRED | NOT-USED | NOT-USED | NOT-USED | NOT-USED | NOT-USED | NOT-USED |
| exclusions（清单 + 准则可重算标志） | NOT-USED | REQUIRED | NOT-USED | NOT-USED | NOT-USED | NOT-USED | NOT-USED | NOT-USED |
| member ↔ 外部 run 身份绑定 | OPTIONAL（封顶 FAIL→INC） | OPTIONAL（匿名⇒INC） | NOT-USED | NOT-USED | NOT-USED | NOT-USED | NOT-USED | NOT-USED |
| transformation 链（step + stage + applied_at） | REQUIRED（需 format 步） | NOT-USED | NOT-USED | NOT-USED | OPTIONAL（成员级） | REQUIRED | NOT-USED | NOT-USED |
| artifact 列 + 声明生产者写的列 | OPTIONAL（封顶） | NOT-USED | NOT-USED | NOT-USED | NOT-USED | NOT-USED | NOT-USED | REQUIRED（产物侧检查） |
| selection criterion 六字段 | NOT-USED | NOT-USED | REQUIRED（PASS 需全 DIRECT） | NOT-USED | NOT-USED | NOT-USED | NOT-USED | NOT-USED |
| candidate values + promoted ref | NOT-USED | NOT-USED | REQUIRED（否则不可判） | NOT-USED | NOT-USED | NOT-USED | NOT-USED | NOT-USED |
| candidate universe 状态 + 不可见来源 | NOT-USED | NOT-USED | NOT-USED | REQUIRED | NOT-USED | NOT-USED | NOT-USED | NOT-USED |
| spread 措辞 | NOT-USED | NOT-USED | NOT-USED | NOT-USED | REQUIRED | NOT-USED | NOT-USED | NOT-USED |
| presentation rule + observed marks | NOT-USED | NOT-USED | NOT-USED | NOT-USED | NOT-USED | NOT-USED | REQUIRED | NOT-USED |
| `quantity_key`（跨产物同一量） | NOT-USED | NOT-USED | NOT-USED | NOT-USED | NOT-USED | NOT-USED | NOT-USED | REQUIRED（≥2 locus） |

推论（也是 §14 partial audit 的定义）：**只写前 3 行（reported value + members + 公式）就能跑 RD001/RD005**，
其余规则各自发 NOT_RUN；这是最小可审计单元，不需要用户为了「跑起来」补齐 8 个 section。

---

## 5. Generic input principles

1. 一条事实进入 bundle 当且仅当它**来自 locator 的确定性读出**或**来自用户的显式断言行**；两者都不是 ⇒ `unknown_field()`。
2. 工具可以**报告**文件里有什么（存在、列名、单元格值、字节哈希），不可以报告**文件意味着什么**。
3. 「没写」永远不等于「有问题」；「写了但不可解析」才等于输入错误。
4. manifest 的每个 section 都可为空；空 section 的规则结果是 NOT_RUN，不是 FAIL，也不是 INCONCLUSIVE。
5. 用户写下的每个值都会被记录为 DECLARED 并带上 `manifest:` locator；**没有任何路径**能让手写值获得 DIRECT 等级。
6. 声明可以解锁判定（把 UNKNOWN 提升为 DECLARED 从而允许 FAIL/ PASS），这是设计意图而非漏洞：
   GMMVI 之所以只能停在 INCONCLUSIVE，正因为它连声明都没留下（FM1/FM3）。

---

## 6. Two-door provenance model（冻结为正式约束）

```text
DOOR 1  OBSERVED   locator 在声明的 root 内可解析 + 读法唯一确定（列名/行号/key）
DOOR 2  DECLARED   用户以 `declared:` 键断言，附 `by`（谁声明）与可选 `statement`
OTHER            UNKNOWN
```

与 Phase 1 等级的一一映射：

| 门 | Phase 1 `Grade` | generic path 允许 |
|---|---|---|
| OBSERVED | `DIRECT` | ✔ |
| （规则内部计算） | `DERIVED` | ✔ 只由 `compute.py` 产生，loader 不接受该输入 |
| DECLARED | `DECLARED` | ✔ |
| — | `INFERRED` | **禁止**（Phase 1 两份 bundle 中 INFERRED 命中 0 次，generic 亦不产出） |
| 无 | `UNKNOWN` | ✔ 默认 |

**声明的天花板（写进合同，不靠自觉）**：声明 `universe: complete` 使 RD004 进入 RECOVERED；
但 `declared_size` 与 `surviving_size` 若都来自声明且互相矛盾，RD004 仍会 FAIL —— 声明提供 provenance，不提供 consistency（§9 的要求）。同理用户声明 `spread = standard error` 而成员值只能被 population std 复现时 RD005 = FAIL
（Phase 1 已有实例：TorchSSL 两个 cell 的 `spread_label=declared(...)` + `observed_value=direct(...)` ⇒ FAIL）。

---

## 7. Generic manifest contract

文件：`result-doctor.yml`，放在项目根或经 `root:` 指认的目录之下。
格式选 YAML 的理由：PyYAML 已是 Phase 1 唯一第三方依赖，且需要注释与多行原文（`quoted_text`）。
不引入 JSON Schema 语言、不引入 URI 方案、不做模板引擎。

顶层只有 8 个 section（与 8 对象一一对应，但**作者面被压缩**：id 由 loader 生成，用户不寻址嵌套值记录）：

```text
schema_version / project / root
artifacts:         [{path, columns_observed?, producer?, writes_columns?, supersedes?}]
reported_results:  [{label, printed_in{table,row,column,quoted_text}, quantity?,
                     value{observed|declared}, spread{observed|declared, kind/ddof/k},
                     wording?, members?, aggregate{center}, steps?, selection?, comparison?}]
aggregations:      （由 reported_results[].aggregate 内联生成；排除项在此声明）
candidate_sets:    [{id?, kind, members[], universe?, universe_evidence?, unrecoverable?{reason,evidence},
                     declared_size?, surviving_size?, champion?}]
selection_events:  [{kind, over=candidate_set, chosen, values?, criterion{metric,split,direction,scope,tie,timing}?}]
comparisons:       [{over[reported_result refs], marks?, rule?{expression,operator,symmetric,k_factor}}]
transformations:   （由 reported_results[].steps 内联生成）
```

三条压缩规则，避免「机械复制 8 对象」：
成员、变换步、准则都**内联**在使用它们的 cell 里，只有需要被多处复用时才升级成顶层 `aggregations/candidate_sets/comparisons`；
`ResultArtifact` 只描述文件本身，一切「这文件是什么」的判断都归 cell。

---

## 8. Observation vs declaration vs UNKNOWN（对照表）

| 项目 | 门 | 落到 Phase 1 字段 |
|---|---|---|
| `path` 存在、SHA256、CSV 表头列名、第 N 行第 C 列的数值 | OBSERVED | `ResultArtifact{path,columns}`、`AggregationMember.observed_value=direct()`，locator = `{path, line/row/column}` |
| 「这一列是本项目记录的指标」 | DECLARED | `ReportedResult.metric_name=declared()` |
| 「论文表 2 第 3 行第 5 列印的是 26.69±0.39」 | DECLARED（可 OBSERVED，若用户给 PDF 页文本 locator；Phase 2 不实现 PDF） | `Locus` + `value=declared()`，locator 前缀 `manifest:` |
| 「这 4 个 run 就是那次平均的成员」 | DECLARED | `Aggregation.member_ids` + `member_rule.kind=enumerated, grade=DECLARED` |
| 「选择依据是验证集 top-1 最大」 | DECLARED（若同时给出代码 locator 则 OBSERVED） | `SelectionCriterion.split/direction=declared()/direct()` |
| candidate universe 有多大 | 默认 UNKNOWN | `universe_status=UNKNOWN`（**不降级为 singleton**） |
| 被剔除 run 的原因 | UNKNOWN | `Exclusion.reason_grade=UNKNOWN` |
| 文件名 `best.pt` / `seed_42/` / `final/` / `mean.csv` | 不进门 | 不产生任何字段；见 §11 禁止清单 |
| 目录里只剩 3 个 run | 不进门 | 不得成为 `surviving_size` 之外的任何断言 |

---

## 9. 用户声明不能自动等于 PASS（合同化）

三句可检验的约束：

1. `declared:` 只写进对应字段的 `EvidenceField.grade=DECLARED`，**不写进任何 `observed_value`**：
   成员值必须有 locator 才能成为 DIRECT，用户若只想写数字，则该成员值记为 DECLARED，
   此时 RD001 的复算仍在做（它比较的是声明的模型与声明的数字是否自洽），但 finding 的 evidence 指向 manifest。
2. 判定权始终在复算侧：RD001/RD005/RD006 都不读 `declared` 的*措辞*来决定 PASS，措辞只在 RD005 里作为**被检验对象**。
3. 归因可读性不靠改规则：generic loader 写入的 `SourceRef.path` 一律以 `result-doctor.yml#<section>/<index>` 开头，
   因此 RD001 的「members, aggregation and transforms are all determined yet the cell differs」这类 FAIL
   在 evidence 列表里就机械可辨为「用户声明模型内部不自洽」，与 GMMVI 那种「产物列缺失」型 FAIL 天然区分。
   **规则函数与 reason 模板保持不动。**

---

## 10. 最小字段清单（每字段回答：谁需要 / 哪个 FM / 可否 UNKNOWN / 可否自动观察 / 可否声明）

只列被规则读取的字段；「删」= 从 contract 中删除。

| 候选字段 | 需要的规则 | 动机 FM | 可 UNKNOWN | 可 OBSERVED | 只能 DECLARED | 结论 |
|---|---|---|---|---|---|---|
| `value{observed\|declared}` | RD001/005/006/008 | FM1 FM13 | 否（缺 ⇒ cell 不成立） | ✔（表格文本） | ✔ | 必留 |
| `members[{path,column,row\|selector}]` | RD001/002/005 | FM3 | 否（缺 ⇒ RD001/002/005 NOT_RUN） | ✔ | ✔（内联值） | 必留 |
| `aggregate.center ∈ {mean,median}` | RD001/005 | FM6 | 默认 `mean` 但需声明来源 | ✘ | ✔ | 必留 |
| `spread{kind,ddof,k}` | RD001/005 | FM6 FM7 | ✔（`none`） | ✘（公式不是产物） | ✔ | 必留 |
| `wording` | RD005 | FM6 FM7 | ✔（⇒ INCONCLUSIVE） | ✔（caption locator） | ✔ | 必留 |
| `steps[{step,stage,params}]` | RD001/005/006 | FM11 FM2 | ✔（⇒ RD006 INCONCLUSIVE） | ✘ | ✔ | 必留（`format` 步是 PASS 的前提） |
| `member_rule` | RD002 + RD001 封顶 | FM5 FM1 | ✔（⇒ 只能 INCONCLUSIVE） | ✘ | ✔ | 必留 |
| `exclusions[{member,criterion_recomputable}]` | RD002 | FM4 | ✔ | ✔（`.bad` 这类同构惯例） | ✔ | 必留 |
| `identity{run_id}` | RD001 封顶 + RD002 | FM3 | ✔ | ✘（Phase 1 两份归档都拿不到） | ✔ | 必留（声明即可解锁 FAIL） |
| `producer{script,call,line}` / `writes_columns` | RD008 产物侧 + RD001 封顶 | FM2 | ✔ | ✔（脚本行可 OBSERVED） | ✔ | 必留 |
| `quantity` | RD008 | FM13 | ✔ | ✘ | ✔ | 必留 |
| `universe` + `unrecoverable{reason,evidence}` | RD004 | FM9 FM10 | ✔（默认） | ✔（过滤器代码行） | ✔ | 必留 |
| `criterion{六项}` | RD003 | FM8 | ✔ | ✔（代码 locator） | ✔ | 必留 |
| `values` + `chosen` | RD003 | FM8 | ✔（⇒ 不可判） | ✔（日志列） | ✔ | 必留 |
| `marks` + `rule{expression,operator,symmetric,k_factor}` | RD007 | FM12 | ✔ | ✔（表格粗体需产物含标记列） | ✔ | 必留，但见 §18 的天花板 |
| `sha256` / `size` / 自由 `note` | 无规则读取 | — | — | ✔ | ✔ | **删**（仅可作 evidence 文本，不作字段） |
| `dispersion_expression`（自由公式串） | 无规则读取（RD005 只枚举六族） | FM6 | ✔ | ✔ | ✔ | **降级**为注释性 `statement`，不参与计算 |
| `parent_aggregation_ref` / `output_ref` / `effect_on_report` / `generation` / `superseded_by` | 无判据读取 | FM2 FM9 | ✔ | ✔ | ✔ | **删**（adapter 内部可用，不进 contract） |

结论：**没有新增字段需求**。8 对象在 generic path 上全部可被填到「有证据」或「UNKNOWN」两种状态之一，无需 Phase 1 schema 改动。

---

## 11. Generic loader 边界（自动发现的安全集与禁止集）

**允许自动做**：解析 manifest；检查 `root` 下的 path 存在；算 SHA256；读 CSV 表头；按 `row/column` 或 `line` 读值；
读 JSON 的显式 key；把 `observed:` 读出的值转成 float（失败即输入错误）。

**永远不做（Phase 3 以测试钉死）**：

```text
best.pt        → best checkpoint
seed_42/       → seed=42
results.csv    → metric of record
mean.csv       → 最终 aggregation
final/         → 最终结果
同名 wandb.group / 目录名相同 → 同一 CandidateSet
目录中 run 的个数 → candidate universe 的大小
文件名/目录名/stdout 文本的任何语义
```

**安全约束**：所有 path 必须位于 `root` 之下（拒绝绝对路径与 `..`）；越界 = 输入错误。
这既防误读，也顺带排除「loader 顺手遍历仓库」的退化路径——它**没有**遍历能力。

**hint 系统不做**：Phase 1 证据显示所有线索要么能升级为 OBSERVED（给出 locator），要么是猜测；
不存在「值得作为 hint 保留但不作事实」的中间态被两个归档实际用到。若 Phase 3 之后出现，再设计。

---

## 12. Validation error vs scientific unknown

| 输入错误（loader 抛错，audit 不运行） | 科学未知（正常运行，产出状态） |
|---|---|
| 引用不存在的 object id（cell 指向无成员聚合、selection 指向无候选集） | 该 cell 没有 selection event（⇒ RD003 NOT_RUN） |
| 枚举 token 非法（`center=trimmed_mean`、`kind=mad`、`step=softmax`） | universe 状态未知（⇒ RD004 INCONCLUSIVE） |
| 该是数字处不是数字（成员值、`k`、`ddof`、`tie_tolerance`） | 措辞缺失（⇒ RD005 INCONCLUSIVE） |
| path 不存在 / 越出 root / locator 越界（列名不在表头、行号超范围） | 排除原因不知道（⇒ RD002 INCONCLUSIVE，`criterion_recomputable=False`） |
| 同一 section 内 id 重复；`steps` 含 compute 层不施加的步（见 §18） | 标记未被恢复（⇒ RD007 INCONCLUSIVE，等级 UNKNOWN） |
| YAML 语法错误、`schema_version` 不支持 | 引用了外部基线且内容不可访问（⇒ RD008 定位 dependency gap，不猜） |

一句话纪律：**证据不足不是 parser error；结构不可解析也不是 UNKNOWN。** 二者输出通道不同（异常 vs finding 状态向量）。

---

## 13. Partial audit 语义（含 NOT_RUN 的落地位置）

Phase 1 现状：`RD002/003/004/007/008` 对空 target 类**产出 0 条 finding**，与「跑过且无问题」在 JSON 里不可区分。
generic path 需要区分，因此冻结：

- 由 **generic 入口层**（`evaluate(bundle)` 的调用方，Phase 3 新增的 `audit_manifest()`）在规则输出之后追加：
  凡 target 数为 0 的规则，补一条 `RuleFinding(rule_id, target="rule:RDxxx", status=NOT_RUN, reason="no target of this class was supplied")`。
- **不改规则函数、不改 schema、不改状态词表**（NOT_RUN 是 Phase 0 五态之一，Phase 1 全程未使用它）。
- 因此 Phase 1 legacy path 的输出字节不变（两个归档的 target 类都非空），零回归。

partial audit 的合法结果示例（不是失败）：

```text
RD001 PASS   RD002 PASS   RD003 NOT_RUN   RD004 INCONCLUSIVE   RD005 PASS
RD006 PASS   RD007 NOT_RUN   RD008 INCONCLUSIVE(单 locus)
```

---

## 14. Adapter 与 generic 的关系（架构约束，冻结）

1. 两条入口必须汇聚到同一个 bundle：`load_gmmvi_bundle(root)` 与 `bundle_from_manifest(yml)` 都返回同一个 `Bundle`，
   之后走同一份 `evaluate()`。**禁止** project-specific 规则集（Phase 0/1 已确立，Phase 2 再次冻结）。
2. adapter 的唯一正当性：它能 OBSERVE 到 manifest 作者不可能逐个写的东西
   （GMMVI：500 个成员末行值、128 个产物列清单、98 个选择事件的候选值、1074/1152 点网格抽检）。
   判据：**adapter 只为「重复声明次数 ≥ 手工声明成本」的项目存在**。GMMVI/TorchSSL 满足；3-cell 项目不满足。
3. adapter 与 generic loader 受**同一** two-door 约束：adapter 不得因为它「懂这个项目」而输出 manifest 会被拒为猜测的事实
   （反例警戒：把 `run_3.csv` 判成 seed 3 —— Phase 1 里 `external_id` 一律 UNKNOWN 正是这条纪律的体现）。
4. 新项目的默认路径是 manifest；只有当同一项目要被反复审计时才升格为 adapter，且升格后必须能复用 Phase 1 的验收方式
   （oracle 向量 + 反例锁定 + 防火墙）。

---

## 15. CandidateSet 的 generic 语义

```text
universe_status 默认 UNKNOWN
RECOVERED   ← 用户声明 `universe: complete` 且给 evidence locator（或成员清单本身即被声明为全集）
PARTIAL     ← 声明了部分成员 + 明确存在未纳入来源
DECLARED_ONLY ← 只有声明、无 locator
UNRECOVERABLE ← 必须给 `unrecoverable: {reason, evidence}`；「没找到」不升级
```

映射到既有枚举（**不新增 `COMPLETE`**，brief §20 的 COMPLETE 语义由 `RECOVERED` 承担）。
`declared_size` 与 `surviving_size` 保持为两个独立证据字段：
「列出的成员 = 3」永远不等于「宇宙 = 3」（Phase 1 的 TorchSSL 实例：declared 3 vs surviving 6 因单位不同而**不是**矛盾，
`sizes_stated_in_same_unit=False` ⇒ INCONCLUSIVE）。generic contract 因此要求二者各带 `statement` 才能被比较。

## 16. SelectionEvent 的 generic 语义

- `kind` 必须落在既有五类（checkpoint/run/hyperparameter/model/reported_result）；`dataset_level` 亦可选。
- 六个准则字段全部可缺，缺 ⇒ 该字段 UNKNOWN ⇒ RD003 至多 INCONCLUSIVE（Phase 1 的 `table_exp1.py` 型「仅代码隐含」即此状态）。
- `direction` 必须字面以 `min`/`max` 开头（`direction_is_minimizes` 用 `startswith("min")` 判定）；其他写法 = 输入错误，不做语义猜测。
- `values` 与 `chosen` 是「声明还是观察」的分水岭：`chosen` 可由产物路径 OBSERVED（如持久化 `model_best.pth`），
  但「它是被这个准则选中的」必须 DECLARED。
- 不强迫用户伪造 selection policy：无政策 ⇒ RD003 INCONCLUSIVE 是**正确**结果，不是缺失。

---

## 17. Aggregation / Transformation contract（只支持已被实现的东西）

**Aggregation**：`center ∈ {mean, median}`（`compute.center` 只有这两个）；
`spread.kind ∈ {none, std, sem, k_sem}`、`ddof ∈ {0,1}`、`k` 数值；`n` 一律由成员数派生，**不接受用户声明 n**。
`dispersion_expression` 只作人读说明。

**Transformation**：允许用户写的步 = Phase 1 已验证需要的类型：

```text
scale(factor) · sign_flip · sum_of_part(parts) · format(mode∈{fixed,str_round}, digits) · identity
```

以下步**接受但不参与复算**，因而若出现在 `member/center/dispersion` 阶段即判为输入错误：
`round · delta · best_of_n · truncate_window`（`compute.apply_stage` 对它们是 `continue`）。
这条校验是 Phase 2 新发现的**假通过风险**：若允许 `delta` 进入成员阶段，RD001 会把它当恒等并给出错误的 PASS/FAIL。
`render` 阶段只允许 `format`；无 `format` 步的 cell 允许存在，其 RD001 结果为 INCONCLUSIVE（`rendering_undeclared`）。
禁止：`eval()`、Python 片段、任意代码、符号表达式语言。

## 18. Presentation 的诚实边界

generic path 的 RD007 能力被 Phase 1 事实限制：`recomputed_marks` 不是被计算的。因此合同规定：

- 用户必须**同时**给 `marks`（产物里实际呈现了哪些标记）与 `rule`（比较规则）；两者各自带门/等级。
- 工具做的检查是「规则与同伴取值是否蕴含用户报告的标记集」，其中蕴含一步由 **adapter 或 manifest 的 `marks_derivation` 断言**给出。
- 由此 RD007 在 generic path 的 PASS 语义是「两处声明一致」，其 evidence 必然同时指向 `marks` 与 `rule` 两个 locator。
  **禁止**把它读成「工具自行复算了加粗」。Phase 1 的 S1 fixture 正是这个形态（手写 `recomputed_marks`）。
- 若项目存在机器可读的呈现标记（表格列里带 `**`、或有生成脚本），adapter 可将其 OBSERVED；这是 adapter 的正当用途之一。

---

## 19. 证据引用（Phase 1 结构是否够用）

够用，**无需新增字段**。`SourceRef{path, key, line, artifact_id, note}` 的承载方式：

```text
path      = 相对 root 的产物路径 或 "result-doctor.yml#reported_results[2]/members[0]"
line      = 行号 / 行范围（CSV 行、脚本行）
key       = locator：column:<名> · row:<n> · key:<json pointer> · text:"<原文片段>"
artifact_id = manifest 内被引用对象的生成 id（Phase 1 未使用，generic path 启用它）
note      = 人类可读说明（唯一允许的自由文本）
```

不设计 citation language、不设计 URI scheme：locator 只有上述四种，且必须是**可确定性重放**的读法。

---

## 20. Generic examples

### Example A — 最小可审计结果（3 seeds，mean ± population std，无 selection）

```yaml
schema_version: 1
project: tiny-demo
root: .
reported_results:
  - label: acc/cifar-resnet20
    printed_in: {table: "Table 2", row: ResNet-20, column: Acc, quoted_text: "94.12 ± 0.31"}
    quantity: acc/cifar-resnet20            # 只出现一次也没关系：RD008 会给 INCONCLUSIVE
    value:   {observed: {path: paper/table2.txt, line: 7, key: "text:\"94.12 ± 0.31\""}}
    spread:  {kind: std, ddof: 1, k: 1}
    wording: {observed: {path: paper/table2.txt, line: 3, key: "text:\"mean ± SD over 3 seeds\""}}
    aggregate: {center: mean}
    members:
      - {path: runs/a/log.csv, column: test_acc, row: last}
      - {path: runs/b/log.csv, column: test_acc, row: last}
      - {path: runs/c/log.csv, column: test_acc, row: last}
    member_rule: {kind: enumerated, statement: "these three runs are the reported mean"}
    steps:
      - {step: format, stage: render, mode: fixed, digits: 2, applied_at: manual}
```

映射与预期：RD001 可 PASS/FAIL（成员 OBSERVED + 公式声明 + format 步声明 ⇒ 无 UNKNOWN 封顶，除非 `member_rule` 或身份未定）；
RD002 PASS（enumerated + 无排除项）；RD005 检验 `wording` 说的 std 与复现族是否一致；RD006 PASS（链已枚举）；
RD003/RD004/RD007 = **NOT_RUN**（未提供该类对象）；RD008 = INCONCLUSIVE（单一 locus）。
**这份 manifest 不能得出的结论**：宇宙完整性（未声明 ⇒ UNKNOWN，绝不读成「只有 3 个候选」）。

### Example B — 含 checkpoint selection

```yaml
schema_version: 1
project: tiny-demo-with-ckpt
root: .
reported_results:
  - label: acc/x
    printed_in: {table: "Table 1", row: A, column: Acc, quoted_text: "91.4"}
    value: {declared: {by: author, statement: "the paper prints 91.4"}}
    aggregate: {center: mean}
    members:
      - {path: ckpt/r1/test_acc.txt, selector: best}
      - {path: ckpt/r2/test_acc.txt, selector: best}
      - {path: ckpt/r3/test_acc.txt, selector: best}
    member_rule: {kind: enumerated}
    steps: [{step: scale, factor: 100, stage: member, applied_at: script},
            {step: format, stage: render, mode: fixed, digits: 1, applied_at: manual}]
candidate_sets:
  - kind: checkpoint
    members: [ckpt/r1/ep10.pt, ckpt/r1/ep20.pt, ckpt/r1/ep30.pt, ckpt/r2/ep10.pt, "..."]
    universe: complete
    universe_evidence: {observed: {path: train.py, line: 88, key: "text:\"for epoch in range(30)\""}}
selection_events:
  - kind: checkpoint
    over: 0
    chosen: ckpt/r1/ep30.pt
    values: {observed: {path: ckpt/r1/val.json, key: "key:/acc"}}
    criterion:
      metric:    {observed: {path: train.py, line: 96, key: "text:\"val_acc\""}}
      split:     {declared: {by: author, statement: "validation split"}}
      direction: {observed: {path: train.py, line: 97, key: "text:\"if val_acc > best\""}}
      scope:     {declared: {by: author, statement: "per run"}}
      tie_break: {unknown: true}
      timing:    {observed: {path: train.py, line: 97, key: "text:\"in training loop\""}}
comparisons:
  - over: [acc/x, acc/y]
    marks: {observed: {path: paper/table1.txt, line: 5, key: "text:\"**91.4**\""}}
    rule: {expression: "bold iff strictly greater than every peer", operator: ">", symmetric: true, k_factor: 1}
    marks_derivation: {declared: {by: author, statement: "bold set recomputed from the printed values"}}
```

映射与预期：RD001 若 `value.declared` 的 91.4 与成员复算不符 ⇒ **FAIL**（成员 OBSERVED、链完整、`member_rule` 已声明 ⇒ 无封顶），
evidence 指向 manifest ⇒ 可读为「声明模型内部不自洽」；RD003 = PASS 需要六字段全 DIRECT，
本例 `split/scope` 为 DECLARED、`tie_break` 为 UNKNOWN ⇒ **INCONCLUSIVE（正确，不是失败）**；
RD004 = PASS（universe 声明 + 代码 locator）；RD007 处于 §18 的「两处声明一致」语义；
RD005 = NOT_APPLICABLE（该 cell 无 ±）。
`steps` 里若有人写 `delta` 于 member 阶段 ⇒ **输入错误**（§17）。

---

## 21. Firewall（Phase 3 必测清单）

§24 的 7 条 + 本轮设计新暴露的 4 条：

```text
missing field            ≠ false fact
listed candidates        ≠ complete universe
declared evidence        ≠ direct observation
best filename            ≠ best-checkpoint provenance
same directory           ≠ same aggregation
same group               ≠ same candidate universe
successful parse         ≠ scientific completeness
declared identity        ≠ observed identity          （解锁 FAIL 资格，不改变事实强度）
declared marks           ≠ recomputed marks            （RD007 的 PASS 只声明两处声明一致）
unapplied transform step ≠ applied step                （member/center/dispersion 阶段直接判输入错误）
inline value             ≠ artifact cell value         （等级恒为 DECLARED）
```

外加两条结构闸（延续 Phase 1）：generic 输出不得引入任何评分字段/对象；
`bundle_from_manifest()` 之后的 bundle 与 adapter 之后的 bundle 必须是同一 dataclass 集合（禁止 manifest 专用 schema）。

---

## 22. Rejected designs（附理由，均为本轮实际考虑并否决的候选）

| 被否决 | 理由 |
|---|---|
| 自动仓库扫描器 / 目录发现 | 与 §3「generic ≠ 猜」直接冲突；Phase 1 两个归档证明目录惯例本身要取证才能用 |
| hint 层（文件名候选 + 人工确认） | 无真实承载对象：观察能升级的就升级，升不了的是猜测；徒增状态 |
| manifest = 8 对象的直接序列化 | 逼用户写 id/selector/grade ⇒ 更易错，且会出现假的 `grade: DIRECT`（用户手写等级） |
| JSON Schema / URI citation 语言 | locator 四种已够；标准化不带来新判定能力 |
| 通用表达式或 NumPy 执行器 | 引入不可判定复算与安全问题；`_FAMILIES` 与 `STAGES` 的封闭枚举才是可审计性的来源 |
| `universe_size` 单一字段 | 抹掉 declared/surviving 的区分，正是 FM10 的来源 |
| 规则内部发 NOT_RUN | 会改 Phase 1 规则函数与输出向量（回归风险）；入口层追加即可 |
| 为 FAIL 归因新增 `input_grades` 测量字段 | 可用现有 evidence 的 locator 前缀机械区分，不值得改规则 |
| 第三个真实项目 | 见下 |
| 新增 RD009（如「test 指标参与选择」） | 判据已覆盖所需证据面；跨入结论性宣称，Phase 0 已明确舍弃 |

**§25 的答案：不需要第三个项目。** 剩余两处真正的设计分叉是（a）呈现标记的复算来源、（b）universe 完整性的证据门槛，
两者都由**原则**（声明天花板、two-door）判定而非由新证据判定：GMMVI 给了「无标记恢复 + 无声明」的下界，
TorchSSL 给了「有观察 + 措辞冲突」的上界，两端已把 RD007/RD004 的可达状态空间钉满；
再多一个项目只会重复同一形态，并把范围推回「为完整而加 acceptance」。

---

## 23. Phase 3 acceptance oracle

| 用例 | 输入 | 预期（状态向量层面） | 反向不变式 |
|---|---|---|---|
| **G1 最小 generic 项目** | Example A 原样 | RD001/002/005/006 PASS；RD003/004/007 NOT_RUN；RD008 INCONCLUSIVE | 不得凭空出现 selection/candidate 相关 target |
| **G2 证据不全** | A 去掉 `member_rule` 与 `wording`，成员值改 `declared` | RD001 不符时 INCONCLUSIVE（不 FAIL）；RD002 INCONCLUSIVE；RD005 INCONCLUSIVE | **不得 parser error**；不得因缺字段而整体失败 |
| **G3 假推断防火墙** | 目录内放 `best.pt/seed_42/final/mean.csv`，manifest 不提它们 | 对应 target 不存在或字段 UNKNOWN；bundle 成员数不受文件名影响 | 文件名任一子串不得出现在 evidence 之外的事实里 |
| **G4 声明不一致** | 声明 `wording: "standard error"`，成员值只有 ddof=0 std 能复现 | RD005 **FAIL**；RD001 仍可 PASS | 措辞声明不得使 RD001 升格或降格 |
| **G5 外部产物不可访问** | `comparisons.over` 引用外部基线，`external_origin: {unknown}`，外部路径不存在但**未被 cell 直接引用** | RD007 INCONCLUSIVE（peer 值不可恢复）；RD008 定位到缺 locus | 不得因外部不可访问而 FAIL 或猜测其取值 |
| **G0 零回归** | Phase 1 全套 | 76 tests 全绿；两归档 `canonical_json` 字节不变 | generic path 不得触碰 legacy 输出 |

---

## 24. Phase 3 唯一最小范围

```text
generic manifest loader（result-doctor.yml + root 内 locator → 同一个 Bundle）
+ §17/§12 的输入校验错误枚举
+ 入口层 NOT_RUN 追加（audit_manifest）
+ G0–G5 验收与 §21 防火墙
```

不含：仓库扫描器、paper/PDF parser、tracker API、GUI、server、database、agent、第三个项目、RD009、schema 改动。

---

## 25. 成功标准核对（brief §31）

| # | 问题 | 回答位置 |
|---|---|---|
| 1 | 未见项目如何接入 | §7 contract + §20 示例 |
| 2 | 最小 manifest 是什么 | §4 推论 + Example A（1 个 cell、3 行输入） |
| 3 | 哪些事实自动观察 | §11 允许集 |
| 4 | 哪些必须显式声明 | §8 表 + §10 每字段的门 |
| 5 | 哪些必须 UNKNOWN | §8 第三段 + §15/§16 |
| 6 | partial audit 如何工作 | §13 |
| 7 | validation error 与 scientific unknown 如何分 | §12 |
| 8 | generic 与 adapter 边界 | §14 四条 |
| 9 | 如何防 heuristic provenance | §6 two-door + §11 禁止清单 + §21 防火墙 |
| 10 | Phase 3 最小范围 | §24 |

---

## 26. Phase 2 verdict

**CLOSED。** 十条问题全部有唯一答案，且不依赖任何未取证的新项目。
本轮未编码、未修改 Phase 1 的 schema / 规则 / 状态词表 / 验收 oracle，未改写 Phase 0 原报告。

**唯一下一步**：按 §24 实现 Phase 3 —— 只写 `result-doctor.yml` 的 generic manifest loader（含 §12 校验错误枚举与 §17 变换白名单）、
入口层 NOT_RUN 追加，并以 §23 的 G0–G5 作为验收。
