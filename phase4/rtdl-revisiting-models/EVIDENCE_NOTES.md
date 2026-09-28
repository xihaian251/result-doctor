# Phase 4 证据工作表（写 manifest 之前）

项目：`yandex-research/rtdl-revisiting-models`（NeurIPS 2021, "Revisiting Deep Learning Models for Tabular Data"）
本地检出：`phase4/rtdl-revisiting-models/`，commit `e3ed46cac38568785289d8fa16b8cfa585bde27e`（sparse checkout，只取本次审计用到的文件）

本文件只做一件事：在碰 `result-doctor.yml` 之前，人工记录每个字段能不能从**仓库里已有的 artifact** 确定地拿到。
标记含义：

- `OBSERVABLE` = 四种冻结 locator（CSV column/row、JSON pointer、line、text）之一能确定性读出来
- `DECLARABLE` = 仓库里没有可解析的数字/字段位置，但作者能把这句话写进 `declared:`（并可用 locator 作为 `supported_by`）
- `UNKNOWN` = 作者也无法诚实地给出，必须留 `unknown:` 或不写

---

## 0. 本次审计的切片

1 张表：README「How to explore metrics and hyperparameters」小节打印的 MLP-tuned 每个数据集的平均 test score。
取其中 2 个代表 cell：

| cell | 打印值 | 打印位置 | 任务类型 |
|---|---|---|---|
| `mlp-tuned/adult` | `0.852` | `README.md:80` | 分类（accuracy） |
| `mlp-tuned/california_housing` | `-0.499` | `README.md:82` | 回归（R² 类，可为负） |

选这两个的理由：一个是正的分数、一个是负的分数，`round(3)` 的渲染行为在两侧都要求值；
两者都有 15 个 per-seed artifact 在仓库里。其余 9 个数据集不写。

---

## 1. reported value（打印值本身）

| 项 | 标记 | 依据 |
|---|---|---|
| 打印数字文本 | OBSERVABLE-但不可用 | `README.md:80` 整行是 `adult                 0.852`（标签与数字同行、以空格对齐）。`line:` locator 读回**整行文本**，数值闸门 `number()` 会拒绝它 ⇒ 打印值只能 `declared:` |
| 打印位置（table/row/column/quoted_text） | OBSERVABLE | `README.md:80` / `:82` 行号 + `text: "adult"` / `text: "california_housing"` 可确定性核验 |
| 「这张表等于论文 Table 2」 | DECLARABLE | `README.md:76` 是一句散文宣称；论文 PDF 不在仓库里，不能 OBSERVED |

⇒ 两个 cell 的 `value:` 用 `declared:`，把 README 行号写成 `supported_by`。

## 2. artifact path（成员文件）

| 项 | 标记 | 依据 |
|---|---|---|
| `output/<dataset>/mlp/tuned/<seed>/stats.json` | OBSERVABLE | 15 个目录（seed 0..14）真实存在，每个文件 ~4.6 KB，顶层键 `dataset/algorithm/config/environment/epoch_size/n_parameters/best_epoch/metrics/time` |
| 目录里有几个 seed | OBSERVABLE-但禁止使用 | 契约无目录扫描；成员必须由作者逐个列出（见 §9 防火墙） |

## 3. metric

| 项 | 标记 | 依据 |
|---|---|---|
| 成员数值 = `metrics.test.score` | OBSERVABLE | JSON pointer `/metrics/test/score`，例如 `output/adult/mlp/tuned/0/stats.json` ⇒ `0.8519132454581358` |
| score 对 adult 就是 accuracy | OBSERVABLE | 同一 dict 里 `metrics.test.accuracy` 与 `score` 同值；`lib/metrics.py` 的分类打分逻辑可读，但**本次不引**（只需 pointer） |
| score 对 california_housing 是什么统计量 | DECLARABLE | 回归分支里 `score` 的具体定义要靠读代码；作者只声明「它是仓库里记录的 test 统计量」，不猜名字 |

## 4. aggregation

| 项 | 标记 | 依据 |
|---|---|---|
| center = mean | OBSERVABLE | `README.md:73` 的 `df.groupby('dataset')['metrics.test.score'].mean()`；行 locator + `text: ".mean()"` 可核验 |
| 聚合口径的散文 | OBSERVABLE | `README.md:70`：`test score averaged over all random seeds`（RD005 的 wording 证据） |
| 成员集合 = 「所有 random seed」 | DECLARABLE | README 说 all random seeds，具体是哪 15 个 seed、有没有被排除的 seed，仓库没有一张清单 ⇒ `member_rule: enumerated` 由作者声明 |
| spread（std / sem / 区间） | **UNKNOWN** | README 打印的只有均值，没有任何离散度字段；`spread:` 不写 |
| 有没有排除规则 | UNKNOWN | 仓库里没有 exclusion 记录 |

复算基线（人工用 Python 独立算过，作为 oracle）：

```
adult               mean = 0.8521753373052433  -> round(3) = 0.852   (与 README:80 一致)
california_housing  mean = -0.4985475737517660 -> round(3) = -0.499  (与 README:82 一致)
```

## 5. members（15 个 seed）

| 项 | 标记 | 依据 |
|---|---|---|
| 成员值 | OBSERVABLE | `/metrics/test/score` |
| 成员身份（seed） | OBSERVABLE | `/config/seed`（整数，同一文件内），但**必须把 path 再写一遍**（契约没有「同一文件」的简写） |
| 成员名 | DECLARABLE | 目录名 `0..14` 只是路径字符串，不是身份；身份取 `/config/seed` |

## 6. selection info

仓库里有两层选择，都属于「per-member 内部」的选择，而契约的 `selection:` 绑在 cell 上：

**(a) 每个 run 内部：test 分数取的是按验证集分数选出的那一个 epoch**

| 项 | 标记 | 依据 |
|---|---|---|
| 被选中的 epoch 号 | OBSERVABLE | `/best_epoch`（如 adult seed0 = 24） |
| 选择准则的 metric | OBSERVABLE | `bin/mlp.py:250` = `progress.update(metrics[lib.VAL]['score'])`，行 locator 可核验 |
| direction（越大越好？） | **UNKNOWN** | 最大化行为写在第三方库 `zero.ProgressTracker` 里，`bin/mlp.py:136` 只给出调用；本仓库 artifact 里没有比较符号。⇒ 不能从 metric 名 `score` 猜 direction |
| scope / timing | DECLARABLE | 「每个 run 内、训练循环里」由作者声明 |
| tie-break | UNKNOWN | 无记录 |

**(b) tuned 配置的来源：一次超参搜索的最优 trial**

| 项 | 标记 | 依据 |
|---|---|---|
| objective 是验证分数 | OBSERVABLE | `bin/tune.py:131` = `return stats['metrics'][lib.VAL]['score']` |
| direction = maximize | OBSERVABLE-但不可用 | `bin/tune.py:178` 这一行文本是 `        direction='maximize',`；`observed:` 读回的是**整行**，`direction` 校验要求值字面以 `min`/`max` 开头 ⇒ 只能 `declared: {value: maximize}` + `supported_by: 行 locator` |
| 被选中的 trial | OBSERVABLE | `output/adult/mlp/tuning/0/stats.json` 的 `/best_stats/trial_id`；`/best_stats/metrics/val/score` = `0.8550591125441425` |
| chosen 产物 | OBSERVABLE-存在性 | `output/adult/mlp/tuning/0/best.toml` 真实存在（其内容 = `tuned/0.toml`） |

## 7. candidate-set knowledge

| 集合 | 项 | 标记 |
|---|---|---|
| 超参搜索 | 计划 trial 数 = 100 | OBSERVABLE-但不可用：`output/adult/mlp/tuning/0.toml:20` 是 `n_trials = 100`，行 locator 读回整行文本 ⇒ 数值只能 DECLARABLE，行内容作 `supported_by` |
| 超参搜索 | 逐 trial 结果是否可恢复 | **UNKNOWN**：`bin/tune.py` 会写 `trial_stats.json`，但仓库里没有任何 `trial_stats.json`（`git ls-files` 计数 0）；只剩 `best.toml` + 汇总 `stats.json` ⇒ universe 只能 `partial`，绝不写 `complete/recovered` |
| epoch | 候选 epoch 全集 | UNKNOWN：`n_epochs = 1000000000`（`tuned/0.toml:17`）+ `patience = 16`（`:19`）早停 ⇒ 实际跑了多少 epoch、每个 epoch 的分数都不在 artifact 里 |
| seed | 15 个 seed 是不是候选集 | 不是：它们是聚合成员，不是被挑选的候选 ⇒ 不建 candidate_set（G1 反向不变式的真实版） |

## 8. spread semantics

UNKNOWN。README 打印列里没有任何 ±、std、CI；作者不补。

## 9. transformation

| 项 | 标记 | 依据 |
|---|---|---|
| 渲染时 `round(3)` | OBSERVABLE | `README.md:73` 含 `.round(3)` ⇒ 契约的 `format` 步（mode fixed, digits 3, stage render）；`applied_at` 取 `script`（README 展示的是脚本片段，不是编译期代码） |
| 有没有 ×100 | OBSERVABLE-否 | README 打印的就是原始 0.852，没有百分比化 ⇒ 不写 `scale` 步 |
| 成员值到均值之间的其它变换 | UNKNOWN | 无记录；不猜 |

## 10. comparison dependency

| 项 | 标记 | 依据 |
|---|---|---|
| 这 11 行数字与论文 Table 2 的关系 | DECLARABLE | `README.md:76` 的散文；论文 PDF 不在 root 内，不能 OBSERVED |
| 比较集成员（其它模型/其它论文） | UNKNOWN | 本次切片只包含 MLP 一列，无同表 peer 值被审计 ⇒ 不建 comparison set（缺对象就让它缺，交给 NOT_RUN） |

---

## 11. 预判（写 manifest 前，只根据上面的标记）

- 6 层里能真正走通的：reported result（declared）、transformation（observed format）、aggregation（observed mean + 15 observed members）、member results（observed）、selection（部分 observed、direction unknown）、candidate set（partial/unknown）。
- 预期 RD001 由复算决定（真实数字对得上 ⇒ PASS）；RD003 因 direction/tie_break 不全而 INCONCLUSIVE；RD004 因 universe 为 partial 而不会 PASS；RD005 因无 spread 而不会有可判对象；RD006 由 format 步与成员链条判定；RD007/RD008 因没有比较集 ⇒ NOT_RUN。
- 预期作者面最贵的一项：per-member identity 要把同一个 path 再写一遍（30 个成员 = 30 行重复路径）。
- **本工作表不含任何代码改动建议**；缺口只登记，不动契约。
