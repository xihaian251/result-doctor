# Result Doctor Phase 6 — CLI, Distribution, Fresh-User Workflow

冻结状态：Phase 0/1/2/3/4/5 全部 CLOSED。本轮授权范围：简报 §32 允许清单
（`cli.py`、`pyproject.toml`、`README.md`、`tests/test_cli.py`、`phase6/`）+ 简报 §1–§38。
本轮唯一问题：第一次使用 Result Doctor 的研究者，能否从安装开始，用一条 CLI 命令完成 audit 并理解输出。

开工前基线复核（不是改动）：`161 passed / ruff check / ruff format --check / mypy` 全绿，与交接文档 §6 一致；
唯一不符项见 §15 的 D-P6-1。

---

## 1. Executive result

| 判据 | 结果 |
|---|---|
| `result-doctor` 入口点 | 存在，`[project.scripts]` = `result_doctor.cli:main`，wheel 内 `entry_points.txt` 已核对 |
| `result-doctor audit PATH` | 可用，PATH 可为 manifest 或其所在目录 |
| 真实 98 行 manifest | 加载并审计成功，exit 0 |
| 16 条 finding | 状态向量 PASS 6 / FAIL 0 / INCONCLUSIVE 6 / NOT_APPLICABLE 3 / NOT_RUN 1，与 Phase 4/5 冻结记录逐项相同 |
| CLI/API 等价 | fresh venv 安装的 CLI 产出的 JSON 与 repo 内 `canonical_json(audit_manifest(...))` **字节相同**（13,396 B，sha256 `2ad02c8fb6ace0af`） |
| JSON 确定性 | 同一 manifest 连续两次运行字节相同；三个独立环境（fresh/editable/final wheel）产物互为字节相同 |
| 校验错误 UX | G1/G2 复现物、缺文件、指错文件四种情形均 exit 2 并原样打印 `{code} at {where}: {problem}`，无 traceback |
| 科学 FAIL 伪装成进程失败 | 否。`example_b` 的 RD001 FAIL 用例断言 exit 0 |
| fresh 非 editable wheel 安装 | 通过：`import result_doctor` 指向 venv site-packages，PyYAML 由 metadata 真实拉入，`pip check` 干净 |
| editable 冒烟 | 通过（在隔离 venv 内，见 D-P6-9） |
| schema 改动 | **0**（`schema.py` 未触碰） |
| RD001–RD008 语义改动 | **0**（`rules.py`/`compute.py`/`status.py`/`evidence.py`/`bundle.py`/`audit.py` 未触碰） |
| 新增错误码 / locator family / manifest 字段 / 自动发现 | **0 / 0 / 0 / 0** |
| 门禁 | pytest **170 passed**（161 + 9）、Phase 1 子集 76 passed、ruff check 绿、format 绿（26 files）、mypy 绿（14 files） |
| Blockers | **0** |
| 真人 fresh-user 测量 | **未完成**（本轮为零上下文 agent 代理，见 §12 的诚实标注与 §18） |

一句话：科学内核一行未改，它现在有一条能被陌生人执行的命令。

### 改动清单（全部改动，无遗漏）

| 文件 | 改动 |
|---|---|
| `src/result_doctor/cli.py` | **新增**。argparse 单命令 `audit`、`render_text()`、`--json` 写文件、退出码 0/2/1 |
| `src/result_doctor/__main__.py` | **新增**。`python -m result_doctor` 三行转发，未安装也能跑 |
| `tests/test_cli.py` | **新增**。9 个用例，全部是「CLI 与 API 不得漂移」的对照断言 |
| `pyproject.toml` | 2 处：`[project.scripts]`；`description` 去掉已失效的 `(Phase 1 minimal implementation)`（D-P6-6） |
| `README.md` | **新增**。quickstart（§18/§19 + §12 摩擦修订，见 §13） |
| `phase6/RESULT_DOCTOR_PHASE6_REPORT.md` | 本报告 |

**未改动**：`schema.py`、`rules.py`、`status.py`、`compute.py`、`evidence.py`、`bundle.py`、`audit.py`、
`manifest.py`、`loaders/gmmvi.py`、`loaders/torchssl.py`、以及 `tests/` 下任何既有用例与 fixture、
`phase0`–`phase5` 下任何证据文件。证明方式：无 git，故用 mtime 逐文件核对 —— 15:00 之后被修改的 `.py`
只有上表三个新文件，其余源码最后修改时间停留在 Phase 5 的 14:33 或更早。

---

## 2. 现状清点（简报 §3，动手之前）

| 检查项 | 事实 |
|---|---|
| 既有 CLI / entry point | 无。`pyproject.toml` 无 `[project.scripts]`，`src/` 无 `cli.py`、无 `__main__.py` |
| package metadata | `name=result-doctor`、`version=0.1.dev0`、`requires-python>=3.11`、`dependencies=["PyYAML>=6"]`、`[tool.setuptools.packages.find] where=["src"]` |
| `__init__.py` 公开面 | 已导出 `audit_manifest` / `bundle_from_manifest` / `canonical_json` / `ManifestError` / `RuleFinding` / `RuleStatus`，CLI 无需新增公开符号 |
| README / 安装说明 | 仓库根**没有** README（`phase4/README.md` 是试点上游 README 的副本，不是本项目文档）→ 简报 §16「只读 README」的前置物不存在，本轮新建 |
| 入口层是否够用 | 够用：`audit_manifest(path)` 已经把 bundle→rules→NOT_RUN 全包了，且连「文件不存在」都已是 `ManifestError`（`E_ARTIFACT_MISSING`），CLI 不需要任何新错误语义 |

结论：最小缺口 = 一个 `cli.py` + 一个 entry point + 一份 README。无重构需要，故未重构。

---

## 3. 命令契约

```text
result-doctor [--version] {audit} ...

result-doctor audit PATH [--json REPORT_JSON]
```

| 契约项 | 冻结值 | 依据 |
|---|---|---|
| 子命令 | 只有 `audit`。无 `scan/init/run/serve/watch/doctor/sync/upload/plugins` | 简报 §4/§21 |
| `PATH` | manifest 文件本身，或其所在目录；目录只解析成固定名 `result-doctor.yml` | 简报 §4，D-P6-10 |
| 自动找 manifest | **不做**。不递归、不 glob、不猜别名 | 简报 §22 |
| `--json` | 取值 = 输出文件路径，**写文件**，不是布尔开关，也不写 stdout | 简报 §7 首选形式，D-P6-3 |
| Markdown / HTML 报告 | **不做**（代码里不存在可复用的 renderer，`canonical_json` 是唯一序列化器） | 简报 §8 |
| 颜色 / emoji / 表格框线 / 进度条 | 无 | 简报 §26 |
| CLI 框架 | stdlib `argparse`，零新增依赖 | 简报 §25 |
| CLI 内是否重新实现规则 | 否。只调用 `audit_manifest()` | 简报 §5 |

`--version` 打印 `result-doctor 0.1.dev0`（`__version__` 未 bump：本轮不是 release，简报 §31）。

---

## 4. 终端输出

真实试点输出（`phase4/rtdl-revisiting-models`，逐字）：

```text
# result-doctor audit phase4/rtdl-revisiting-models/result-doctor.yml
RD001   PASS            mlp-tuned/adult
        reason: recomputed rendering equals the reported cell
RD001   PASS            mlp-tuned/california_housing
        reason: recomputed rendering equals the reported cell
RD002   PASS            aggregation:agg:mlp-tuned/adult
        reason: membership enumerable and every exclusion bindable
...
RD007   NOT_RUN         rule:RD007
        reason: no target of this class was supplied (comparison_sets is empty)
RD008   INCONCLUSIVE    quantity:metrics.test.score/adult
        reason: the quantity is printed in a single product, so there is nothing to cross-check
RD008   INCONCLUSIVE    quantity:metrics.test.score/california_housing
        reason: the quantity is printed in a single product, so there is nothing to cross-check

PASS: 6
FAIL: 0
INCONCLUSIVE: 6
NOT_APPLICABLE: 3
NOT_RUN: 1
```

设计决定：

- 首行回显实际加载的 manifest —— 代理测量证明它是排查「我到底审了哪个文件」最有效的信息；
- 每行 = `rule_id / status / target`，固定列宽，顺序 = `(rule_id, target)`，与 `audit_bundle` 已冻结的顺序一致（简报 §23）；
- `reason` 单独缩进一行，**逐字打印、不截断**：缩短一句证据说明是科学损失，而列对齐本身已保证可扫读；
- 末尾状态计数按 `RuleStatus` 声明顺序固定输出五项（含 0），是**计数**不是总评（简报 §6 明确允许，§34 禁止总体状态）；
- `question` 与 `rule_name` 不进终端（它们进 JSON），因为 16×2 行说明会把表格冲成文档。

---

## 5. JSON 输出

`--json report.json` 写入的内容 = `canonical_json(findings) + "\n"`，与 API 同一序列化器、同一数据模型，
不存在第二套结构（简报 §7）。试点文件 13,396 字节、单行、16 元素数组，每元素含
`rule_id / rule_name / target / status / question / measurements / evidence[] / reason`；
`evidence[]` 保留 `path / key / line / artifact_id / note` 全部可追踪字段（简报 §7 的「获得完整 finding」）。

---

## 6. 退出码语义（实测，非声明）

| 码 | 含义 | 实测输入 | 观测 |
|---|---|---|---|
| 0 | 审计跑完了，无论规则说什么 | 试点目录 / `example_b`（内含 RD001 **FAIL**） | 后者仍 exit 0，被 `test_a_completed_audit_exits_zero_even_though_a_rule_says_FAIL` 钉住 |
| 2 | manifest 不是可读契约 | `phase5/trapcheck/g1.yml` → `E_LOCATOR_TEXT at reported_results[0]/value/observed: ...`；`g2.yml` → `E_MISSING_FIELD at reported_results[1]/quantity: ...`；空目录 → `E_ARTIFACT_MISSING at ...\result-doctor.yml: the manifest file does not exist`；指到 `pyproject.toml` → `E_YAML ...` | 四条均 exit 2，stderr 原样，无 `Traceback` |
| 2 | 命令行本身写错 | `audit`（缺 PATH）、`bogus`（未知子命令） | argparse 原生 2 |
| 1 | 工具意外失败 | 未构造（无此类已知路径） | 未捕获异常自然逃逸为 1，traceback 保留给维护者 |

采纳简报 §9 推荐值（0/2/1），**不**采用交接文档 §9 草案里的「非零 = 错误」笼统说法。
副作用登记：`2` 同时覆盖「manifest 无效」和「命令行写错」两类输入错误，区分方法是后者打印
`usage:` 而前者打印 `E_* at ...` —— 已写进 `--help` 与 README（§13 修订项 2）。

---

## 7. Editable 冒烟（简报 §11 第一层）

```bash
python -m venv --system-site-packages F:/MLResearch/.phase6-venvs/editable
<venv>/Scripts/python.exe -m pip install --no-deps --no-build-isolation -e F:/MLResearch/result-doctor
<venv>/Scripts/result-doctor.exe audit <pilot> --json editable.json
```

`import result_doctor.__file__` = `F:\MLResearch\result-doctor\src\result_doctor\__init__.py`（editable 如期指向源码）；
`editable.json` 与 wheel 环境的产物字节相同。该 venv 的 `pip check` 报
`googletrans 4.0.0rc1 has requirement httpx==0.13.3, but you have httpx 0.28.1` —— 这是 `--system-site-packages`
把**本机全局环境里既有的、与本工具无关的**冲突暴露出来，不是 Result Doctor 造成的；判据以 §8 的隔离 venv 为准。

## 8. Fresh 非 editable wheel 安装（简报 §11 第二层 / §27 / §28）

```bash
python -m build --wheel --outdir F:/MLResearch/.phase6-dist/final      # build 只作为 dev 工具，未进 runtime deps
python -m venv F:/MLResearch/.phase6-venvs/final                        # 不带 --system-site-packages
final/Scripts/python.exe -m pip install .phase6-dist/final/result_doctor-0.1.dev0-py3-none-any.whl
```

| 必查项 | 结果 |
|---|---|
| `import result_doctor.__file__` | `F:\MLResearch\.phase6-venvs\final\Lib\site-packages\result_doctor\__init__.py` —— 不是 `...\result-doctor\src`，源码偷加载已排除 |
| runtime 依赖真的装上了 | `yaml.__file__` 也在该 venv 的 site-packages 内（由 `Requires-Dist: PyYAML>=6` 解析安装，简报 §13 无 blocker） |
| `pip check` | `No broken requirements found.` |
| console script | `result-doctor.exe` 存在，`result-doctor --version` → `result-doctor 0.1.dev0` |
| wheel 内容 | 14 个模块（含 `cli.py`、`__main__.py`、两个冻结 loader）+ `entry_points.txt` `[console_scripts] result-doctor = result_doctor.cli:main` |
| 是否依赖 repo cwd | 不依赖：从 `F:\MLResearch\.phase6-venvs`、以及代理从 `C:\Users\<user>\Documents\...` 运行，finding 字节相同 |
| 未做的事 | 不发布 PyPI、不打 tag、不动 version（简报 §31） |

---

## 9. 真实项目验收 + API/CLI 等价（简报 §14）

```text
api bytes  13395+1  2ad02c8fb6ace0af...   canonical_json(audit_manifest("phase4/rtdl-revisiting-models/result-doctor.yml"))
cli bytes  13396    2ad02c8fb6ace0af...   fresh-wheel CLI --json
identical: True
```

16 条 finding、`(rule, target)` 序列、状态向量三者全部一致；终端列与 `audit_manifest()` 返回列表逐项对齐由
`test_the_table_lists_one_line_per_finding_in_rule_and_target_order` 断言。试点缺失时该用例 `skipif`
（沿用 Phase 3/5 对归档的做法）。

## 10. 确定性（简报 §15）

同进程两次 `--json` 到不同文件：字节相同（`test_the_json_report_is_byte_identical_when_the_audit_is_rerun`）。
跨进程、跨安装方式三次：`pilot-fresh.json` / `editable.json` / `final.json` 三者字节相同，13,396 B。
未引入任何时间戳、随机 id、绝对路径归一化等动态字段（`canonical_json` 本身就禁 timestamps）。

---

## 11. 文档改动（简报 §18/§19/§20）

新增 `README.md`：Install（两条路由 + 明确「未发布到 PyPI」）→ Audit（两种 PATH + 真实输出样例）→
`### Which rule is which`（RD001–RD008 逐条名称与 question，**逐字取自 `rules.NAME`/`rules.QUESTION`**，
不是本文作者转述）→ target 语法说明（含 `rule:RDxxx` 这个看起来像报错的特例）→ 五态表 +
「FAIL ≠ 论文失败」「INCONCLUSIVE/NOT_RUN 记录的是缺证据」→ 退出码与 `E_*` 拒绝格式 → `--json` 语义 →
manifest 三扇门与三处指针（`manifest.py` docstring / 试点 98 行 / phase2 设计）。

未做的事：不搬 Phase 0–5 设计史，不做教程，不改科学内核来「让输出更易懂」（简报 §20 要求优先修 quickstart，本轮照办）。

## 12. Fresh-user workflow（简报 §16/§17）—— **代理测量，非真人**

诚实标注：本轮由一个**零上下文 subagent**（`general-purpose`）执行，它被禁止读取 `README.md` 与
`--help` 之外任何本项目文件，被要求从干净 venv 开始自行安装并跑通。它是「不带本项目内部知识的人」的
**代理**，不是「不懂 Python 工具链惯例的人」。**简报 §9.3 要求的真人从零测量仍未闭合**，这是本轮最大的证据缺口。

代理结论（逐字要点摘录）：审计本身**首次即成功**（`result-doctor audit <试点目录>` exit 0，16 条），
从陌生 cwd 重跑 finding 相同，README 的「两次运行字节相同」被它自行 `cmp` 验证通过。

### 计数（简报 §17，不估时间）

| 量 | 值 |
|---|---|
| 从干净 shell 到成功的 shell 步骤 | 19（其中约 30 次离散调用，含它自加的验证） |
| 因失败而多花的命令 | **1**（`pip install result-doctor` → PyPI 不存在） |
| 必需位置参数 | 1（`PATH`） |
| 必需 flag | 0（`--json` 只为交付 JSON） |
| 首次运行错误 | 1 个硬错误（PyPI）+ 1 个瞬时网络重试告警（pip 侧，已自愈） |
| 离开文档的跳数 | 4（PyPI 猜测、`ls .phase6-dist` 找 wheel、`json.load` 自查、**两次试图打开 README 指出去的 `manifest.py` docstring / phase2 设计**） |
| 手工编辑文件 | **0** |
| 首次成功前必须理解的概念 | 10 项，其中 README/help 已解释 4 项、部分解释 2 项、未解释 4 项：venv 惯例、RD001–RD008 各自查什么、target id 语法、`root:` 与产物路径如何解析 |

代理原话中最该记住的一句：「零摩擦不等于 UX 完美 —— 是因为我本来就懂 Python/venv/pip 惯例」。
因此 §13 的摩擦项按「可确定性缺陷」记录，而不是按「它跑通了」记录为通过。

## 13. 已测摩擦与处置

| # | 摩擦（全部来自 §12 实测，非臆测） | 本轮处置 |
|---|---|---|
| 1 | README 没说包未发布 → 浪费 1 条失败命令 | **已修**：Install 首句声明 + wheel 路由 |
| 2 | 退出码 2 被 argparse 复用，文档未提 | **已修**：`--help` 与 README 各写明判据（`usage:` vs `E_* at`） |
| 3 | `E_*` 码表无处可查 | **已修**：README 指出定义位置（`manifest.py`）并说明拒绝文本自带 where+fix |
| 4 | 未说明产物路径相对谁解析（它为此多跑 2 条验证命令） | **已修**：Audit 节一句「相对 manifest 的 `root:`，与 cwd 无关」 |
| 5 | 未说明 `--json` 是替代还是附加、写到哪 | **已修**：Machine-readable 节两句 |
| 6 | README 样例缺真实首行 `# result-doctor audit ...` | **已修**：样例改为逐字真实输出 |
| 7 | RD001–RD008 在允许输入里查不到含义；且 JSON 里的 `question` 终端不打印（「机器可读版比人读版更会解释」） | **已修（文档侧）**：README 增 `Which rule is which` 表，文本逐字取自 `rules.QUESTION`。**未改终端列布局**（简报 §6 示例即三列，见 §18 遗留项） |
| 8 | target id 语法无图例；`rule:RD007` 看着像报错 | **已修**：target 语法段 |
| 9 | `where` 分隔符风格不一致（文件形态保留 `/`，目录形态归一为 `\`） | **登记未修**：文本由 `manifest.py` 生成，不在本轮允许改动面（简报 §32），且改动会牵动 26 码 oracle 的既有测试 |
| 10 | 指错文件（TOML）时 `E_YAML` 附带 PyYAML 的 2 行 mark 文本，形似堆栈 | **登记未修**：来自上游异常消息，非本项目 traceback；已在 §6 记录实测 |

## 14. 回归（简报 §29/§30）

```text
python -m pytest -q                                     -> 170 passed      (161 原有 + 9 新增，0 回归)
python -m pytest -q -k "not generic and not phase5 and not cli" -> 76 passed, 94 deselected
python -m ruff check .                                  -> All checks passed!
python -m ruff format --check .                         -> 26 files already formatted
python -m mypy                                          -> Success: no issues found in 14 source files
```

未新增质量工具。既有的 26 错误码 oracle、`row4` 防火墙、「generic path 绝不产出 INFERRED/DERIVED」、
两个冻结归档的 `canonical_json` 字节不变，全部在新代码下继续通过。

## 15. 偏差与决策登记（本轮全部）

| 编号 | 内容 |
|---|---|
| D-P6-1 | 交接文档 §6 记 `21 files already formatted`，接手实测 **22**。根因：ruff 0.16 会把仓库根的 Markdown 代码块一并计入，多出的是 `HANDOFF_RESULT_DOCTOR_2026-09-28.md` 本身；源码/测试集仍是 12 + 9 = 21，**基线未被污染**。本轮该数升到 26 = 14 src + 10 tests + README.md + HANDOFF.md（`phase*`、`tests/generic_fixtures` 仍按 §4.4 排除） |
| D-P6-2 | Phase 1 子集门禁命令 `-k` 表达式追加 `and not cli`，否则 `76` 会变成 `85`。语义不变：该门禁仍是「Phase 1 的 76 条未被触碰」 |
| D-P6-3 | `--json` 采纳简报 §7 **首选**形式（取值写文件），而非布尔开关；因此终端始终是人读表，JSON 不进 stdout，避免混流 |
| D-P6-4 | 退出码采纳简报 §9 推荐 0/2/1，覆盖交接文档 §9.2 的笼统「非零退出」 |
| D-P6-5 | **真人 fresh-user 测量未做**，用零上下文 agent 代理；已在 §12 显式标注为代理 |
| D-P6-6 | `pyproject.toml` `description` 去掉 `(Phase 1 minimal implementation)`：`pip show` 会把它交给用户，阶段标注现已失真。未加 classifiers/badge/homepage（简报 §12） |
| D-P6-7 | 新增 `_force_utf8_stdout()`：Windows 下 stdout 被重定向到文件时取 cp936，finding 引用中文路径或打印值会在 encode 时崩；控制台本就是 UTF-8，故只在重定向时生效。属于交接文档 §7.4 已记坑的收口 |
| D-P6-8 | 不加 Markdown/HTML renderer（简报 §8 的条件「已有可复用 renderer」不成立：唯一的序列化器是 `canonical_json`） |
| D-P6-9 | 三层安装验证全部在 `F:/MLResearch/.phase6-venvs/` 下的独立 venv 完成，**未改动本机全局解释器**（已复核：全局 `importlib.metadata.version('result-doctor')` → PackageNotFoundError）。与简报 §11 字面的 `pip install -e .` 相比是等价性更高的替代做法 |
| D-P6-10 | 目录 PATH → 唯一固定名 `result-doctor.yml`。这是约定不是发现：不递归、不 glob、不接受别名文件 |
| D-P6-11 | 分发验证脚手架留在仓库外：`F:/MLResearch/.phase6-venvs/{fresh,editable,newcomer,newcomer-wheel,final}`（各 ~15 MB）与 `F:/MLResearch/.phase6-dist/{final/, pilot-fresh.json, newcomer-report.json}`。证据 repo `phase6/` 只含本报告；`build/`、`src/result_doctor.egg-info` 已清除，可随时 `rm -rf` 两个点目录 |

## 16. Known limitations

1. 终端表只给 `rule/status/target/reason`，规则的 question 需要查 README 或 JSON —— 简报 §6 的列集是本轮的天花板。
2. 输出不告诉用户「下一步改哪个字段」。这是契约的固有属性（工具不评分、不指示），代理 §E 已确认并记录，**没有**用「fix 提示」去补，那会变成第 27 个错误码或自动推断。
3. `--json` 只写单行 canonical JSON，无缩进版；人读 JSON 需要自行 `jq .`。
4. 版本仍是 `0.1.dev0`，未做 release 决策（简报 §31）。
5. G3/G5/G6/G7/G8/G9、B3、O1–O8 全部保持登记状态，本轮一条未顺手解决（交接文档 §11 仍然有效）。
6. `E_*` 码表在 README 只给指针，不给清单：26 码的权威定义与 oracle 在 `manifest.py` +
   `test_generic_firewall.py:463`，复制一份到文档会产生第二套真相。

## 17. Release-readiness assessment（简报 §35）

> Is the package technically ready for a 0.x public release?

**YES**，含义严格限于四项：installable（fresh wheel 在纯净 venv 装通、`pip check` 干净、依赖声明真实生效）、
usable（一条命令、两种 PATH、人读表 + 机器可读 JSON）、tested（170 条，含 9 条 CLI/API 漂移防护）、
fresh-user workflow demonstrated（**以代理为限**）。

不构成：发布许可、版本号决策、PyPI/tag/GitHub Release（本轮一律未做）。

## 18. 阻塞判据复核（简报 §7 的「documentation jumps」遗留 + §34）

§34 的 20 项逐条满足；唯一非 YES 的是 README 充分性的证据来源为代理而非真人（D-P6-5），
因此本轮判定为 CLOSED 且 blockers = 0，同时在唯一下一步里把真人测量钉成第一个动作。

```text
Phase 6 verdict: CLOSED
```

## 19. Unique next step

```text
Release Candidate / public-release audit —— 其第一个动作：一次真人从零跑通
（找一个不了解本项目的人，只给 README + 已安装 CLI + 试点目录，复现 §12 的计数表）
```

理由：本轮没有暴露任何 blocker；代理指出的最大理解缺口（RD001–RD008 含义）已在文档侧闭合；
继续加功能会违反简报 §2，而 §12 的证据缺口只能由真人跑一次来补，补完才有资格判断「是否发布」与
「是否还需要一轮 UX 工作」。
