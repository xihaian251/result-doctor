# Result Doctor Phase 4 — Real-World Onboarding Pilot

输入：Phase 3 已冻结的 generic contract（`src/result_doctor/manifest.py`，1244 行，26 个错误码，148 passed 门禁）。
本轮目标只有一个：在一个从未适配过、没有专用 adapter、没有现成 fixture 的真实公开项目上，只靠一份人工写的
`result-doctor.yml` 完成第一次 onboarding，并量出**普通用户实际能提供什么、哪里只能留 UNKNOWN**。

---

## 1. Executive result

- 项目：`yandex-research/rtdl-revisiting-models`（NeurIPS 2021，表格数据深度学习模型对比），commit `e3ed46c`。
  Result Doctor 此前对它没有任何 adapter、fixture 或取证记录。
- **零代码改动、零 schema 改动、零规则改动**下：generic loader 成功解析（修 4 个作者自己的验证错误后），
  RD001–RD008 全部产出，16 条 finding：`PASS ×6`、`INCONCLUSIVE ×6`、`NOT_APPLICABLE ×3`、`NOT_RUN ×1`。
- 复算证据是真的：两个 cell 的 15 个 per-seed 值从 30 个 `stats.json` 用 JSON pointer 确定性读出，
  `mean` + `format(3)` 链算出的字符串与仓库 README 里打印的 `0.852` / `-0.499` **逐字相等** ⇒ RD001/RD006 真 PASS。
- UNKNOWN 没有被偷换：candidate universe 只敢写 `partial`（100 trial 的宣称）和 `unknown`（epoch 集），
  两条 RD004 都 INCONCLUSIVE 且 reason 明确拒绝从存活 artifact 数量反推；没有比较集 ⇒ RD007 `NOT_RUN`。
- manifest = **110 逻辑行**，超预算 10 行；超出的来源可指认：**30 行成员枚举**（无目录展开是契约自己的防火墙），
  加上第二个 cell 的 25 行；身份重复造成的是横向啰嗦（`path:` 出现 73 次里 60 次是同一批文件名的第二遍），不是行数。
- `Phase 4 verdict: CLOSED`。唯一下一步见 §19。

---

## 2. Selected project

筛选过程（只看元数据与文件树，不做深入分析）：

| 候选 | 结论 |
|---|---|
| `tkipf/gcn` | 存在（7405★），但结果只以 stdout 文本形式存在；契约的数值闸门会把 `test_acc= 0.81` 这种行拒掉 ⇒ 六层一层都走不动，不适合当首个试点 |
| `hatem-ibrahim/EffNet`、`otic-project/ot_benchmark`、`kojima0530/ml4cs`、`google-research/mambular` | GitHub API 返回空（仓库名不存在或已改名），未深入 |
| **`yandex-research/rtdl-revisiting-models`** | 365★，论文公开、repo 公开，且 **repo 内直接提交了 per-run 数值 artifact** ⇒ 选中 |

选定后确认的 §2 条件：

- 公开论文 + 公开 repo + 明确的报告结果：README「How to explore metrics」小节的输出块**就是**论文 Table 2 的数字列。
- 可读 artifact：`output/<dataset>/mlp/tuned/<seed>/stats.json`（45 个本次用到的，每个 ~4.6 KB，纯 JSON）。
- 含聚合/选择/变换的部分：README 给出聚合口径与 `.round(3)`；`bin/tune.py`、`bin/mlp.py` 给出两层选择；
  `output/*/mlp/tuning/*/best.toml` 是被选中配置的产物。
- 无需重新训练、无需下载数据集：只读已提交的 JSON/TOML/源码。
- 结构与两个冻结 adapter 明显不同：GMMVI 是「CSV 列 + 行」、TorchSSL 是「文本日志 + 逐 epoch 行」，
  这里是 **一个 run 一个 JSON，值靠 JSON pointer 寻址**，且成员分布是 `dataset × model × seed` 三维目录。
- 与用户 Row-Amplitude 项目无关。

## 3. Why this project（为什么它是最优选）

它同时提供**打印值**和**打印值的来源**，而且两者都在同一个 commit 里：
README 既打印 `0.852`，又写出产生它的两行 pandas 代码，还声明它等于论文 Table 2。
于是第一次 onboarding 就能测到契约里最关键的一组区分：

- 「聚合口径可以被行 locator 引用到」⇒ 聚合层能 OBSERVED，而不是全靠作者声明；
- 「打印值是文本行里的一个片段」⇒ 文本 locator 与数值闸门会在真实项目上正面相撞（§11、§12 的证据）；
- 「候选集只剩最优点」⇒ 100 trial 只剩 `best.toml`，正好检验 §15 的「不要从存活数量反推 universe」。

## 4. Audited result slice

只审 1 张表里的 2 个代表 cell（§6 允许 1–3 个）：

| cell | 打印值 | 打印位置 | 成员 |
|---|---|---|---|
| `mlp-tuned/adult` | `0.852` | `README.md:80` | 15 个 seed 的 test score |
| `mlp-tuned/california_housing` | `-0.499` | `README.md:82` | 同上 |

选这两个是因为一个正一个负，`format(fixed, digits=3)` 的渲染在两侧都要正确；其余 9 个数据集不写。
本次审计**不涉及**论文里其它 30 张表、其它 11 个模型、以及 ensemble/合成数据分析。

## 5. Ground-truth evidence map

写在 manifest 之前，落盘于 `phase4/rtdl-revisiting-models/EVIDENCE_NOTES.md`。压缩版（O=OBSERVABLE，D=DECLARABLE，U=UNKNOWN）：

| 事实 | 标记 | 依据 |
|---|---|---|
| 成员值 `metrics.test.score` | O | JSON pointer `/metrics/test/score` |
| 成员身份（seed） | O | 同文件 `/config/seed`（整数） |
| 被存下的 test 指标属于 `best_epoch` | O（存在性）+ D（含义） | `/best_epoch` 可读；「只有 new-best 才覆盖」要靠读 `bin/mlp.py:250-254` 的一句话 |
| 聚合中心 = mean | O | `README.md:73` 的 `.mean()` |
| 聚合口径散文 | O | `README.md:70`，作为 `wording` 的 `observed:` |
| 渲染 = 保留 3 位 | O | `README.md:73` 含 `.round(3)` ⇒ 契约的 `format` 步 |
| 打印的数字本身 | D | 该行是「标签 + 空格 + 数字」，`line:` 读回整行 ⇒ 过不了数值语义；只能 declared + 行 locator 作 `supported_by` |
| 成员集合是「所有 random seed」的哪 15 个 | D | 契约无目录扫描；作者逐个列举 ⇒ `member_rule: enumerated` |
| 离散度 | U | README 打印列里没有任何 ±/std/CI |
| 超参搜索 trial 总数 = 100 | D（数字）+ O（宣称的位置） | `output/adult/mlp/tuning/0.toml:20` |
| 逐 trial 结果能否恢复 | U | 代码会写 `trial_stats.json`，仓库里一个都没有 ⇒ universe 只能 `partial` |
| epoch 候选全集 | U | `n_epochs = 1000000000` + `patience = 16`，实际跑过的 epoch 分数不在 artifact 内 |
| epoch 选择的 direction | U | 比较行为在第三方 `zero.ProgressTracker` 内，本仓库 artifact 无比较符号 ⇒ **不从 metric 名 `score` 猜方向** |
| 超参选择的 direction | O | `bin/tune.py:178` 该行含 `maximize`，引用片段即得 DIRECT |
| 与论文 Table 2 的关系 | D | `README.md:76` 是散文，PDF 不在 root 内 |
| 同表 peer（其它模型）的值 | U | 本次切片没有其它列 ⇒ 不建 comparison set |

## 6. Manifest

文件：`phase4/rtdl-revisiting-models/result-doctor.yml`（与项目检出同目录，`root: .`）。

结构（8 个 section 里只用了 6 个）：

```
schema_version / project / root
evidence:            1 条（best-epoch，被 30 个成员的 selector 用 via: 复用）
transformations:     1 条链（format@render/fixed/3/script，observed 于 README.md:73）
candidate_sets:      2 条（hyperparameter=partial+declared_size 100；checkpoint=unknown）
selection_events:    2 条（超参搜索；run 内 epoch 选择）
reported_results:    2 个 cell × 15 个成员（成员用单行 flow 写法）
comparisons:         不写（缺对象就让它缺）
```

写法刻意保持「第三方用户」姿态：最少声明、能引用就引用、不知道就 `unknown:` 或不写；
没有为了好看而补的字段，也没有把 15 个 seed 目录扫一遍再粘进来（路径由作者逐个写，loader 无发现能力）。

## 7. Authoring metrics（§17 的可确定计数）

| 指标 | 值 |
|---|---|
| 文件总行数 | 118 |
| 纯注释行 / 空行 | 1 / 7 |
| **逻辑行数** | **110**（预算 100，超 10） |
| 审计的 reported cell | 2 |
| 聚合成员 | 30 |
| `path:` 出现次数 | 73（其中成员 30、成员身份 30、其它 13） |
| 引用的不同文件 | 34（30 个 stats.json + README.md + bin/mlp.py + bin/tune.py + tuning/0.toml + best.toml） |
| **DIRECT 事实（EvidenceField）** | **69** |
| **DECLARED 事实（EvidenceField）** | **7** |
| **UNKNOWN 事实（EvidenceField）** | **17** |
| 非 EvidenceField 的 grade 承载 | 37（selector DECLARED ×30、member_rule DECLARED ×2、SpreadForm UNKNOWN ×4、Transformation DIRECT ×1） |
| 首轮验证错误 | 4 个硬错误（`E_BAD_FIELD ×2`、`E_LOCATOR_TEXT ×1`、`E_UNKNOWN_KEY ×1`）+ 2 个语义陷阱（见 §11） |
| 首轮成功加载？ | 否（第一次 `bundle_from_manifest` 即报错）；第 5 次尝试通过 |

逻辑行分布（按顶层 section 实测）：`reported_results` 52（其中成员枚举 30 = 全文 27%，cell 元信息 22）、
`selection_events` 23、`candidate_sets` 15、`transformations` 10、`evidence` 7、header 3。

**每多审一个 cell 的边际成本是刚性的：+25 逻辑行**（15 行成员枚举 + 10 行元信息），
因为契约没有任何目录展开/通配，成员必须逐个写（实测：删掉第二个 cell 剩 85 行，110 − 85 = 25）。
反过来：一份 ≤100 行的预算实际只买得起 **1 个 cell 加完整的 selection/candidate 声明**（85 行）。
README 那一列 11 个数据集若要全审，约需 `85 + 10 × 25 = 335` 逻辑行。

## 8. Generic loader result

- 最终：加载成功，产出 8 对象 Bundle，与两个冻结 adapter 走同一套 `evaluate()`；
  Bundle 对象数：members 30、aggregations 2、candidate_sets 2、selection_events 2、reported_results 2、
  transformations 1、comparison_sets 0、artifacts 0（`artifacts:` 一段都没写，也照样能跑）。
- 首轮 4 个错误的原文（格式仍是 `{code} at {where}: {problem}`）：

```
E_BAD_FIELD at candidate_sets[0]/declared_size: size declares nothing: declared: needs a value or a statement
E_BAD_FIELD at candidate_sets[0]/surviving_size: size must be exactly one of observed:/declared:/unknown:, got ['note']
E_LOCATOR_TEXT at selection_events[0]/criterion/metric/observed: line 131 of bin/tune.py is "        return stats['metrics'][lib.VAL]['score']", which does not contain "metrics[lib.VAL]['score']"
E_UNKNOWN_KEY at reported_results[0]/aggregate: unknown key(s) ['member_rule', 'members']
```

可修复性评价：第 3 条最好——它把真实行内容打出来，用户一眼看出自己的片段多写了一个字符；
第 4 条最差——它只说「这里不认识这两个键」，不告诉用户 `members` 应该写在 cell 层级（正确写法就在同一份契约的示例里）。
前两条属于同一类：`{value, statement}` 外层尺寸写法与 `declared:` 内层写法**互相不知道对方的存在**，
用户被迫把同一个数字写两遍（见 §12-C）。

## 9. RD001–RD008 output

| 规则 | 状态 | target | 判据要点 |
|---|---|---|---|
| RD001 | PASS ×2 | 两个 cell | 15 个 OBSERVED 成员值 → mean → `format(fixed,3)` → 字符串与打印值逐字相等 |
| RD002 | PASS ×2 | 两个 aggregation | 30 个成员全部可绑定，0 排除，member_rule = enumerated/DECLARED |
| RD003 | INCONCLUSIVE ×2 | 两个 selection event | 准则 6 字段：DIRECT ×3（metric/direction/timing）、DECLARED ×2（split/scope）、UNKNOWN ×1（tie_break）；`n_candidates = 0` ⇒ 无法核对被选中者 |
| RD003 | NOT_APPLICABLE ×1 | `reported:mlp-tuned/california_housing` | 该 cell 未绑任何 selection ⇒ 规则自己宣布不适用，而不是硬判 |
| RD004 | INCONCLUSIVE ×2 | 两个 candidate set | universe 分别是 UNKNOWN 与 PARTIAL；reason 固定写「绝不从存活 artifact 数量反推」 |
| RD005 | NOT_APPLICABLE ×2 | 两个 cell | 打印 cell 没有离散度 ⇒ 无可判对象 |
| RD006 | PASS ×2 | 两个 cell | 链 `format@script` 逐步应用得到打印串 |
| RD007 | NOT_RUN ×1 | `rule:RD007` | `comparison_sets` 为空 ⇒ 对象类缺席，evidence 为空，不复述任何结论 |
| RD008 | INCONCLUSIVE ×2 | 两个 quantity | 每个 quantity 只出现在 1 个产品 ⇒ 无可交叉核对对象 |

`n_members`、`member_values`、`recomputed_center`、`criterion_grades`、`universe_status` 等测量字段都填了真值，
`declared_size = 100`、`surviving_size = 1`、`sizes_stated_in_same_unit = True` 都在 RD004 的测量里可见。

## 10. UNKNOWN / partial evidence 的实际行为

这是本轮最重要的一条结论：**契约没有把用户逼成造假者。**

- direction：epoch 选择的方向在第三方库里 ⇒ 写 `unknown: "the comparison lives inside the third-party zero.ProgressTracker, not in this repository"`
  照样加载成功，RD003 给出 INCONCLUSIVE；没有「必须六个字段齐全」的强迫。
- universe：只敢写 `partial`（且有 100 的声明尺寸 + 行 locator 支撑）与 `unknown`；
  RD004 因此**永远不会 PASS**，正是 §15 要求的行为。若作者改口写 `complete`，
  loader 会因为 `universe_evidence` 不存在而自动降级成 `DECLARED_ONLY`（Phase 3 的规则），
  所以谎报也没有收益。
- 离散度：不写 ⇒ RD005 `NOT_APPLICABLE`，而不是把缺失当成 FAIL。
- 比较集：不写 ⇒ RD007 `NOT_RUN`，且只多这一条 NOT_RUN（其余八条规则都正常出 finding），
  证明「缺对象」与「缺科学结论」在入口层是可区分的。
- 一个未预期的好行为：**未被 cell 绑定的 selection event 也会被 RD003 审计**（`sel:per-run-epoch` 出了 INCONCLUSIVE）。
  我原本担心写了没人看，实测不是。

## 11. First-pass validation experience

三轮才跑通，其中两类体验截然不同：

**(a) 硬错误（好修）**：4 个，每个都是一行 YAML 的事，见 §8。全部是我自己的写法问题，
没有一个是 loader 拒绝了合法契约。第 4 个之后我改成把成员放在 cell 层级，一次通过。

**(b) 静默的语义陷阱（危险）**：加载成功但结论错，两处：

1. **`value: {observed: {path: README.md, line: 80}}` 读回整行**。
   该行是「数据集名 + 空格 + 数字」，于是打印值变成 `"adult                 0.852"`，
   RD001 **FAIL**、RD006 **INCONCLUSIVE**，reason 是「成员、聚合、变换都已确定，但 cell 不同」。
   这是一次假指控：错的是我的 locator 粗，不是论文的数字。
   修法是自己把片段写进去（`text: "0.852"`），改完立刻 PASS。
   关键点：**契约对成员值有数值闸门，对打印值没有**（打印值本来就是字符串），
   所以「读到一整行」不会报错、只会误判。真实表格行几乎都带行标签，这个坑是**默认会踩**的。
2. **`quantity: metrics.test.score` 写成列名**。RD008 把两个数据集的 cell 归为同一个 quantity，
   于是报 FAIL「同一量在两个产品里印成不同值」。实际上 0.852 与 -0.499 是两个不同数据集的同一列，
   本就该不同。正确写法是行级作用域的 key（示例 fixture 用的就是 `acc/cifar-resnet20` 这种
   `<列>/<实体>` 形式）。`quantity` 这个字段名没有告诉用户它必须携带行身份。

⇒ 结论：真正的 onboarding 风险不在 loader 报错，而在**报错之外的两处静默误判**；本轮只登记，不改规则。

## 12. Onboarding friction

**A. 最难的字段（按痛感排序）**

1. 聚合成员：15 行×2 cell 的机械枚举，且每行还要重复路径才能写身份。
2. candidate universe：真实项目基本只能 `partial`/`unknown`，用户需要理解
   「100 写在 `declared_size` 里 + 行 locator 作 `supported_by`」不等于宣称可恢复。
3. selection criterion：六个字段各自走门，`direction` 要求字面 min/max 开头（这条设计本轮帮了大忙：
   `bin/tune.py:178` 只要引用片段 `maximize` 就得到 DIRECT）。
4. comparison dependency：想写「这张表等于论文 Table 2」但 PDF 不在 root 内 ⇒ 只能整段放弃（本轮选择不建比较集）。
5. transformation：`round(3)` 要写成 `format(fixed, digits 3, stage render, applied_at script)`，
   用户必须先知道「`round` 是被禁止的步、`format` 才是渲染步」，契约里没有这条提示。

**B. 最难的契约概念**

1. `aggregate` vs `reported_result`：本轮第 4 个错误就是它（members 必须在 cell 层，不在 `aggregate:` 里）。
2. `declared` vs `observed`：直觉上「README 里印着」= 观察到，实际因为数值/文本之别只能 declared；
   反过来「代码里印着 `maximize`」直觉上是解释，实际可以 observed（引用片段）。这两个方向的反直觉同时出现。
3. 冗长 locator：一个事实要写 `{path, line, text}` 三件套，30 个成员里每个 identity 都是四元嵌套。
4. 尺寸写法的双形状：`{value, statement}`（外层）与 `declared: {value, statement}`（门内）语义重叠但互不可见。

**C. 同一事实被重复写了几次（实测）**

| 重复 | 次数 |
|---|---|
| 成员文件路径写两遍（locator + identity） | **30 对 = 60 次出现**，占全部 73 次 `path:` 的 82% |
| 同一尺寸数字写两遍（`declared_size.value` 与 `declared.value`；`surviving_size` 同理） | 2 |
| `printed_in.quoted_text` 与 `value` 引用同一行的同一个串 | 2 |
| 聚合口径 `wording` 引用同一行（`README.md:70`） | 2 cell 各一次（这是有意的重复声明，可接受） |

⇒ 这条重复**不增加行数**（成员已压成一行），但增加 30 次同样的路径字符串：平均每个成员行 233 个字符，
其中约一半是第二次写同一个文件名。若契约允许「identity 默认取成员自身文件」，`path:` 出现数从 73 降到 43、行长减半。
所以身份这一项是**横向啰嗦**；纵向成本是成员枚举本身（§7：每 cell 15 行成员）。

**D. UNKNOWN 是否自然**

自然。`unknown: "<一句话理由>"` 与「干脆不写」两种写法都通过加载，且都不产生 FAIL/PASS；
`evidence:` 注册表 + `via:` 让 30 个 selector 共用一条声明（本轮真用了），
所以「留未知」的成本低于「编一个值」。唯一别扭处是 `_size`：想给尺寸加一句 `note` 反而报 `E_BAD_FIELD`（§8 错误 2）。

## 13. What required declaration（7 个 DECLARED EvidenceField + 32 个 DECLARED 承载）

打印值本身最终**不是**声明（`value: {observed: {path: README.md, line: 80, text: "0.852"}}` ⇒ DIRECT，见 §14）；
它只在中间态被写成 `declared:`。下表是最终 manifest 里真正靠作者说话才存在的 7 个事实：

| 被声明的事实 | 为什么不能 OBSERVED |
|---|---|
| `member_rule: enumerated` ×2 | 「这 15 个就是全部成员」是作者的话，仓库里没有一张 seed 清单 |
| `declared_size: 100 optimization trials` | 数字在 TOML 的一行里，行不是数（G6） |
| `surviving_size: 1` | 同上，且「仓库只剩 best.toml」是我对目录的解读而非一次确定性读取 |
| selection `split: validation` ×2 | 代码只给出被传进 `progress.update` / `return` 的对象名，「它就是验证集」要靠读上下文 |
| selection `scope` ×2 | 「一次搜索服务一个数据集×模型」「每个 run 内一次」是我对脚本组织的描述 |
| `sel:adult-tuned-config` 的 declared policy | loader 从 direction+chosen 自动合成（用户一个字节都没写），登记为 DECLARED |

另有 32 个 DECLARED 承载在非 EvidenceField 对象上：30 个成员的 `selector.kind = best`（经 `evidence: best-epoch` + `via:`
复用一条声明）与 2 个 `member_rule.grade`。

注意：这 7 个 DECLARED 里没有一个是「数字对不上」型的声明；它们全是**结构/口径型**断言，
这正是契约设计的意图（声明解锁判定，不保证一致）。

## 14. What was directly observable（69 个 DIRECT EvidenceField + 1 个 DIRECT 承载）

| 事实 | locator | 计数 |
|---|---|---|
| 每个成员的值 | JSON pointer `/metrics/test/score` | 30 |
| 每个成员的身份（seed） | JSON pointer `/config/seed` | 30 |
| 打印值 `0.852` / `-0.499` | `{path: README.md, line: 80/82, text: "<数字>"}` | 2 |
| 聚合口径散文 | `{path: README.md, line: 70, text: "averaged over all random seeds"}` | 2 |
| 搜索目标函数 | `{path: bin/tune.py, line: 131, text: "stats['metrics'][lib.VAL]['score']"}` | 1 |
| 搜索方向 = maximize | `{path: bin/tune.py, line: 178, text: "maximize"}` | 1 |
| 选中时刻 | `{path: bin/tune.py, line: 192, text: "study.best_trial"}` | 1 |
| epoch 准则的 metric 与 timing | `{path: bin/mlp.py, line: 250, text: "progress.update"}` | 2 |
| 渲染变换 `format(3)` | `{path: README.md, line: 73, text: ".round(3)"}` | 1（`Transformation.grade` 承载，不是 EvidenceField） |
| 被选中的 epoch 号 | JSON pointer `/best_epoch`（`sel:per-run-epoch` 的 `chosen:`） | 1（读出后只作为 ref 字符串落进 `promoted_ref`，**不占 grade**） |

⇒ 69 = 30 + 30 + 2 + 2 + 1 + 1 + 1 + 2。JSON pointer 是真实项目里最好用的一扇门：一个 run 一个 JSON 的仓库，
成员值和成员身份都能零歧义读出，不需要任何专用解析。四类 locator 里本轮用到两类（JSON key、line+text），
CSV column/row 与整文件 text 没用上（这个仓库没有 CSV）。

## 15. What remained unknowable

| 未知 | 条数/表现 |
|---|---|
| 离散度（std/sem/CI） | 2 个 cell 的 `spread` = UNKNOWN ⇒ RD005 NOT_APPLICABLE |
| epoch 候选全集、以及实际跑过的 epoch 数 | `cand:adult-epochs` universe UNKNOWN ⇒ RD004 INCONCLUSIVE |
| 100 个 trial 的逐 trial 结果 | 只有 `best.toml` 存活；universe 不敢写 complete |
| epoch 选择方向（maximize 还是 minimize） | 在第三方 `zero` 库内 ⇒ criterion.direction UNKNOWN |
| tie-break 规则 | 两处均无记录 ⇒ UNKNOWN ×2 |
| 是否存在被排除的 seed | 无任何 exclusion 记录 ⇒ 不写 `exclusions:` |
| `score` 对回归任务的确切定义 | 本轮只声明「它是仓库记录的 test 统计量」，不猜 R² |
| 与论文 Table 2 的一致性 | PDF 不在 root 内 ⇒ 无 comparison set ⇒ RD007 NOT_RUN、RD008 无交叉核对 |
| candidate 的 promotion / identity collision | `promotion_evidence` UNKNOWN ×2 |

对账（17 个 UNKNOWN EvidenceField，全部实测）：`spread` ×2、`metric_name` ×2、`direction_semantics` ×2
（我没声明 score 叫什么、越大越好还是越小越好）、`criterion.tie_break` ×2、`criterion.direction` ×1（epoch 事件）、
`selection_events[].is_recorded` ×2（没人记录「这次选择被登记过」）、`declared_policy` ×1（epoch 事件无 direction ⇒ 连自动合成都不发生）、
`candidate_sets[].promotion_evidence` ×2、epoch 集的 `declared_size` ×1 与 `surviving_size` ×1、
`transformations[].condition` ×1。另有 4 个 `SpreadForm.grade = UNKNOWN` 承载。
表里没列的两条也是 UNKNOWN：`score` 对回归任务的确切定义（落在 `metric_name`）、以及「是否存在被排除的 seed」
（`exclusions:` 干脆不写 ⇒ RD002 的 `n_exclusions = 0` 是「未声明」而非「确认没有」）。

## 16. Generic contract gaps（只登记，不动契约）

| # | 缺口 | 证据 | 若不登记会被怎样误用 |
|---|---|---|---|
| G1 | 打印值没有「行内数值」读法：`{path, line}` 返回整行，表格行必带行标签 | §11(b)-1，RD001 假 FAIL | 用户以为论文数字错了 |
| G2 | `quantity` 不提示必须携带行身份 | §11(b)-2，RD008 假 FAIL | 用户以为工具说作者自相矛盾 |
| G3 | 成员 identity 无法默认取成员自身文件 ⇒ 路径重复 60 次 | §12-C | 用户放弃写身份，RD002/RD001 变弱 |
| G4 | `_size` 的双形状互不可见（外层 `{value, statement}` vs 门内），带 `note` 直接报错 | §8 错误 1、2 | 用户放弃给尺寸加单位说明 |
| G5 | `E_UNKNOWN_KEY at .../aggregate` 不说 members 的正确层级 | §8 | 用户去猜 section 结构 |
| G6 | TOML/自定义配置只能整行引用，数值宣称（`n_trials = 100`）只能 DECLARED | §13 | 用户改成把 100 塞进成员清单以「凑出」RECOVERED |
| G7 | selection 只能绑在 cell 上；真实项目里 epoch 选择是 per-member，本轮只能写成一个不绑 cell 的事件 | §9 RD003 三行 | 用户把 per-member 选择硬绑到 cell，产生语义错位 |
| G8 | 禁止的 `round` 与可用的 `format` 之间没有指引（错误信息里有，但要先撞上） | §12-A-5 | 用户写 `round` 后误以为工具不做舍入检查 |
| G9 | 论文/PDF 侧的打印物完全不可达，「打印值」只能来自仓库内文本 | §15 末行 | 用户把 README 当论文原文，或干脆不审 |

其中 G1、G2、G4 属于**会在真实项目上稳定复现的静默误判**，优先级高于其余「写法别扭」类。

## 17. Bugs discovered

本轮**未修改任何代码**（`src/`、`tests/`、两个冻结 adapter、Experiment Doctor 全部只读）。
可确认的确定性缺陷登记如下，留给下一轮判定是否算 bug：

- **B1（`_size` + `door_of`）**：`{value, statement, note}` 这类合法尺寸写法被 `E_BAD_FIELD` 拒绝，
  因为 companion 键（`note`）单独构成「非空 door 集合」→ `field()` 看到 0 扇门。
  复现：`python -c "bundle_from_manifest(...)"` 于修改前的 `surviving_size` 行；错误文本见 §8 错误 2。
  判定：本轮**不算阻塞**（换写法即可），因此按 §13 不改代码。
- **B2（非 bug，但反直觉）**：`{path, line}` 与 `{path, line, text}` 的返回不同
  （前者整行 strip，后者返回片段）。这是 fragment 校验的既有设计，但它正是 §11(b)-1 假 FAIL 的来源；
  契约本身没写「读表格行请带 text」。
- **B3（未复现的怀疑）**：`identity:` 走通用 `field()`，因此可以引用**另一个文件**的数值。本轮没有构造这个用例，
  只记录「跨文件身份」在语法上无阻拦，值得下一轮用防火墙测试钉住。
- 除此之外，26 个错误码没有一次误报：所有硬错误都对应我自己的写法问题，没有一次合法契约被拒。
- 零改动的证据：本轮结束时重跑既有门禁，`python -m pytest -q` ⇒ **148 passed**（与 Phase 3 关闭时同一数量），
  `src/`、`tests/`、两个冻结 adapter、Experiment Doctor 均未被写入。

## 18. Phase 4 verdict

本轮证据只回答一个问题：**一个陌生的真实研究项目，能否在没有专用 adapter、没有编造 provenance 的前提下进入 Result Doctor？**

- 能：110 逻辑行 YAML、34 个仓库内文件、0 行代码改动，走通 reported result → transformation → aggregation →
  members → selection 五层，candidate set 停在诚实的 partial/unknown。
- 复算给出 6 个真 PASS，未知给出 6 INCONCLUSIVE + 3 NOT_APPLICABLE + 1 NOT_RUN，没有任何 UNKNOWN 被偷换成结论。
- 代价可量化：成员枚举占行数 27%、路径重复占 locator 引用 82%；两处静默误判（G1/G2）是首次 onboarding 的真实风险。
- 本轮**不评价论文本身**（§18 of brief）：上面所有 PASS/FAIL 只关于「打印值与仓库 artifact 的推导链是否自洽」。

`Phase 4 verdict: CLOSED`

## 19. Unique next step

实测落在「可用，但啰嗦」一侧：契约没有阻塞性缺陷、不需要新 locator、不需要新 transformation
（四类 locator 用到两类就足够表达一个真实 JSON-per-run 仓库）；超预算与两处静默误判（G1/G2）才是问题。

同时本轮量出一个必须由下一轮正面处理的张力：**`≤100 逻辑行` 与 `禁止目录扫描决定成员` 互相冲突**。
成员逐个写是防火墙的代价（1 cell 15 行、每加一个 cell +25 行），
所以简化只能走**作者面**，绝不能走「加通配/加发现能力」那条路——那等于把 §9 的两门纪律换成便利。

唯一方向：**Generic UX 简化轮**。验收物就用本轮这份真实 manifest：
在**不删任何 provenance、不加发现能力、不动 8 对象 schema 与 RD001–RD008** 的前提下，
把 110 逻辑行降到 ≤100，并消除 G1/G2 两类静默误判。范围严格限于三类：

1. 横向简写的 lowering（纯语法糖，语义不变）：成员 `identity:` 默认取成员自身文件的 pointer；
   `_size` 接受 `{value, statement, note}` 这种带 companion 的合法尺寸写法（B1）。
2. 错误/判据文本：`E_UNKNOWN_KEY at .../aggregate` 补一句「members 与 member_rule 写在 cell 层级」；
   RD001/RD006 的 reason 在 `reported_center` 里出现空白对齐的「标签 + 数字」时，明确提示这是 locator 读宽了。
3. 作者文档：把「读表格行必须带 `text:` 片段」「`quantity` 必须携带行身份」「渲染用 `format` 不用 `round`」
   三条写成契约使用说明（本轮三条都是用户靠撞才知道）。

