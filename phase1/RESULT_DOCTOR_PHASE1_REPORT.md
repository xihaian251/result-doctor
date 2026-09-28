# Result Doctor — Phase 1 最小实现关闭报告

- 日期：2026-09-28
- 上游权威：`phase0/RESULT_DOCTOR_PHASE0_REPORT.md`（Phase 0 / Design：CLOSED，Verdict：YES）
- 本轮性质：实现已冻结的最小设计，不是重新设计
- 状态：**Phase 1 CLOSED**（§24 的 11 条判据逐条通过，见 §12）
- 代码位置：`F:\MLResearch\result-doctor\{src/result_doctor,tests,pyproject.toml}`

---

## 1. 一句话结论

在两个冻结归档上，Result Doctor 已经能把「论文里被报告的数字」确定性反推到「成员 / 聚合 / 变换 / 选择 / 候选集」证据链，
并在证据断掉的地方**精确说出断在哪一层**（51 个单元格逐位复现、5 个单元格定位到成员身份、5 个定位到产物列缺失），
全程不产生任何评分、不出现任何对科研行为的定性词。

---

## 2. 交付物清单

| 文件 | 行数 | 职责 |
|---|---|---|
| `src/result_doctor/evidence.py` | 76 | `Grade` / `SourceRef` / `EvidenceField` + `direct/declared/derived/unknown_field` |
| `src/result_doctor/status.py` | 66 | 五态 + `UniverseStatus` + `RuleFinding` + `canonical_json` |
| `src/result_doctor/schema.py` | 312 | 8 个 Phase 0 对象 + 11 个嵌套值记录（共 19 个 dataclass） |
| `src/result_doctor/bundle.py` | 73 | 只读容器与 `chain/included/members_of` 等确定性访问器 |
| `src/result_doctor/compute.py` | 98 | `std/dispersion/center/render/apply_stage`（RD001/RD005/RD006 复用） |
| `src/result_doctor/rules.py` | 834 | RD001–RD008，全部确定性判断 |
| `src/result_doctor/loaders/gmmvi.py` | 760 | GMMVI exp3 冻结归档 → bundle（链 A/B/C + 网格代际） |
| `src/result_doctor/loaders/torchssl.py` | 368 | TorchSSL 冻结归档 → bundle（best-checkpoint + 生成工作簿） |
| `tests/`（5 测试文件 + fixtures） | 1428 | 76 个测试 |

全仓 16 个 `.py` 共 4045 行。行数已含 `ruff format` 的结果；论文誊抄表
（`ELBO_CELLS / SECONDARY_CELLS / TABLE5_ELBO`）用一对 `# fmt: off / # fmt: on` 保住「一行一个印刷单元格」的排版，
使其仍能与论文表格逐行对照——这是格式化门禁下唯一保留的版式例外。

**未创建** `docs/`（§20 列出的目录）：Phase 1 唯一文档产物就是本报告，建空目录或复述 Phase 0 内容都会造出无信息模块。已登记为偏差 D11。

---

## 3. Schema 落地情况（8 对象）

Phase 0 §10 的 8 个对象全部落地，且**只有**这 8 个是顶层对象；其余 11 个是它们的嵌套值记录，不进入独立索引。

| 对象 | 字段数 | 服务的失败模式（Phase 0） |
|---|---|---|
| `ReportedResult` | 13 | FM1 FM2 FM6 FM7 FM13（锚定被报告值 + locus + quantity_key） |
| `ResultArtifact` | 9 | FM2（`required_columns` × `produced_by` ⇒ 覆盖/替换可诊断） |
| `Aggregation` | 9 | FM3 FM4 FM6（成员规则、离散度表达式、排除项） |
| `AggregationMember` | 6 | FM3（`external_id` 常为 UNKNOWN，而 `observed_value` 为 DIRECT） |
| `CandidateSet` | 10 | FM9 FM10（`declared_size` 与 `surviving_size` 独立 + `unobservable_sources`） |
| `SelectionEvent` | 10 | FM5 FM8（6 个准则字段各自带等级、`is_recorded`、`tie_tolerance`） |
| `ComparisonSet` | 6 | FM12 FM14（`observed_marks` 是证据字段而非列表；`external_origin`） |
| `Transformation` | 9 | FM11 FM2（`step` × `applied_at` × `condition` ⇒ 未触发分支 ≠ 未施加） |

明确不存在的对象（防火墙测试逐条钉死）：`ResultDAG`、`MetricRecord`、`ClaimRef`、`TrackerConnection`，
以及任何形式的 `TrustScore / ConfidenceScore / PaperScore`。
`schema.py` 中没有 seed / git / environment / resolved-config / termination 字段：上游 provenance 只以路径与行号被引用。

---

## 4. 规则实现与真实证据上的状态向量

规则语义沿用 Phase 0 §11–§14 的最终命名与边界，未改语义。每个 finding 输出
`rule_id / rule_name / target / status / question / measurements / evidence / reason`；**没有跨规则聚合**。

GMMVI 归档（59 单元格、128 产物、46 聚合、500 成员、98 选择事件、100 候选集、5 比较集、3 变换）→ 538 份 finding：

| 规则 | PASS | FAIL | INCONCLUSIVE | NOT_APPLICABLE |
|---|---|---|---|---|
| RD001 复算 | 51 | 0 | 5 | 3 |
| RD002 成员可导出 | 0 | 0 | 46 | 0 |
| RD003 选择准则 | 0 | 4 | 94 | 59 |
| RD004 候选集可恢复 | 0 | 0 | 100 | 0 |
| RD005 ± 语义 | 54 | 2 | 0 | 3 |
| RD006 变换链 | 51 | 0 | 5 | 3 |
| RD007 呈现依赖 | 0 | 0 | 4 | 1 |
| RD008 跨产物一致 | 9 | 5 | 39 | 0 |

TorchSSL 归档（3 单元格、6 产物、2 聚合、6 成员、6 选择事件、7 候选集）→ 31 份 finding：
RD001 `2 PASS / 1 NA`；RD002 `2 PASS`；RD003 `6 PASS / 1 NA`；RD004 `6 PASS / 1 INCONCLUSIVE`；
RD005 `2 FAIL`；RD006 `2 PASS / 1 FAIL`；RD007 `3 NA`；RD008 `3 INCONCLUSIVE`。

两点值得单独说明，因为它们**不是**缺陷：

- **RD002 在真实归档上 46/46 INCONCLUSIVE**：每个成员都无法绑定到外部 run id（FM3），而剔除准则不可重算（FM4）。
  这正是规则该给的答案——不是「成员检查通过」，也不是「成员被操纵」。
- **RD004 在 GMMVI 上 100/100 INCONCLUSIVE**：`RECOVERED` 分支存在（网格 adopted 走通并被 fixtures 覆盖），
  但 FM9 的同名跨代分支先于它命中，于是两个网格代际都停在 INCONCLUSIVE 并显式声明不作断言。

---

## 5. 合成夹具 S1–S5（§16）

`tests/synthetic_fixtures.py` 手写、规模小、人可复算；只测真实语义边界，**不做 8×5 笛卡尔矩阵**。

| 夹具 | 被测边界 | 关键状态 |
|---|---|---|
| S1 干净闭环 | 复现 + 跨产物一致 + 呈现可复算 | 8 规则全 PASS（S1/B 单元格单一 locus 给 RD008 INCONCLUSIVE） |
| S2 成员身份断裂 | 生产者 UNKNOWN + 缺列 + 匿名成员 | RD001/002/004/006 INCONCLUSIVE，RD008 FAIL（产物），RD005 仍 PASS |
| S3 ± 措辞与公式 | 一处无声明、一处措辞与公式冲突 | RD005 INCONCLUSIVE + FAIL，其余不连带 |
| S4 选择偏离声明 | 声明「取最优」而提升非冠军 | RD003 FAIL，**同一链上 RD001 仍 PASS**（偏离不污染算术） |
| S5 隐形候选 | PARTIAL + IdentityCollision、UNRECOVERABLE + 不可见来源 | RD004 两条 INCONCLUSIVE，测不到 `universe_size` 字段 |

共 59 份 finding，`tests/test_synthetic_oracle.py`（18 测试）做**精确状态向量相等**，并要求每条 finding 都带证据与理由。

---

## 6. GMMVI 冻结验收（§14）

**链 A — 闭环成立。** `TALOS/sepyfux/entropy/Table 8` 的 `−25.03 ±5.46` 由 4 个非 `.bad` run 的末行、
ddof=0、`std*3/sqrt(4)`、`%.2f` 独立取整逐步重算得出，逐位一致；整条 TALOS 行 18/18 PASS。
两个锁定反例被钉死为「工具不得误判为正确」：
- 同公式取 ddof=1 ⇒ `±6.31`（六族渲染表里只有 `k_sem_ddof0_k3` 命中发布值）；
- 把 6 个 `.bad` 也当成员（n=10）⇒ `−45.32 ±42.91`，与发布值不符，而 RD002 仍记录 10 成员 / 4 纳入 / 6 排除。

**链 B — 断点被精确命名，而不是「论文错了」。** BC 的 4 个已转录单元格（`samtron` 两表各一次 + `sepyfux / sepyrux`）
值为 `78.00±0.02 / 79.78±0.40 / 79.91±0.93`：
RD001 = INCONCLUSIVE，理由链是「成员身份不可判定」；RD008 = FAIL，`missing ["MMD:"]`，
理由明说存活产物**不是**产生该单元格的那个产物（生产者等级 UNKNOWN）。
RD006 在同一批单元格上给出同样的 INCONCLUSIVE（分支归属未定），而 RD005 反而是 PASS：
三/六族都能打印 `0.02`，断点全在中心值。RD001 的 5 个 INCONCLUSIVE = 这 4 格 + `STM300/sepyfux/Table 5`
（FM13 孪生格与 Table 8 重算不符，但身份断点在上游，故不升格为 FAIL）。

**链 C — 候选 / 选择 / 声明 / 不可恢复四件分开表达。** 98 个搜索组：91 组冠军=提升项（gap 0.0）、
4 组 FAIL（如 `GMM100/sepyrux` 0.675964 vs 1.138794）、1 组按声明精度算作近并列（`GC/samtrux` gap 0.000916）、
2 组提升项无法绑定（INCONCLUSIVE）。98/98 的 `is_recorded=False`：冠军只被打印，从不落盘。

**网格代际（FM9）。** adopted 1074 点 / discarded 1152 点，`wandb.group` 复用 35 次。
RD004 的理由既不说「两个 grid 相同」也不说「完全无关」，而是给出抽检统计（7 组键集完全相同、
0 组值不相交、14 组部分重叠、21 组共有键取值全等）后停在 INCONCLUSIVE。

**FM12 / FM13 / FM14。** 呈现标记以 UNKNOWN 等级记录（「未恢复」≠「没有标记」），非对称算子使边界情形两义；
`quantity:STM300/sepyfux/-elbo` = FAIL，值 `{26.69, 26.87}` / 宽 `{0.39, 0.45}`，理由含「is not determined here」且不出现 typo 猜测；
3 组一致对给 PASS；外部基线 `artifact:repo/evaluations/iBayesLR_results` = FAIL（缺 `track_elbos`、`track_n_fevals`），
VIPS 单元格在 RD001/RD006 上是 NOT_APPLICABLE 而非「已校验」。

---

## 7. TorchSSL 冻结验收（§15）

- 事实全部来自 `fixmatch.py` / `ssl_dataset.py` / `average_log.py` 的逐行读取：
  metric=`eval/top-1-acc`、split=`test`、direction=max、tie=最早、timing=in-training、result=持久化 `model_best.pth`，
  六个准则字段全 DIRECT ⇒ 6 个 RD003 PASS；EMA 影子拷贝与 BN 重算写进成员规则表达式（`'1048000 iteration'`）。
- ± 措辞 vs 公式：**2 个 RD005 FAIL**（README 说 standard error，只有 ddof=0 std 族能复现发布值）。
- FM11：生成工作簿的 `Top5_20` 列被写入 top-1 滚动均值 ⇒ 该单元格 RD006 FAIL，而两个精度单元格 RD006 PASS。
- 每个 run 的评测候选集 = RECOVERED（378 次评测），而超参候选宇宙 = UNRECOVERABLE 并携带 4 个 `UnobservableSource`
  （含 `seeds=[0]` 这一条：它在这里是「候选宇宙不可恢复的证据」，不是被复制的上游 provenance 字段）。
- **零泄漏判定**：全套 31 份 finding 中不含 leakage / misconduct / invalid paper 任何一词，由防火墙扫描钉死。

---

## 8. 防火墙测试（§17，15 项）

1. 禁用词扫描：两份 bundle 的全部 569 份 finding 的 `reason` + `measurements` 中，
   p-hacking / cherry-pick / misconduct / fraud / leakage / 可信度评分 / 学术不当 / 论文错误 / suspicious 等 0 命中。
2. §8 状态语义 9 行逐条：只剩 1 个 candidate ≠ 宇宙只有 1 个；多 run ≠ cherry-picking；best ≠ leakage；
   缺产物 ≠ 作者删除；恢复不了 ≠ 当前列表完整；`UNRECOVERABLE` 必须带肯定性证据；「当前没找到」不升级。
3. 结构闸：`RuleFinding` 字段集合封闭；`schema` 中 `__module__` 属于本包的 dataclass 恰好是 Phase 0 的 8+11；
   `canonical_json` 的 **键名** 里不含任何 score 词（值里出现 "confidence intervals" 是论文原文，不算违规）；
   `CandidateSet` 默认 `universe_status=UNKNOWN`；源码无网络/tracker 导入。
4. 弃用网格案例：断言 RD004 既不断言「相同」也不断言「无关」（两侧理由字符串都被检查）。

---

## 9. 与 Phase 0 的偏差登记

| # | 偏差 | 证据 | 影响 |
|---|---|---|---|
| D1 | Phase 0 §6 标题写「12 条语义规则」实为 14 条 | 逐条清点 | 已在 Phase 0 原文就地更正，无语义影响 |
| D2 | 链 C 的 99 组三分 85/6/4 ⇒ 实测 98 组的 91/4/1/2 | 归档目录清点（1 组无存活搜索 csv 不构成事件） | 只改计数，不改判据 |
| D3 | §8「弃用 grid 与最终 grid 抽检参数值交集 = 0」不成立 | 修正 `_grid_census` 后重算：0 组不相交 / 14 组部分重叠 / 21 组共有键全等 / 7 组键集相同 | 防火墙断言改为「两个方向都不得断言」，语义反而更严格 |
| D4 | §5.2「BC 用 ddof=0 得 78.01±0.01」的 ± 截断有误 | `0.015126` 按 `%.2f` 打为 `0.02` | BC 的 ± 其实被三个公式族复现；断点只在中心值 |
| D5 | Table 5 题注显式声明 3σ·SE | `SPREAD_LABEL` 原文 | 链 A 的 RD005 应为 PASS（措辞与公式一致），Phase 0 未预判 |
| D6 | §15.2 把「TorchSSL 复算一致」列为 RD008 预期 | 该量只出现在一处产物 | 归位到 RD001 PASS + RD008 INCONCLUSIVE |
| D7 | 新增 `Locus.quantity_key`、`ComparisonSet.observed_marks` 两个 `EvidenceField` | FM13 需要「同一量」跨产物配对；FM12 需要「未恢复」≠「无」 | 8 对象不变，仅字段补齐，Phase 1 期间必需 |
| D8 | RD002 在真实归档上永不 PASS | FM3/FM4 是归档的既成事实 | 不是缺陷：这正是规则设计要产出的状态 |
| D9 | RD004 在 GMMVI 永不 PASS | FM9 分支先于 RECOVERED | `RECOVERED`+PASS 路径由 S1 与 TorchSSL 覆盖，未被删除 |
| D10 | RD004 的 NOT_APPLICABLE 分支未实现 | 两份真实归档都不产生「无搜索的单配置实验」对象 | 不写无证据承载的分支；fixtures 覆盖 PASS/INCONCLUSIVE |
| D11 | 未创建 `docs/` | §20 目录清单 | 文档职责由本报告承担 |
| D12 | 收口时补跑 `ruff format`：8 个文件被重排（16 文件现已全绿），只对论文誊抄表保留一对 `# fmt: off/on` | 誊抄表必须与论文逐格对照；其余文件的摊开无信息损失 | 纯版式，零语义改动 |

所有偏差都属于「Phase 0 描述性事实的更正」或「字段级补齐」；**没有任何一条改动 RD001–RD008 的判据语义来让测试通过**。
Phase 0 原报告未被本轮改写（D1 的「12→14」是本轮之前就已在原文就地更正的那一处例外）。

### 9.1 本轮两处 Phase 0 修正（详细）

**修正一 —— Phase 0 §8 关于两代 grid 的参数值关系（对应 D3）**

- **原 Phase 0 表述**：弃用 grid 与最终 grid「35/35 共用 `wandb.group`，但抽检参数值交集 = 0」。
- **现场证据**：修正 `_grid_census`（同名多文档必须按组累加，否则 35 个文件 / 61 个文档会漏掉 510 个网格点）后重算两代网格：
  adopted 1074 点、discarded 1152 点，键名复用 35 次；逐组抽检得到
  **7 组键集完全相同、0 组取值不相交、14 组部分重叠、21 组在共有键上取值全等**。即「交集 = 0」不成立。
- **最终修正**：Phase 0 的该项事实描述更正为「同名跨代复用，取值关系从完全一致到部分重叠不等」；
  防火墙测试 `test_grid_generations_are_censused_and_neither_merged_nor_separated` 改为断言
  RD004 的理由字符串里既不出现「相同」结论也不出现「无关/confus」结论，并抽检上述四组统计。
- **是否改变 schema**：否（`IdentityCollision` 与 `CandidateSet` 字段不变）。
- **是否改变 rule semantics**：否。RD004 的判据「仅当同单位的两处声明互相矛盾才 FAIL」保持原样；
  INCONCLUSIVE 的承载对象（`IdentityCollision`）与理由模板不变，只有理由文本按实测统计重写。
- **是否改变 acceptance oracle**：变了该测试内的**统计数值**（0 组不相交 / 14 组部分重叠 / 21 组全等 / 7 组键集相同），
  未变状态向量：两个 grid 的 RD004 仍为 INCONCLUSIVE。
- **定性**：`non-Phase-0-semantic correction` → 精确归类为 **non-semantic Phase 0 correction**（evidence-detail 更正）。

**修正二 —— Phase 0 §5.2 关于 BC 行 ddof=0 重算结果（对应 D4）**

- **原 Phase 0 表述**：BC 行若按 ddof=0 重算会得到 `78.01 ± 0.01`，与论文的 `78.00 ± 0.02` 两值皆不符。
- **现场证据**：`fetch_exp3.py:64-71` 对中心与 ± **各自独立** `%.2f`；成员末行实算 `std(ddof=0)=0.015126`，
  `f"{0.015126:.2f}" == "0.02"`，而不是 `0.01`（原表述按截断而非取整）。RD005 的六族渲染表实测：
  `std_ddof0 / std_ddof1 / k_sem_ddof1_k3` 三种都打印 `0.02`，只有 `k_sem_ddof0_k3` 打印 `0.01`。
- **最终修正**：Phase 0 §5.2 的该句更正为「发布 ± 被三个公式族复现，断点仅在中心值 78.01 vs 78.00」；
  `test_chain_b_spread_family_is_the_only_bc_claim_that_survives` 把这一点钉为断言。
- **是否改变 schema**：否。
- **是否改变 rule semantics**：否。RD001 仍是「按声明精度比较渲染后的字符串」，RD005 仍是「六族各自渲染后比对」，
  且两者都仍要求先施加 `Transformation` 再比较（正是这条纪律暴露了 Phase 0 的截断笔误）。
- **是否改变 acceptance oracle**：变了该测试内的**期望字符串**（BC 的 `families_matching_published_spread`
  为 `["k_sem_ddof1_k3","std_ddof0","std_ddof1"]`），未变状态向量：BC 的 RD001 仍 INCONCLUSIVE、RD005 仍 PASS、RD008 仍 FAIL。
- **定性**：**non-semantic Phase 0 correction**（file:line / evidence-detail 层，不动核心设计）。

---

## 10. 验证命令与结果

```
cd F:\MLResearch\result-doctor
python -X utf8 -m pytest tests -q                # 76 passed
python -X utf8 -m ruff check src tests           # All checks passed!
python -X utf8 -m ruff format --check src tests  # 16 files already formatted
python -X utf8 -m mypy                           # no issues found in 10 source files
```

四条门禁全部使用 `pyproject.toml` 里已配置的命令与规则集（`select = ["E","F","I","UP"]`、`line-length = 120`、
`ignore = ["UP042"]`、`mypy` 的 `files = ["src/result_doctor"]`）；收口阶段未新增任何 lint/type 配置项，
唯一一次配置调整是把 `line-length` 从 110 调到 120 并显式豁免 `UP042`（`(str, Enum)` 是刻意的，
`canonical_json` 通过 `.value` 显式序列化）。

| 测试文件 | 数量 | 覆盖 |
|---|---|---|
| `test_compute.py` | 7 | 离散度族、渲染模式、阶段变换、`sum_of_part` 一元恒等、FM11 冲突判据 |
| `test_synthetic_oracle.py` | 18 | S1–S5 精确状态向量 + 覆盖率 + 证据齐备 + 反向不变式 |
| `test_gmmvi_acceptance.py` | 23 | 链 A/B/C、网格代际、FM12/13/14、确定性 |
| `test_torchssl_acceptance.py` | 13 | best-checkpoint 选择、± 措辞、FM11、UNRECOVERABLE、无泄漏用语 |
| `test_firewall.py` | 15 | §17 全部条目 + 结构闸 |

确定性由「同一 bundle 两次评估的 `canonical_json` 字节相等」+「重载归档后仍相等」双测保证（`findings total 538`，序列化 >10 KB 稳定）。

---

## 11. 已知限制（不阻断 Phase 1）

- Table 8 的 9 个 BreastCancer 单元格里只冻结了 3 个（`samtron / sepyfux / sepyrux`）；
  其余 `samtrux / samtrox / samyron / samyrox / samyrux / zamtrux` 6 格仍需人工转录论文，Phase 1 不解析 PDF。
- BC 行真实生产者停留在 UNKNOWN：`:191-195`（secondary=MMD）只是 Phase 0 记下的 INFERRED 候选，**未升级**，
  因此 `Grade.INFERRED` 在两份 bundle 中实际为空（唯一的 INFERRED 构造函数因无证据承载而被删除）。
- `ComparisonSet.recomputed_marks` 在 GMMVI 上没有一条能被复算，因为比较集合成员值本身被覆盖（FM2 上游缺口）。
- 两个 loader 是冻结归档的证据映射器，不是发现器：换任何目录结构都要重写它们，这是 §13 的有意约束。

---

## 12. §24 关闭判据逐条核对

| # | 判据 | 结论 | 证据 |
|---|---|---|---|
| 1 | 8 对象最小 schema | ✔ | §3 表 + 结构闸测试 |
| 2 | RD001–RD008 全部实现且被执行 | ✔ | 569 份 finding，8 规则各有真实承载 |
| 3 | S1–S5 通过 | ✔ | 59 份 finding 精确匹配预写向量 |
| 4 | GMMVI oracle 匹配 | ✔ | `−25.03 ±5.46` 逐位；反例 `6.31` / `−45.32 ±42.91` 被拒 |
| 5 | TorchSSL oracle 匹配 | ✔ | 6 RD003 PASS + 2 RD005 FAIL + FM11 单点 FAIL |
| 6 | 防火墙通过 | ✔ | 15 项，含双向「不断言」 |
| 7 | UNKNOWN 纪律保持 | ✔ | RD002 46 INCONCLUSIVE、RD004 100 INCONCLUSIVE、`observed_marks` UNKNOWN |
| 8 | 不产生 overall 判定/评分 | ✔ | 无跨规则聚合代码路径 + 键名闸 |
| 9 | 不复制 ED 语义 | ✔ | schema 无 seed/git/env/resolved-config/termination 字段 |
| 10 | 无多余架构 | ✔ | 无 DAG/plugin/ORM/metaclass/DI，19 个 dataclass + 纯函数 |
| 11 | 本地全套通过 | ✔ | 76 passed / ruff check / ruff format --check / mypy 四项全绿 |

---

## 13. 明确未做（§23 禁止项，逐项确认未越界）

第三个真实项目 · 任何新调研 · 数据下载 · GMMVI/TorchSSL 重训 · 完整论文复现 · PDF parser · W&B/MLflow/Hydra ·
数据库 / dashboard / server / REST / GUI · agent 框架 / LLM judge · 自动论文批评 · misconduct 检测 · 总分 ·
Paper Doctor · Result Doctor v2 路线图 · Experiment Doctor 修改 · Dataset Doctor 修改 · PyPI 发布。

---

## 14. 唯一下一步

在 `phase0/RESULT_DOCTOR_PHASE0_REPORT.md` 权威不变的前提下，**人工转录 Table 8 剩余 6 个 BreastCancer 单元格**
（写入 `notes/paper_exp3_table_transcription.md`，再由 `loaders/gmmvi.py` 的 `ELBO_CELLS["BreastCancer"]` 读取），
使链 B 的复算与产物定位断言从 3/9 扩到 9/9。除此之外不启动任何新机制、新范围。
