# Result Doctor — Phase 0 设计报告（真实证据驱动的 Problem Definition / Schema / Rules / Oracle）

- 日期：2026-09-27
- 阶段：Phase 0 / Design。**不编码、不建包、不建 CLI、不修改 Experiment Doctor**
- 上游事实源：两个真实公开项目的盘上产物 + 论文原文 + 本会话独立重算。所有引用给 `file:line` 或表/页号
- 证据等级记法：`DIRECT`（代码/产物/论文中逐字存在）· `DERIVED`（由直接证据确定性重算得到）· `DECLARED`（作者散文声明，未必有产物支撑）· `INFERRED`（结构性猜测，**永不升级为事实**）· `UNKNOWN`（证据不足）
- 一句话定位：**Experiment Doctor 证明一个 run 是怎么产生的；Result Doctor 证明若干 run 是怎么变成论文里某一个被报告的数字的。**

---

## 1. Executive conclusion

Result Doctor 要解决的问题被两个真实项目逐条证实存在，且不是"文档写得不够仔细"这一类可归因于作者疏忽的问题：

1. **一个异常透明的团队仍然无法让被报告数字可核验。** GMMVI 的 README 用整段散文声明了候选搜索的代数、被剔除 seed 的数量与理由、以及"最佳 config 是打印到终端后人工誊抄进评测 config 的"。即便如此，其 Experiment-3 主表（Table 8）中 BreastCancer 一行的 9 个数字**没有一个能从发布产物重算得到**——发布产物里的 `BC_EVAL` 其实是另一个 wandb 项目（`logregacc`）的导出，论文所需的 `MMD:` 列在盘上根本不存在（`DIRECT`：列扫描；§5.2）。同一条链在 TALOS 行则**逐位闭合**（`DERIVED`：18/18 个数字精确复现）。同一项目、同一脚本、同一张表，两端相差一个数量级。
2. **候选宇宙在最好的情况下也只能部分恢复。** GMMVI 最终候选 grid = 98 组 / 1074 个参数点，被弃用 grid（作者主动保留并发布的 `previously_tried_grids/`）= 35 组 / 1152 点——**弃用量大于采用量**（`DERIVED`：本会话展开）。而这 35 个弃用组与最终组**共用同一个 `wandb.group` 身份串**（`DIRECT`，35/35 重合）。exp1/exp2 用的是 `method: bayes` 连续采样，尝试次数只受墙钟约束，且 fetch 阶段还有两道丢弃过滤（`sweep_fetching.py:17-22`）——真实尝试数 `UNKNOWN`。
3. **选择事件确实发生、且其结果确实偏离"朴素读法"，但没有一处落盘。** 从产物重算 argmin 冠军并与评测 config 比对：99 个组中 **85 个精确命中冠军**、**6 个命中的是非冠军 run**（其中 `GMM100/sepyrux` 评测用的值 1.139 对冠军 0.676，不是并列）、**4 个匹配不到任何存活的搜索 run**（`DERIVED`/`DIRECT`，§5.3）。TorchSSL 侧的选择准则则完全可代码恢复：在**测试集** top-1 准确率上做运行内最大值（`fixmatch.py:206-217` + `ssl_dataset.py:247-252`，`DIRECT`），一次 run 里最多被重复评测上百次。
4. **± 的语义与散文标签在两项目里都错，且两种错法相反。** TorchSSL `README.md:58` 自称 "standard errors"，实际是 `round(np.mean,2)+"±"+round(np.std,2)` 且 `np.std` 默认 ddof=0、全仓库无 `/sqrt(n)`（`average_log.py:132`，`DIRECT`）；用 ddof=0 恰好复现发布值（95.14±0.05、95.02±0.09，`DERIVED`）。GMMVI 从不声称 std，它印的是 **3 倍标准误** `std*3/sqrt(n)`（`fetch_exp3.py:55,108,111`，`DIRECT`）。同一失败类的两个方向。
5. **呈现层决策依赖单元格之外的数据。** GMMVI 的加粗由整行 9 个方法的 3-STE 区间重叠决定，且 `larger_is_better` 两分支算子不对称（`>=` vs 严格 `<`，`fetch_exp3.py:57-63`，`DIRECT`）——被剔除的 run 会同时移动均值、±和**谁的格子被加粗**。

结论：Result Doctor 有明确、独立、可核验的问题域，且 Experiment Doctor 的 10 条规则**不覆盖**其中最关键的部分（候选集、选择图、呈现依赖、跨产物矛盾）。建议进入 Phase 1，scope 见 §15。

---

## 2. Result Doctor 问题定义

Result Doctor 是一个**只读**工具，输入是「一个论文中的被报告数字」加上「产生它的项目产物」（脚本、结果文件、日志、聚合产物），输出是该数字的 **candidate → selection → aggregation → transformation → reported** 证据链，以及链上每一环的证据等级与状态。

它回答的六类问题（来自 §1 的真实观察，不是设想）：

| # | 问题 | 真实锚点 |
|---|---|---|
| Q1 | 这个被报告数字能否从被声明的成员 + 被声明的变换确定性重算出来？ | GMMVI TALOS 行 18/18 复现 vs BC 行 0/9 复现 |
| Q2 | 聚合成员集合能否被枚举，剔除是否既被记录又可绑定到具体成员？ | `bad_run_ids` 12 个 uuid ↔ 盘上 22 个 `.bad`，绑定 `UNKNOWN` |
| Q3 | 每一次选择事件的准则（指标/数据划分/方向/范围/平局/时机）是否有直接证据？ | 6/99 组评测 config 等于非冠军；TorchSSL 测试集运行内取最大 |
| Q4 | 候选集能恢复到什么程度？弃用的搜索代际能否与存活 run 区分？ | 1074 采用点 vs 1152 弃用点共用组名 |
| Q5 | ± 到底是什么语义，与项目自己的散文是否一致？ | ddof=0 std 被叫作 standard error；3·STE 从不叫 std |
| Q6 | 从原始指标到表格单元之间发生了哪些变换，是否有未被记录的变换？ | 取负、仅 `bi_accuracy` 分支 ×100、secondary 先求和、mean/std 各自独立取整、Top5 列被写入 Top-1 值 |

它**不回答**：这个结果好不好、作者是否有意挑选、这篇论文可不可信（§8）。

---

## 3. 与 Experiment Doctor 的边界

Experiment Doctor v1.0.0 的规则面（只读核查其 `rules` 自述）：

```
ED001 run 身份  ED002 seed 溯源  ED003 历史代码溯源  ED004 有效配置溯源
ED005 指标选择溯源  ED006 聚合成员溯源  ED007 聚合数值一致性  ED008 ±语义一致性
ED009 终止溯源  ED010 运行环境溯源
```

**真实重叠（必须承认，不能靠改措辞回避）**：ED005 的问题正是"被报告指标代表 run 的哪一个观测"，这与"checkpoint/epoch 选择"在概念上相交；ED006/ED007/ED008 与本报告 RD002/RD001/RD005 也相交。

**边界划法（一句话）**：Experiment Doctor 的评价对象是 **一个 run 或一个已声明聚合的内部一致性**；Result Doctor 的评价对象是 **候选集合与被报告结果之间的关系**，其中候选集合、选择图与呈现层在 Experiment Doctor 的实体模型里没有承载对象（其 entity 只有 `run / family / aggregation`，且 aggregation 的成员必须来自已发现的 run 候选）。

| 观察到的事实 | 归属 | 判据 |
|---|---|---|
| run 的最后一步 vs 最好一步 | **ED005**（已有） | 选择发生在单个 run 内部 |
| 1074 个候选参数点中哪 1 个被提升 | **RD** | 选择跨越未被报告的候选集合 |
| 99 组中 6 组提升的是非冠军 | **RD** | 需要候选集 + 选择图才能表述 |
| `bad_run_ids` 使 n 从 10 变 4 | **ED006 部分 / RD 扩展** | ED 检查成员可追溯；RD 检查"同数量声明↔清单↔盘上文件"三者可绑定 |
| ± 是 3·STE 而散文说 std | **ED008**（已有） | 语义与措辞比对 |
| ± 用 ddof=0 复现、ddof=1 复现不出 | **RD**（RD001 的组成） | 需要重算并区分公式族 |
| 加粗取决于同行 8 个对手 | **RD** | 比较集合是 ED 模型外对象 |
| 发布的 `BC_EVAL` 被后续 fetch 覆盖 | **RD** | 产物 supersession，属结果层而非 run 层 |
| Table 5 与 Table 8 同项不同值 | **RD** | 跨产物矛盾 |
| run 的 git/环境/seed 溯源 | **ED**（RD 只引用 `run_ref`） | §12 不复制上游 |

Result Doctor 通过引用连接上游：`run_ref{project, run_name, artifact_path?, run_hash?, lock_hash?}`——**不**重记 Python 版本、CUDA、seed 溯源、git commit、数据集指纹。

---

## 4. 公开研究对象筛选

### 4.1 候选与被拒原因

| 候选 | 结论 | 原因 |
|---|---|---|
| **GMMVI**（Arenz et al. 2023, arXiv:2209.11533 / TMLR） | **选为主对象** | 论文 PDF 在本地；Zenodo 产物 bundle 在本地；超参搜索 + 10-seed 评测 + 剔除清单 + LaTeX 表生成 + 跨论文 baseline 全部齐备 |
| **TorchSSL**（公开 SSL 库与 benchmark） | **选为第二对象** | 补 GMMVI 缺失的结构：真正的 per-epoch/per-iteration checkpoint 选择、EMA 第二副本、可用的聚合脚本、6 份完整绑定日志 |
| CRDA（Mohebbi et al., ICML 2024） | 未使用 | 已就地核验其结构（`scripts/collect_*_results.py → all_results.csv`）。其形态与 GMMVI/TorchSSL 的 7 类结构高度重复，按 §20「第一个项目覆盖够就不为数量强找」不再计入 |
| 用户自己的 Row-Amplitude / RAA 材料 | **禁用** | §3 明令。另做独立性核验：GMMVI `repo/` 全量字节正则 `amplitude|raa|row_amp` 命中 1 处，为 `hyperopt/sweep_names.txt:42` 里 wandb 随机 sweep id `bysjraaj` 的**同形误报**（`DIRECT`）；GMMVI 论文与代码不涉及行幅概念 |
| 只有一个 seed 的 toy repo / 仅 inference demo / 无结果表仓库 | 未选 | §3 排除项 |

规模纪律：全程未训练模型、未下载数据集（GMMVI 结果 bundle 与 TorchSSL 日志为既有本地材料）、未跑完整复现。

### 4.2 为什么是两个而不是一个

GMMVI 完全没有 checkpoint 选择（每个 run 只取历史 CSV 的**最后一行**，`fetch_exp3.py:98,102`，`DIRECT`），TorchSSL 完全没有候选集/超参搜索产物（仓库内 `sweep|grid_search|optuna|ray.tune` 零命中，`DIRECT`）。两者相加才使 §20 的 7 项结构全部有真实证据支撑。

---

## 5. 真实结果链反向追踪

### 5.1 链 A：完整闭合 —— GMMVI Table 8 `H(q)` × TALOS × Sepyfux = `−25.03 ± 5.46`

| 环节 | 事实 | 等级 | 出处 |
|---|---|---|---|
| 论文单元格 | `−25.03 ± 5.46`（同列 `-ELBO` 为 `−16.64 ± 5.26`） | DIRECT | arXiv v2 p.29 Table 8 |
| 产生它的调用 | `fetch_exp3.py:245-252`（**已被注释掉**；仓库 HEAD 唯一活跃调用是 `:271-275`） | DERIVED（唯一匹配产物 schema 的调用） | 代码 + 列名 + 12 个 id |
| 成员 | `TALOS_EVAL/sepyfux_talos/` 保留 4 个 `run_*.csv`，另有 6 个 `.bad`；10 份 config | DIRECT | 盘上清点 |
| 成员身份绑定 | run 序号 ↔ wandb uuid 的对应**不在产物中**（config 无 id 无 seed，CSV 无 id 列） | UNKNOWN | `run_1_config.yml` 实测仅 5 个 config 块 |
| 每成员取值 | 该 run 历史 CSV **最后一行**的 `entropy` | DIRECT | `fetch_exp3.py:98,102` |
| 均值 / ± | `mean` / `np.std(ddof=0)*3/sqrt(4)` | DIRECT+DERIVED | `:55,108` |
| 变换 | 无取负（仅 `elbo_fb:` 分支取负）、无 ×100（仅 `bi_accuracy:` 分支）、`np.sum` 单元列表=恒等、`%.2f` | DIRECT | `:99-100,136-139,103,64-71` |
| 复算 | n=4：mean −16.64 ± 5.26 / −25.03 ± 5.46 → 与论文逐位相同；ddof=1 → ±6.07 / ±6.31（不符）；含 `.bad` n=10 → −45.32 ± 42.91（不符） | DERIVED | 本会话重算 |
| 整行 | TALOS 9 方法 × 2 指标 = 18 个数字全部匹配 | DERIVED | 同上 |
| 剔除理由 | README:176-186 "sometimes unstable leading to outliers with very high ELBOs" + 论文 Table 5 caption | DECLARED | `README.rst:176-186` |
| 剔除数量对应 | 声明 5/3/6/6 + zamtrux 2 ↔ 盘上 `.bad` 10+12 ↔ 代码 uuid 10+12 | DIRECT | 三方一致 |
| 剔除准则可重算？ | **否**：`sepyfux_talos/run_2.csv.bad` 的**最终** `-elbo`=−14.54 落在被保留 run 区间 −12.24…−20.21 之内，"很高 ELBO"只在 run 中段可见（其 entropy min=−143.5）；另有 1/6/9 号仅跑 62/3/32 步 | DIRECT（观察） | 剔除是按人工 uuid 清单执行，非规则 |

**这一条链给出 Result Doctor 必须能表达的全部要素，也给出它必须保持 UNKNOWN 的位置。**

### 5.2 链 B：断裂 —— GMMVI Table 8 `-ELBO` × BreastCancer × Samtron = `78.00 ± 0.02`

| 环节 | 事实 | 等级 |
|---|---|---|
| 论文单元格 | `78.00 ± 0.02`（Table 8 p.29；Table 5 p.12 同值） | DIRECT |
| 盘上 `BC_EVAL/samtron_bc/` | 10 个 run、0 个 `.bad`、10 份 config | DIRECT |
| 重算 | mean 78.0132；ddof=0 σ=0.0151 → 印 `78.01 ± 0.01`；ddof=1 → `78.01 ± 0.02` | DERIVED |
| 结论 | **没有任何行选取规则（last/min/max/时间均值）能得 78.00**；BC 整行 9 格中 5 格不符（Sepyrux 论文 79.91±0.93 vs 重算 80.13±0.79；Sepyfux 79.78±0.40 vs 79.68±0.40；Samyrux/Samyrox 亦不符） | DERIVED |
| 断点定位 | `fetch_exp3.py` 有**两个**调用写同一 `BC_EVAL` 目录：`:191-195`（项目 `gmmvi-exp3-eval`，secondary=`MMD:`）与 `:256-260`（项目 `logregacc`，secondary=`bi_accuracy:`）。盘上 BC/GC/BCMB/GCMB 的 CSV **含 `bi_accuracy:` 而全无 `MMD:`** → 现存产物是 `logregacc` 的导出，论文 BC 行所需的产物不在 bundle 里 | DIRECT（列扫描 + 代码状态） |
| 论文 BC 行的真实来源 | `INFERRED`（`:191-195` 是 secondary 为 MMD 的唯一候选）——**不升级** | INFERRED |
| 同根因旁证 | GC 行 9 格中 7 格精确相符、2 格差 0.01（Samyrox 585.10 vs 585.11） | DERIVED |
| `GC_EVAL/` 异常 | 18 个子目录 = 9 个 `*_gc` + 9 个无关 `*_bc` | DIRECT（存在）/ UNKNOWN（成因） |

**断点的性质**：不是"数字对不上"，而是**结果产物的身份/版本不可判定**——写产物的是目录名，多个不同数据源复用同名目录且无哈希、无版本、无产生者记录。

### 5.3 链 C：选择图 —— GMMVI 超参搜索 → 10-seed 评测

- 机制（`DECLARED`，`README.rst:162-167`）：`fetch_exp3.py` 打印冠军超参 → **人工誊抄**进 `configs/exp3 (eval)/*.yml` → 跑 10-seed 评测。唯一机器可读的联系是人起的 `wandb.group` 串（`INFERRED` 级绑定）。
- 本会话独立重算（99 组：从 `run_*_config.yml` 复算组内 argmin 冠军，再与对应 EVAL 组 config 逐字段比对）：

| 结果 | 数量 | 代表样本 | 等级 |
|---|---|---|---|
| 评测 config == 重算冠军 | **85/99** | `BC/samtrux`（冠军 `run_9`）、`WINE/samtrux`（`run_14`）、`GMM20/sepyfux`（`run_13`） | DERIVED |
| 评测 config == **非冠军** | **6/99** | `BC/samyrox` 冠军 `run_22`=78.430 而评测用 `run_23`=78.591；`GMM100/sepyrux` 冠军 0.676 而评测用 1.139（**非并列**）；`BC/zamtrux`、`GC/samtrux`（4 位小数近并列）、`Planar4/samyrox` | DIRECT |
| 评测 config 匹配**不到任何存活搜索 run** | **4/99** | `GMM100/samtrox`、`GMM100/sepyfux`、`TALOS/zamtrux`、`WINE/zamtrux` | 事实 DIRECT，来源 UNKNOWN |
| 冠军是否落盘 | **否**。`fetch_exp3.py:45` 只 `print`；全仓库文件类型清点无 `best.yaml`/stdout 归档 | DIRECT |

- exp1/exp2 侧：冠军**隐含**在 `best_runs/0..29.csv`（`np.argsort` 升序，`sweep_fetching.py:80-82`）；107/107 组的 `best_runs/0.csv` 末行 `-elbo` 与 `all_sweeps.csv` 列的 argmin 精确一致（`DERIVED`）。但**跨组提升**（哪个算法成为评测候选）不落盘，且 `table_exp1.py:33` 的判定是按算法名字符串子串做的，`table_exp1.py:16-22` 在浮点匹配失败时**仍使用 `config.values[0]`**（`DIRECT`）。实测：`exp1_bc` 全局冠军是 `septfux`(78.455)，而被提升进 10-seed 评测的是 `septrux`(78.463) 与 `sepyrux` → **选择范围（scope）不是全局，而是每个设计选择列**（`DERIVED`）。
- 时间维额外一层：exp1 评测的"最终值"实为**墙钟截断后的最优**——`fetch_exp1.py:20-21` 按 `_runtime <= max_time` 切掉尾部，`:33` 注释 "First runs went OOM shortly after 3 hours"（`DIRECT`）。

### 5.4 链 D：TorchSSL 的 checkpoint 选择与聚合

| 环节 | 事实 | 等级 |
|---|---|---|
| 选择准则 | `best_eval_acc` 运行内取最大（严格 `>`，平局保最早），`models/fixmatch/fixmatch.py:206-217`；13 个算法类同模板 | DIRECT |
| 选择指标所在划分 | `loader_dict['eval']` 来自 `train=False` → CIFAR/SVHN/STL-10 **即 test split**，代码中不存在 validation split（`ssl_dataset.py:230,247-248,252`）。例外：ImageNet 用官方 `val/` | DIRECT |
| 权重副本 | `evaluate()` 先 `ema.apply_shadow()`（`:232-235`）→ 选的是 EMA 副本；但 `apply_shadow` 只动 `named_parameters()`，BN running buffer 不是 EMA 的（`train_utils.py:366-378`） | DIRECT |
| 评测密度 | 每 `num_eval_iter`(5000) 一次；超过 0.8·总迭代后改为每 1000 一次（`:225-226`）→ 单次 run 被重复评测上百次 | DIRECT |
| 每 run 报告值 | 该 run 全部评测里 `BEST_EVAL_ACC` 的最大值 ×100 | DIRECT+DERIVED |
| 单元格 | `average_log.py:81` 成员分组 = run 名去掉最后一个 `_` 段（= seed）；`:132` `str(round(np.mean,2))+u"\u00B1"+str(round(np.std,2))`，`np.std` 默认 ddof=0 | DIRECT |
| 复算 | fixmatch/cifar10_250 三种子 best=95.16/95.07/95.18 → 95.14±0.05 与 README 精确相同；flexmatch → 95.02±0.09 精确相同。ddof=1 给 0.06/0.11，SE 给 0.03/0.06，均不符 | DERIVED |
| 声明冲突 | `README.md:58` "best accuracies with **standard errors**" | DIRECT（措辞）↔ 与上条重算矛盾 |
| 隐式成员门槛 | `average_log.py:23-34`：日志必须含字面量 `'1048000 iteration'` 才被计入（6 份本地日志全过） | DIRECT |
| 真实变换缺陷 | `:52-53` 算出的 `avg_20_5acc/avg_50_5acc` 被丢弃，`:58-59` 把 **Top-1** 滚动均值写进 `Top5_20/Top5_50` 列 | DIRECT |
| 声明 vs 产物 | 声明 3 seeds；仓库 191 份 config **全部 `seed: 0`**，生成器硬编码 `seeds=[0]`（`scripts/config_generator.py:192,262`） | DIRECT |
| 名义入口失效 | HEAD 的 `eval.py:37` 读 `checkpoint['train_model'/'eval_model']`，而 HEAD 所有 `save_model` 写的是 `model/optimizer/scheduler/it/ema_model` → 官方评测脚本加载不了自家 checkpoint | DIRECT |

---

## 6. 观察到的真实 failure modes（14 项，全部有锚点）

| # | Failure mode | 一句话事实 | 最强等级 |
|---|---|---|---|
| FM1 | 被报告数字无法从发布产物重算（成员集合身份错误） | BC 行 0/9 复现，因 `BC_EVAL` 实为 `logregacc` 导出 | DERIVED |
| FM2 | 结果产物被后续产生者覆盖且无版本/哈希记录 | 两个 fetch 调用写同一目录名；现存 CSV 缺 `MMD:` 列 | DIRECT |
| FM3 | 聚合成员匿名（成员↔外部 run id 不可绑定） | `run_i.csv` 无 id、config 无 id/seed | DIRECT（缺失事实） |
| FM4 | 剔除被记录但准则不可重算 | 12 个 uuid + 22 个 `.bad`；某被剔 run 的**末值**在被保留区间内 | DIRECT |
| FM5 | 未声明的成员资格门槛 | 日志须含 `'1048000 iteration'` 才计入（`average_log.py:23-34`） | DIRECT |
| FM6 | ± 语义与散文标签冲突 | "standard errors" ↔ `np.std(ddof=0)` | DIRECT |
| FM7 | ± 语义是 `k·SE` 但 k 从未声明 | `std*3/sqrt(n)`（`fetch_exp3.py:55,108`） | DIRECT |
| FM8 | 选择图偏离朴素读法且无记录 | 6/99 提升非冠军、4/99 无可匹配候选、冠军从不落盘 | DERIVED/DIRECT |
| FM9 | 候选集跨代复用同一身份键 | 35 个弃用组与最终组共用 `wandb.group`；参数值抽检 0 重合 | DIRECT |
| FM10 | 候选宇宙受墙钟/采样器/fetch 过滤三重不可见限制 | bayes 采样 + `sweep_fetching.py:17-22` 两道丢弃 + 只有末段可见 | DIRECT |
| FM11 | 变换链部分分支生效且不可从产物判定走了哪条 | 取负仅 `elbo_fb:`、×100 仅 `bi_accuracy`、secondary 先 `np.sum`、mean/std 各自独立取整 | DIRECT |
| FM12 | 呈现层（加粗）依赖单元格外的数据，且算子在两个分支不对称 | `fetch_exp3.py:57-63` | DIRECT |
| FM13 | 同一量在不同产物处取值不同（跨产物矛盾） | Table 5 p.12 Sepyfux×STM300 `26.87±0.45` vs Table 8 p.29 `26.69±0.39`（后者 Sepyrux 列才是 26.87±0.45） | DIRECT |
| FM14 | 比较集中的基线数字来自外部实现且无聚合脚本 | `iBayesLR_results/` 由 `mat_to_csv.py:15` 从 MATLAB `.mat` 转换；`VIPS_results/` 5 run≠10；Table 8 基线行无生成脚本 | DIRECT/DECLARED |

> FM 编号用于 §7 矩阵与 §10/§13 的"哪个真实观察证明它值得存在"追问。共 14 项，无一项为填表而虚构。

## 7. Evidence Matrix

| Failure Mode | Real Project | Observed Example | Evidence Source | Grade | 可确定性判定? | Possible Status | ED 已覆盖? | RD 需要? |
|---|---|---|---|---|---|---|---|---|
| FM1 报告值不可重算 | GMMVI | BC 行 0/9 vs TALOS 行 18/18 | 重算 + CSV 列名 | DERIVED | 是 | PASS / FAIL / INCONCLUSIVE | ED007 部分 | **是** |
| FM2 产物被覆盖 | GMMVI | `BCMB_EVAL` 被 `:271-275` 重写 | 代码状态+列扫描 | DIRECT | 是 | PASS / FAIL / INCONCLUSIVE | 否 | **是** |
| FM3 成员匿名 | GMMVI | uuid↔index 不可恢复 | config/CSV 字段 | DIRECT | 否（只能报缺失） | INCONCLUSIVE | 否 | **是** |
| FM4 剔除不可重算 | GMMVI | `run_2.csv.bad` 末值在保留区间内 | CSV + `:250-251` | DIRECT | 部分 | PASS / INCONCLUSIVE / FAIL | ED006 相邻 | **是** |
| FM5 未声明门槛 | TorchSSL | `'1048000 iteration'` 字面量 | 代码 | DIRECT | 是 | PASS / FAIL | 否 | **是** |
| FM6 ±标签冲突 | TorchSSL | README:58 vs `np.std` | 代码+README | DIRECT | 是 | PASS / FAIL / INCONCLUSIVE | ED008 | 部分重叠，RD 需重算支撑 |
| FM7 ±含未声明因子 | GMMVI | `std*3/sqrt(n)` | `fetch_exp3.py:55` | DIRECT | 是 | PASS / FAIL | ED008 | 部分重叠 |
| FM8 选择图偏离 | GMMVI | 6/99 非冠军、4/99 无匹配 | 重算 + config 比对 | DERIVED | 是（重算冠军） | PASS / FAIL / INCONCLUSIVE | 否 | **是** |
| FM9 候选跨代同身份 | GMMVI | 35/35 组名重合、值 0 重合 | grid 展开 | DIRECT+DERIVED | 否 | INCONCLUSIVE / PASS | 否 | **是** |
| FM10 候选不可见 | GMMVI | 16,645 存活行；尝试数 UNKNOWN | `all_sweeps.csv` + 过滤代码 | DIRECT | 否 | UNKNOWN（不得填 PASS） | 否 | **是** |
| FM11 变换链 | 双 | 取负/×100/求和/双取整/Top5 列错值 | 代码 | DIRECT | 是 | PASS / FAIL / INCONCLUSIVE | 否 | **是** |
| FM12 呈现依赖 | GMMVI | 行内 9 方法 + 算子不对称 | `:57-63` | DIRECT | 是（可复算加粗） | PASS / FAIL / INCONCLUSIVE | 否 | **是** |
| FM13 跨产物矛盾 | GMMVI | Table5 vs Table8 | PDF 双页 | DIRECT | 是 | PASS / FAIL | 否 | **是** |
| FM14 基线外部来源 | GMMVI | `.mat` 转换 / 5≠10 run | 目录+脚本 | DIRECT/DECLARED | 部分 | INCONCLUSIVE / UNKNOWN | 否 | **是** |

## 8. 科学推断防火墙

Result Doctor 只记录，不推断动机。以下为**必须被测试锁死**的禁区（每条右列给出本项目的真实反例）：

| 禁止的推断 | 为什么在本数据上会错 |
|---|---|
| 存在多个 run ⇒ cherry-picking | GMMVI 评测阶段对存活 run **无挑选**，只做均值（`fetch_exp3.py:98-113`）；run 数多来自同名 group 重跑（`STM300_EVAL/samyrux` 30 个 run，`:167-171` 声明因 OOM 加核重跑） |
| `best.pt` / `BestAcc` ⇒ 测试集泄漏 | TorchSSL 的 `BestAcc` 定义清楚且可复算；"选择指标算在 test split"是**独立事实**（划分事实 ≠ 违规判定） |
| 盘上只有 N 个 run ⇒ 只跑了 N 次 | `sweep_fetching.py:17-22` 主动丢弃；真实尝试数 UNKNOWN；"logs present ≠ runs executed" |
| 产物里找不到候选 ⇒ 候选只有一个 | TorchSSL 无任何搜索产物 ⇒ 候选宇宙 **UNKNOWN**，不是"单候选" |
| 论文值 ≠ 重算值 ⇒ 论文错了 | FM1 的正确结论是"现存产物不是该单元格的来源"（成员身份问题），不是"数值错误" |
| 有 run 被剔除 ⇒ 学术不当 | GMMVI 剔除有理由（不稳定性/OOM）、有清单、有数量对应，且声明"额外评测主要帮助了表现最差的 SEPYFUX/SEPYRUX"（`README.rst:156`） |
| 组名相同 ⇒ 一定混淆了不同代际 | 抽检 3 组参数值交集为 0：可经参数重建代际，但无身份字段 → 既不得判"混淆"也不得判"纯净" |
| 加粗/最优标记 ⇒ 作者宣称该法最优 | 加粗是脚本的区间重叠规则自动产生，且算子不对称（FM12）；属呈现层，不属结论层 |
| 状态填 PASS 来"补齐"证据 | 沿用 ED 纪律：不可观察 ⇒ UNKNOWN / INCONCLUSIVE，绝不冒充 |

---

## 9. 最小 Schema

设计约束：**每个字段都必须能被 §6 的某个 FM 指认为必要**。等级四元组沿用 ED 的 `{value, status, source, confidence_note}` 与 `SourceRef{path, key, line, artifact_id, note}`，不新造。

```text
ReportedResult
  locus: {artifact: paper_pdf|tex|readme|xls, page/table/row/column, quoted_text}   # FM1 FM13：必须存论文原文
  metric_name, direction_semantics                                   # FM11（`-elbo` vs `elbo_fb:` 符号）
  value: EvidenceField, spread: EvidenceField                        # 二者各自带等级
  spread_form: {kind: none|std|sem|k_sem, k, ddof}                   # FM6 FM7（k=3 / ddof=0 是本数据实测值）
  members: [AggregationRef | RunRef]
  transformations: [TransformationRef]                               # 有序链
  selection_events: [SelectionEventRef]                              # 该值被哪些选择喂出
  status_matrix: 每环节独立状态（不做综合）
  presentation_marks: [{mark: bold|best, depends_on: ComparisonSetRef}]   # FM12

ResultArtifact                       # FM2 FM3 的直接承载体
  path, sha256, size
  produced_by: {script, call_site, invocation_args, project_id?}     # 覆盖性诊断的依据
  superseded_by / superseded_from: [ResultArtifactRef]               # FM2：同名目录被不同数据源写过
  schema: {columns: [...]}                                            # FM1/FM2：`MMD:` 列缺失即断点证据

Aggregation
  formula: {center: mean|median|…, dispersion: <表达式>, ddof, k_factor}
  member_rule: {kind: enumerated|by_pattern|by_query, expression}    # FM5 `by_pattern`='1048000 iteration' 门槛
  members: [AggregationMember]
  exclusions: [{member_ref, reason_evidence_grade, reason_ref?, list_ref?}]   # FM4：清单存在≠准则可重算
  parent_aggregation_ref?                                            # §18：只做一层嵌套，不建 DAG
  recalculation: {observed_center, observed_dispersion, matches_reported: PASS|FAIL|UNKNOWN}

AggregationMember
  run_ref: {project, family_key, run_name, artifact: ResultArtifactRef, external_id?: EvidenceField}   # FM3：external_id 常为 UNKNOWN
  observation_selector: {kind: last_row|best|min|max|mean|time_truncated_at, param?}   # 链A last vs 链D best vs `fetch_exp1.py` 时间窗
  observed_value: EvidenceField

CandidateSet                          # RD 与 ED 最重要的新增对象（§16）
  kind: hyperparameter|checkpoint|run|model|dataset|reported_result
  universe_status: RECOVERED|PARTIAL|DECLARED_ONLY|UNRECOVERABLE      # 四值，禁止用默认值暗示"完整"
  declared_size: EvidenceField                                        # GMMVI: 1074 采用点 / 1152 弃用点 / README「24 per candidate」
  surviving_size: EvidenceField                                       # 98 组 / 盘上 run 数
  generation: {id, superseded_by?, shared_identity_key?}              # FM9：代际共用 wandb.group
  identity_collision: {key_type, collision_count, value_overlap}      # 35/35 组名重合；参数值抽检 0 重合
  unobservable_sources: [{kind: sampler|wallclock|fetch_filter|early_stop, evidence_ref}]   # FM10
  promotion_evidence: EvidenceField                                   # FM8：冠军是否落盘（本项目=否）

SelectionEvent                        # §17：一个类 + 类型枚举，不拆成六个类，也不压成 `best=true`
  kind: checkpoint|run|hyperparameter|model|dataset_level|reported_result
  criterion: {metric: EvidenceField, split: EvidenceField, direction, scope, tie_break, timing}
      # 实测支撑：TorchSSL split=TEST(DIRECT) / GMMVI scope=per-design-choice-column(DERIVED) / timing∈{in-training, fetch-time, table-writing-time}
  candidate_set_ref, winner_ref, is_recorded: EvidenceField            # FM8：is_recorded=否 是本项目主结果
  effect_on_report: {changes_n, changes_spread, changes_presentation_mark}   # FM12

ComparisonSet                         # FM12 FM14
  members: [ReportedResultRef]
  role: {self, competitor, baseline_source: internal|external_publication}
  external_origin?: EvidenceField                                     # FM14 `.mat` 转换 / VIPS 前作
  presentation_rule: {expression, operator, symmetric: bool}

Transformation                        # FM11
  step: sign_flip|scale|sum_of_part|round|format|percent|delta|best_of_n|truncate_window
  applied_at: code|script|manual                                      # manual：链C「打印后人工誊抄」
  condition: EvidenceField                                            # 仅 `bi_accuracy` 分支 ×100
  grade, note

EvidenceReference                     # 复用 ED SourceRef 形状，不重定义
```

被**明确排除**的对象（避免"为未来扩展"设计）：`ResultDAG`（真实证据只需一层 `parent_aggregation_ref`）、`MetricRecord` 的新 schema（ED 已有）、`ClaimRef`（属 Paper Doctor）、`TrackerConnection`（引入网络与凭据面，与 ED 无网络立场一致）、任何 `score`/`confidence` 字段。

## 10. Schema 必答的 12 问（§11 验收对照）

reported value→`ReportedResult.value`；metric→`metric_name`；来自哪个 aggregation→`members`；成员→`AggregationMember`；成员来自哪个 run/checkpoint→`run_ref + observation_selector`；checkpoint 如何选→`SelectionEvent(kind=checkpoint)`；候选有哪些→`CandidateSet.declared/surviving_size`；选择策略→`SelectionEvent.criterion`；最终数字如何算→`Aggregation.formula + recalculation`；spread 语义→`spread_form`；是否经变换→`transformations`；哪些字段 UNKNOWN→每字段自带的 `status`（工具输出允许整链 UNKNOWN，且不得因 UNKNOWN 而阻断）。

## 11–14. 最小规则集（8 条）

状态模型沿用 `PASS / FAIL / INCONCLUSIVE / NOT_APPLICABLE / NOT_RUN`。

### RD001 Reported-Value Recomputability
- **Question**：给定被声明的成员与被声明的变换，这个被报告数字能否被确定性重算出来？
- **Required Evidence**：`ReportedResult{value,spread,spread_form}` + `Aggregation{members,formula}` + `Transformation[]` + 成员观测值
- **PASS**：重算 mean 与 ± 在声明精度内与论文一致（链 A：18/18 逐位一致）
- **FAIL**：成员与公式齐备而重算不一致（链 B 若 `MMD` 列存在仍不符则应判 FAIL）
- **INCONCLUSIVE**：不一致且成员身份本身不可判定（链 B 当前正确状态：**不是 FAIL**，因为断点在上游身份，而非算术）
- **NOT_APPLICABLE**：该单元格不来自任何聚合（单 run 直报，或基线外部来源 FM14）
- **False-positive 边界**：多重取整顺序差异（mean/std 各自 `round(_,2)` 再拼接）可造 0.01 级不符 → 必须先按 `Transformation` 逐步施加，不得直接比浮点
- **False-negative 边界**：成员集合错但均值巧合接近（GC 行 7/9 相符即临界实例）
- **Real Project Motivation**：链 A vs 链 B
- **Overlap with ED**：ED007 检查"项目内已发现聚合 vs 盘上 run"，RD001 锚定**论文中的被报告值**并要求显式 `Transformation` 链；两者可对同一数据给出不同状态

### RD002 Aggregation Membership Derivability
- **Question**：成员集合能否被枚举？被排除者是否既有记录又可绑定到具体成员？是否存在未声明的成员门槛？
- **PASS**：成员可由显式清单/查询唯一确定，且排除项可绑定（GMMVI `.bad` 与 uuid 清单数量对应）
- **FAIL**：存在产物无法解释的成员差（`STM300_EVAL/samyrux` 30 个存活 run 对 10-seed 声明）
- **INCONCLUSIVE**：成员匿名（FM3：uuid↔index 不在产物中）；或门槛存在但未声明（FM5 若未从代码恢复则不可判）
- **NOT_APPLICABLE**：单成员聚合
- **False-positive 边界**：分组规则本身是代码语义（`average_log.py:81` 去掉最后一个 `_` 段）——不同命名习惯下会不同，不得凭命名猜测成员集合
- **False-negative 边界**：剔除清单完整但准则不可重算（FM4）→ 不得因此判 PASS 完备
- **Motivation**：FM3 FM4 FM5；**Overlap**：与 ED006 同域，RD002 只增加"排除项可绑定性"和"未声明门槛"两项 ED 无承载对象的检查（须在文档中显式承认相交）

### RD003 Selection-Criterion Recoverability
- **Question**：每一次选择事件的准则（指标/划分/方向/范围/平局/时机）是否有直接证据？选择结果是否落盘？
- **PASS**：准则可从代码逐字段确定（TorchSSL：metric=`eval/top-1-acc`、split=TEST、direction=max、tie=最早、timing=in-training、result=持久化 `model_best.pth`）
- **FAIL**：被声明的选择与实际产物矛盾（6/99 组提升的是非冠军 → 若声明"取最优"即 FAIL）
- **INCONCLUSIVE**：仅代码路径隐含、无显式声明（`table_exp1.py` 子串判定）
- **NOT_APPLICABLE**：该结果无选择环节
- **False-positive 边界**：近并列（4 位小数）不是偏离，须按声明精度判等（`GC/samtrux` 实例）
- **False-negative 边界**：`is_recorded=false` 时不得因"重算能对上 85/99"而升格为 DIRECT
- **Motivation**：FM8；**Overlap**：run 内部的 last-vs-best 归 ED005；跨 run/config 的选择归 RD003

### RD004 Candidate-Set Recoverability
- **Question**：候选集能恢复到什么程度？被弃用的搜索代际能否与存活产物区分？
- **状态语义**：输出 `RECOVERED / PARTIAL / DECLARED_ONLY / UNRECOVERABLE` + `declared_size`/`surviving_size` 两个独立字段
- **PASS**：候选集显式且与存活产物一致（GMMVI exp3：grid 展开 1074 点，README:132 声明 24/candidate，实测 sepyfux 各组恰 24）
- **FAIL**：**仅当**声明互相矛盾（如声明的 grid 点数与 config 展开不符）——"候选比存活多"不是 FAIL
- **INCONCLUSIVE**：身份键跨代复用（FM9），且不得据此判"已混淆"或"未混淆"
- **NOT_APPLICABLE**：声明无搜索的单配置实验（TorchSSL 的 NO 覆盖不得被写成 NOT_APPLICABLE——它是 UNRECOVERABLE）
- **False-positive 边界（最重要）**：`surviving_size` 永远不得被当作 `universe_size`（FM10：sampler/wallclock/fetch_filter 三重不可见）
- **Motivation**：FM9 FM10；**Overlap**：无（ED 模型无候选集对象）——RD 的核心差异化规则

### RD005 Spread-Semantics Consistency
- **Question**：发布的 ± 是什么（std / SE / k·SE / 分位数 / IQR），与项目自己的措辞和实际公式是否一致？
- **PASS**：措辞与公式一致且可复现该数值
- **FAIL**：措辞与公式冲突（FM6：README 说 standard error，代码是 ddof=0 std，且重算证明只有 ddof=0 复现发布值）
- **INCONCLUSIVE**：无措辞声明（FM7：3·SE 从未被命名）
- **NOT_APPLICABLE**：无 spread 的单元格（TorchSSL ImageNet 表无 ±）
- **False-positive 边界**：`k·SE` 与 std 在 n=1 时数值相同，不得据此判一致
- **Motivation**：FM6 FM7；**Overlap**：ED008 已做"± vs 散文措辞"比对，RD005 增加**公式族重算**这一证据来源（两者应共享证据而非互相重复判定，Phase 1 需明确不双写）

### RD006 Transformation-Chain Auditability
- **Question**：从原始指标到表格单元之间的每一步变换是否被枚举？是否存在未被记录的变换？
- **PASS**：变换链逐步可施加于原始值并得到论文串（含精度与格式）
- **FAIL**：变换被代码声明但产物显示未施加/施加错对象（FM11 的 `Top5_20/50` 列被写入 Top-1 值，`:58-59`）
- **INCONCLUSIVE**：分支条件依赖不可恢复的调用状态（无法确定该单元格走了哪个分支）
- **NOT_APPLICABLE**：原始值即报告值（需证据，非默认）
- **False-positive 边界**：论文值≠raw 值 ≠ 论文错（×100、best-of-N、取负都是合法变换）
- **Motivation**：FM11 FM2；**Overlap**：无对应 ED 规则

### RD007 Presentation-Dependency Integrity
- **Question**：单元格的呈现（加粗/"最优"标记）是否依赖单元格之外的数据？该依赖与比较集合是否可复算？
- **PASS**：给定产物可精确复算出论文实际加粗的格子（GMMVI 在 GMM20/GMM100/STM20/WINE/Planar4(sam\*) 行可复算）
- **FAIL**：呈现规则内部不自洽到无法确定唯一结果（`>=` 与严格 `<` 不对称只使边界情形两义 → 边界实例判 INCONCLUSIVE 更妥，FAIL 留给"规则与论文实际加粗矛盾"）
- **INCONCLUSIVE**：比较集合的成员值不可重算（BC/BCMB/GC/GCMB 的 `MMD` 列已被覆盖 → 加粗不可复算）
- **NOT_APPLICABLE**：无呈现标记的表
- **Motivation**：FM12；**Overlap**：无

### RD008 Cross-Artifact Consistency
- **Question**：同一量在 ≥2 处产物（论文两表、论文 vs README、论文 vs 生成的 xls/csv）出现时是否一致？结果产物是否被后续产生者覆盖？
- **FAIL**：同一量两处取值不同（FM13：`26.87±0.45` vs `26.69±0.39`；FM2：`MMD:` 列消失）
- **PASS**：两处一致（TorchSSL README vs 重算 2 个格子精确一致）
- **INCONCLUSIVE**：只有一处存在
- **False-positive 边界**：两处测量口径本就不同（p.12 与 p.29 的表可能对应不同设置），须先证明是同一量再报矛盾——本例中判为矛盾的依据是行/列标签与其余 8 格一致
- **Motivation**：FM13 FM2 FM14；**Overlap**：无

> 不新增 RD009+。已明确舍弃的候选规则及理由：**"test 指标参与选择"**（ED005/ED003 已提供证据面，且该判断跨入结论性宣称）；**"排除项数量异常"**（数量异常不是缺陷，RD002 只查可绑定性）；**"候选集规模合理性"**（评价性）；**"作者声明可信度"**（禁评分）。

## 15. Acceptance Oracle

### 15.1 Synthetic oracle（确定性已知答案）
固定 seed 生成 5 个最小 fixture，每个 fixture 内 selection/aggregation/paper 值由构造者**预先写入真值表**：

| fixture | 构造目的 | 期望 |
|---|---|---|
| S1 干净链（3 run × 2 checkpoint，显式 last-epoch，mean+ddof=0 std） | 全链闭合 | RD001 PASS，RD003/006/007/008 PASS，RD004 声明一致 |
| S2 成员身份错位（产物目录名相同但数据源不同，缺列） | 复刻 FM1/FM2 | RD001 **INCONCLUSIVE**（不是 FAIL），RD008 FAIL |
| S3 未声明 k·SE（代码 3·SE，README 说 std） | 复刻 FM7 | RD005 INCONCLUSIVE / FAIL（措辞侧），RD001 PASS |
| S4 选择偏离声明（声明取最优，实际提升非冠军） | 复刻 FM8 | RD003 FAIL 且不得被 RD001 掩盖 |
| S5 候选不可见（产物 3 run，声明 grid 24 点，fetch 过滤器丢弃） | 复刻 FM9/FM10 | RD004 = PARTIAL/UNRECOVERABLE，`surviving_size` 不得写入 `universe_size` |

要求：S1–S5 各自断言**每一条 RD 的状态**（含 NOT_APPLICABLE 与 UNKNOWN），断言集是可执行向量，不是文档描述。

### 15.2 Real-project oracle（冻结，本会话已产出全部数字）
GMMVI：`TALOS_EVAL/sepyfux_talos` 的 4 个保留值与 ±5.46；BC 行不可重算断言；98/1074 与 35/1152 与 35/35 组名重合与 0 值重合；85/6/4 三分账；18/18 TALOS 复现；5/9 BC 不符；Table5/Table8 冲突对。
TorchSSL：`95.14±0.05`、`95.02±0.09` 两格（ddof=0 精确复现、ddof=1 与 SE 均不符）；6 份日志的 `BEST_EVAL_ACC` 三元组（95.16/95.07/95.18、95.12/94.91/95.02）；`'1048000 iteration'` 门槛；`Top5_20/50` 错值；191 份 config 全 seed 0。
全部数字连同产生它们的**命令**一起冻结（沿用 ED 的"逐条实跑过"规程）。预期规则状态向量随同冻结，未来实现必须复现该向量。

### 15.3 Firewall oracle（负向测试，锁死 UNKNOWN 纪律）
§8 的 9 条禁区逐条转为负向断言，例如：
- 输入"同组名两代 grid、参数值 0 重合"⇒ 工具输出**既不得**含"混淆"**也不得**含"纯净"（本会话真实踩过的一次假设修正）；
- 输入"盘上仅 3 个 run 且无搜索产物"⇒ 不得输出 `universe_size=3`，必须 UNRECOVERABLE；
- 输入"论文值≠raw 值但存在 ×100 变换"⇒ RD006/RD001 不得报 FAIL；
- 输入"存在 12 个 `.bad`"⇒ 不得产生任何挑选/违规措辞；
- 断言输出 schema 中**不存在** `overall_score`/`confidence`/`trust_score`/`verdict` 字段（结构测试）。
另加措辞门禁：报告文本禁出现 `p-hacking`/`cherry-pick`/`misconduct`/`可信度评分` 等评价词（沿用 ED 宣传语禁令的写法）。

## 16. Explicit non-goals（Phase 0 与 Phase 1 都不做）

不建包/不建 CLI/不建 GitHub repo；不修改 Experiment Doctor、不新增 ED 规则；不做 Agent / CrewAI / AutoGPT / 多代理编排；不做 dashboard / server / database / plugin 体系；不做 LLM judge 或论文语义解析；不做 tracker/MLflow/W&B/Neptune 客户端（wandb 是本项目唯一缺口来源，但接 API 引入网络与凭据面，超出只读取证定位——记为 §17 开放问题而非 Phase 1 任务）；不自动重跑/自动调参/自动发现实验；不做 metric extraction 以外的结果推断（更不做任何结果推断）；不产综合分；不判断论文好坏；不评价作者诚信；不做 Paper Doctor；不做 v1.x roadmap。

## 17. Open questions（保持 UNKNOWN，不猜测）

| # | 未决 | 需要什么证据才能关闭 |
|---|---|---|
| O1 | GMMVI BC/GC 行论文值的真实产物是否存在 | `gmmvi-exp3-eval` 项目的 `BC_EVAL` 导出，或 wandb 访问 |
| O2 | 被剔除 run 与剔除理由的逐条绑定（OOM vs 发散） | wandb run 元数据或作者侧记录 |
| O3 | exp3 评测实际使用了哪些 seed（config 不设 `start_seed`） | `gmmvi==1.0` 默认值 + wandb run 名 |
| O4 | `GC_EVAL/` 内混入 9 个 `*_bc` 子目录的成因 | 打包/上传侧记录 |
| O5 | TorchSSL 整表（约 48 格）是否全部由当前 `average_log.py` 版本产生 | 作者侧 `final_res.xls` 或运行记录 |
| O6 | TorchSSL 各 cell 背后的候选/调参次数 | 不可恢复（OneDrive 分享是不完整子集）——预期永久 UNKNOWN |
| O7 | 相机就绪版（TMLR）与 arXiv v2 表格是否完全等价 | 本轮仅在 arXiv v2 核验，另一版本为 DECLARED 沿用 |
| O8 | RD005 与 ED008、RD002 与 ED006、RD001 与 ED007 的共享证据接口该怎么定 | 属实现期设计问题；Phase 1 首版必须显式声明"复用"而非"重判" |

## 18. Phase 0 verdict

**YES —— Result Doctor 值得进入 Phase 1 实现。**

判据：§24 十问全部可答；14 个 failure mode 全部有真实锚点与文件行号；其中 FM1/FM2/FM5/FM8/FM9/FM10/FM11/FM12/FM13/FM14 共 10 项在 Experiment Doctor 的实体模型中**无承载对象**；RD001 在链 A 上给出可机器验证的全链闭合、在链 B 上给出可定位的断点——同一工具在两端都工作，这是最小可行性的直接证明。

## 19. Recommended Phase 1（唯一 scope）

实现 **minimal schema（§9 的 8 个对象）+ 两个 frozen archive loader（GMMVI exp3 bundle、TorchSSL log 集）+ RD001–RD008 八条规则 + §15.1 五个 synthetic fixture + §15.2 两个项目的冻结真实验收（含预期状态向量）+ §15.3 firewall 测试**。一次交付，不拆分。

该 scope 内**不含**：wandb/tracker 客户端、论文 PDF 解析器（表值以人工转写记录 + 页表定位引用的方式冻结，沿用本轮做法）、任何自动实验发现、任何评分或排名、任何 GUI、对 Experiment Doctor 的改动。

Phase 1 的验收门禁沿用 ED 已证明有效的四条规程：全量测试可复跑、规则状态向量与冻结基线逐项 diff=0、UNKNOWN 纪律由负向测试锁定、文档哈希以 git blob 口径登记。

---

*本报告引用的两个项目均为第三方公开材料，只读核验，未做任何改动。核心纪律：observable evidence ≠ scientific intent；工具只证明链，不证明动机。*
