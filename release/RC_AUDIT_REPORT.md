# Result Doctor - Release Candidate / Public-Release Audit

日期: 2026-09-28
审计人: Qoder（RC 审计 lane）
被审对象: `F:\MLResearch\result-doctor` @ Phase 6 CLOSED 之后
上游权威报告: `../phase6/RESULT_DOCTOR_PHASE6_REPORT.md`

---

## 1. Executive result

| 项 | 结果 |
| --- | --- |
| Release decision | **NOT_READY_FOR_RELEASE** |
| 唯一记录在案的理由（简报 §27） | `required human onboarding evidence pending` |
| P0 | 0 |
| P1 | 3（真人证据 / LICENSE 缺失 / 仓库无版本控制） |
| P2 | 4 |
| P3 | 3 |
| 候选版本 | `0.1.0`（原 `0.1.dev0`，本轮做 version decision，未 tag、未发布） |
| 候选 commit | **不存在** —— 该目录不是 git 仓库，无 branch / HEAD / git log |
| Wheel | 19 entries / 53,432 B / sha256 `2ab70f2ff313179b420c7ca0e3b24713f7a1fba605e0074960e70d3da1c90174` |
| sdist | 39 entries / 74,751 B / sha256 `ea9edc94ca5f9ef2717ceb72114803e9a9b27f1453e5114882a2f920056f22ff` |
| Fresh wheel | 装成 `result-doctor==0.1.0`，`pip check` clean，import 指向该 venv site-packages |
| Fresh sdist | 从 tar.gz 构建并安装成功，`pip check` clean，audit 退出 0 |
| 真实项目 audit | 16 findings，`PASS 6 / FAIL 0 / INCONCLUSIVE 6 / NOT_APPLICABLE 3 / NOT_RUN 1` |
| API/CLI 等价 | fresh wheel CLI 的 `--json` 与 repo 内 `canonical_json(audit_manifest(...))` **字节相同** |
| JSON 确定性 | 两次运行字节相同；wheel 与 sdist 产出字节相同；且**现在跨平台字节相同**（见 §13） |
| 凭证/隐私扫描 | 载荷内 0 凭证、0 用户名、0 家目录路径；sdist 测试里 8 行含 `F:\MLResearch` 默认路径（P2） |
| Tests | 170 passed（Phase 0–6 全量，无 skip 掩盖） |
| ruff / format / mypy | PASS / 28 files already formatted / no issues in 14 source files |
| schema 改动 | 0 |
| RD001–RD008 语义改动 | 0 |
| 新增功能 / 新增命令 / 新增 locator | 0 / 0 / 0 |

本轮唯一科学内容差异是**报告文件的换行符**（CRLF → LF）；findings 内容逐字节未变（§13 给出证明）。

---

## 2. Candidate identity

| 维度 | 值 | 来源 |
| --- | --- | --- |
| Distribution name | `result-doctor` | `pyproject.toml [project] name` |
| Import name | `result_doctor` | `[tool.setuptools.packages.find] where=["src"]` |
| CLI name | `result-doctor` | `[project.scripts] result-doctor = "result_doctor.cli:main"` |
| Manifest filename | `result-doctor.yml` | `cli.MANIFEST_NAME` |
| Version | `0.1.0` | **单一来源** `result_doctor.__version__`，由 `[tool.setuptools.dynamic] version={attr=...}` 在构建时读取 |
| requires-python | `>=3.11` | pyproject（ruff `target-version=py311`、mypy `python_version=3.11` 一致） |
| Runtime dependency | `PyYAML>=6`（仅此一项） | pyproject；fresh venv 实测装到 `PyYAML==6.0.3` |
| License | **空** —— 无 `LICENSE` 文件，`license` 元数据未声明 | 见 §15 blocker B-RC-2 |
| Author / Home-page | 空 | `pip show` 实测 |

命名一致性（简报 §14）: 全仓 4 种形式各司其职（`Result Doctor` 13 处=产品散文、`result-doctor` 71 处=分发/CLI/manifest 文件名、`result_doctor` 105 处=Python import、`result-doctor.yml` 37 处=manifest 文件名），错误形式（`resultdoctor` / `ResultDoctor` / `Result-Doctor`）命中 **0**。未做任何品牌重构。

版本决策依据: 此前只有 `0.1.dev0`，无任何历史 tag/release（无 VCS，也无 PyPI 记录），故 `0.1.0` 无冲突；不选 `1.0.0`，因为公共接口（manifest 契约与 loader 面）仍是早期阶段且真人首次使用证据尚未取得。

---

## 3. Human onboarding evidence

```text
HUMAN_ONBOARDING = PENDING
```

Phase 6 取得的是一次**零上下文 agent 代理**测量（该报告 §12 已明确标注）。按简报 §2，agent run 不能充当真人可用性证据，本轮我没有扮演"零上下文真人"、没有模拟真人回答、没有用自身理解补写真人体验。

本轮交付的是**采集工具**而非结论: `release/HUMAN_ONBOARDING_RECORD.md` —— 材料白名单/黑名单、6 步最小流程、13 项可观察记录位、P6-U2/P6-U3 的定向观察行、以及"不打 1–10 分 / 不打 trust score / 不统计几分钟上手"的禁止项。填表人必须是没参与 Phase 0–6 的人，观察者只抄录不解释。

在这一栏拿到真人产出之前，§28 的第一条标准不成立，release decision 只能是 NOT_READY。

---

## 4. Repository cleanliness

该目录**不是 git 仓库**（`git rev-parse` → `fatal: not a git repository`），因此不存在 tracked / ignored 之分。按四类清点:

| 类别 | 内容 | 处置 |
| --- | --- | --- |
| intended source | `src/`(457K) `tests/`(682K) `pyproject.toml` `README.md` `CHANGELOG.md` | 保留 |
| intended evidence | `phase0`–`phase6`(共 236K) `HANDOFF_*.md` `release/` | 保留 |
| vendor checkout | `phase4/rtdl-revisiting-models/` = **13M**，含自己的 `.git`（上游 `yandex-research/rtdl-revisiting-models`，pin `e3ed46ca`，2024-11-13） | 未删除（只读 pilot，交接纪律要求原始只读）；发布面处置见 B-RC-5 |
| scratch | `.mypy_cache` 2.7M、`.ruff_cache` 41K、`.pytest_cache` 27K、`__pycache__` 3 个目录 24 个 `.pyc`、`src/result_doctor.egg-info`（本轮构建产生，已清） | 已确认**全部不进 wheel/sdist**；本轮新增 `.gitignore` 覆盖这些模式，未做任何批量删除 |

`dist/` 目前存在，内容是本轮刻意产出的候选包（§24），属 intended evidence 而非 scratch。

---

## 5. Packaging identity

- `version` 此前有**三处独立字面量**（pyproject / `__init__.__version__` / README 里的 wheel 文件名）。README 那句还写死了 `result_doctor-0.1.dev0-py3-none-any.whl`，一旦 bump 就会说谎。现收敛为 `__version__` 单一来源 + README 用 `<version>` 占位；构建产物文件名实测为 `result_doctor-0.1.0-*`，与 `result-doctor --version` 输出一致。
- 载荷含全部 12 个模块 + `loaders/` 子包，无遗漏（`import result_doctor.loaders` 在 fresh venv 成功）。
- console script 在两个 fresh venv 里都真实生成 `result-doctor.exe`。
- `pip check`: wheel venv clean，sdist venv clean。
- 未新增任何依赖，未加 build backend，未做 classifiers 大扫除（简报 §12/§31）。

---

## 6. Wheel payload

19 个条目，逐条清点: `result_doctor/` 12 个 `.py` + `loaders/` 3 个 + `dist-info/{METADATA,RECORD,WHEEL,entry_points.txt,top_level.txt}`。

不含: `phase4` 供应商仓库、`tests`、任何缓存目录、`.git`、`.egg-info`、venv、绝对本机路径、token/credential。最大文件 `manifest.py` 65,912 B；总包 53,432 B。

---

## 7. sdist payload

39 个条目 = `PKG-INFO` + `README.md` + `pyproject.toml` + `setup.cfg` + `src/result_doctor/**` + `tests/*.py`(9 个) + `src/result_doctor.egg-info/**`(7 个构建残留)。

| 检查 | 结果 |
| --- | --- |
| 是否含 13M phase4 供应商仓库 | **否** |
| 是否含 venv / 缓存 / 私人文件 | 否 |
| 是否含 `CHANGELOG.md` | **否**（setuptools 默认未收录，P3-B-RC-8） |
| 是否含 `tests/generic_fixtures/` | **否** → sdist 里的 9 个测试文件无法独立运行（P2-B-RC-4） |
| 是否含 `.egg-info` | **是**（P3-B-RC-7，setuptools 构建顺序所致，不影响安装） |

---

## 8. Credential / privacy scan

方法: 直接扫描**构建产物的字节**（wheel 每个条目 + sdist 每个文件），而不是扫本机磁盘；模式 = `Bearer` / `api[_-]?key` / `secret` / `PRIVATE KEY` / `ghp_*` / `AKIA*` / `password` + 盘符路径正则 `[A-Za-z]:[\\/]` + `MLResearch` / `Users` / 用户名。

| 结果 | wheel | sdist |
| --- | --- | --- |
| 凭证形态命中 | 0 | 0 |
| 用户名 / 家目录 | 0 | 0 |
| 盘符路径命中 | 4 处，全部是 `manifest.py` 里的 `observed:/declared:/unknown:` 文案（`d:/` 被正则误判为盘符），**假阳性** | 同左 + `C:/Windows/win.ini`（防火墙测试的反例 fixture，非泄露） |
| `MLResearch` 命中 | 0 | **8 行**：`tests/test_firewall.py:22-23`、`test_generic_acceptance.py:22-23`、`test_gmmvi_acceptance.py:14`、`test_torchssl_acceptance.py:12` 把 `RD_*_ARCHIVE` 的默认值写成 `F:\MLResearch\experiment-doctor\...` |

一条方法学记录: 我先用 shell 对源码目录 grep `F:\\MLResearch`，返回**零命中**（因为该 grep 只覆盖了反斜杠形式，且把 payload 与源码混为一谈）；改成扫构建产物字节才暴露这 8 行。对"发布载荷是否干净"这类问题，权威对象是**构件**，不是工作树 grep。

这 8 行的实际风险有限: 只暴露盘符 + 目录命名，不含用户名/凭证，且四处都用 `os.environ.get(...)` 包着、目录不存在时测试自动 skip。因此记 **P2** 而非 P1（修法见 §15）。

---

## 9. README / claim audit

陌生访问者视角逐项核对（简报 §13）:

| 要求 | 状态 |
| --- | --- |
| What is Result Doctor? | 有，开头两句 |
| What does it NOT claim? | **本轮加强**：新增 "cannot detect cherry-picking or misconduct，且 clean run 不认证任何东西" —— 与 CLI epilog 的 "never concludes that a paper is reliable, unreliable, or cherry-picked" 对齐（此前 README 只说了不打分，CLI 说了但 README 没说） |
| Install | 有，且明确"未发布 PyPI"（本轮仍成立） |
| Minimal audit command | 有，两种 PATH 形态各一行 |
| 5 statuses | 有表格，含 `FAIL ≠ 实验或论文失败`、`INCONCLUSIVE = 证据不足` |
| JSON output | 有，含"additive / 与 API 同一 canonical line / 两次运行字节相同" |
| manifest pointer | 有（`manifest.py` docstring、98 行真实 manifest、Phase 2 设计） |
| current limitations | **本轮新增** 4 条：要有人写 manifest、只审 manifest 引到的证据、`loaders` 是项目专用非通用 API、只有 RD001–RD008 |
| 其它 | 去掉了写死的 wheel 版本号，避免 bump 后说谎 |

宣称边界（简报 §17）逐词检查: README/CHANGELOG/METADATA 中**不存在** `verifies papers` / `detects fraud` / `detects cherry-picking` / `guarantees reproducibility` / `proves results correct` 的正面宣称；允许集合（audits provenance / recomputes supported aggregations / checks explicit evidence consistency / preserves unknowns）与实现一致。CHANGELOG 只写本轮实测存在的能力，未写 Phase 0–6 研究日志。

未修: README 里 `phase4/` 与 `phase2/` 两个指针只在仓库检出内存在，装 wheel 的用户打不开 —— 记 P3-B-RC-9（属"发布后随公开仓库一起解决"，不阻断安装与首次 audit）。

---

## 10. CLI / public API audit

在 fresh venv（非 editable、非 repo cwd）实测:

```text
import result_doctor      -> site-packages，__version__ 0.1.0，__all__ 13 项
RULE_IDS                  -> RD001..RD008（8 个，无新增）
RuleStatus                -> PASS FAIL INCONCLUSIVE NOT_APPLICABLE NOT_RUN（5 个）
Grade                       -> DIRECT DERIVED DECLARED INFERRED UNKNOWN
import result_doctor.loaders -> ok（两个冻结归档 adapter）
result-doctor --version   -> 0
result-doctor audit <missing> -> 2，stderr = `E_ARTIFACT_MISSING at no-such-file.yml: the manifest file does not exist`
result-doctor（无参数）   -> 2，打印 usage 行，无 traceback
result-doctor bogus       -> 2
```

误暴露检查结论: 无导入即崩溃、无隐藏路径依赖（`src` 全目录 grep `environ|getenv|expanduser|盘符` = 0 命中）、无 secret/绝对路径。发现并修复 1 处**文档宣称与行为不符**（见 §13）。两个项目专用 loader 仍可从包外 import —— 属"未承诺的公开面"，记 P3 并在 README Limitations 明确标注"非通用 API，可能变动"，而不是本轮去重构导出面（简报 §10 禁止为漂亮 API 重构）。

---

## 11. Fresh wheel verification

| 步骤 | 结果 |
| --- | --- |
| `python -m build`（clean tree） | 成功产出 sdist + wheel |
| 新 venv（不含 system site-packages）`pip install dist/*.whl` | `result-doctor==0.1.0` + `PyYAML==6.0.3` |
| `pip check` | No broken requirements found |
| `result_doctor.__file__` | `F:\MLResearch\.rc-venvs\wheel\Lib\site-packages\result_doctor\__init__.py`（**不是** `result-doctor\src`） |
| cwd | 在 `C:\Users\<user>` 下执行，与仓库无路径关系（公开发布前已把真实家目录名替换为 `<user>`） |
| `result-doctor audit <试点 manifest>` | exit 0，16 findings |
| `--json` 两次 | 字节相同 |

## 12. Fresh sdist verification

同一流程换 `dist/result_doctor-0.1.0.tar.gz`：从源码构建成 wheel 后安装、`pip check` clean、`__file__` 指向 sdist venv 自身 site-packages、audit exit 0、`--json` 产出与 wheel 版**字节相同**。sdist 不缺运行期文件。

---

## 13. Real-project frozen acceptance（含本轮唯一行为改动）

试点 = `phase4/rtdl-revisiting-models/result-doctor.yml`（98 行、真实公开仓库）。

| 度量 | Phase 6 冻结值 | 本轮 |
| --- | --- | --- |
| findings 数 | 16 | 16 |
| 状态向量 | `PASS 6 / FAIL 0 / INCONCLUSIVE 6 / NOT_APPLICABLE 3 / NOT_RUN 1` | 同 |
| `--json` 字节数 | 13,396 B，sha256 `2ad02c8fb6ace0af` | 13,395 B，sha256 `2ad02c8fb6ace0af...` |
| API `canonical_json` 字节数 | 13,395 + 1 | 13,395 |

发现: Phase 6 写出的报告文件带 **1 个 CR**（`Path.write_text` 默认文本模式在 Windows 把 `\n` 译成 `\r\n`），于是"canonical JSON"的字节取决于运行平台 —— Linux 上 13,395、Windows 上 13,396。修法是 `write_json(..., newline="\n")` 一个关键字参数，落在简报 §32 允许的文件里；同时在 `tests/test_cli.py` 的既有确定性测试上加一行 `assert b"\r" not in first.read_bytes()` 作为靶测试。

修后 sha256 前缀回到 `2ad02c8fb6ace0af`，与 Phase 6 报告记录的 **API 侧**哈希一致 —— 即现在磁盘上的报告字节 = `canonical_json(...) + "\n"` 字节，跨进程/跨安装方式/跨平台同一 artifact。

零科学漂移证明（两条独立）: ① 新报告与 Phase 6 归档件做字节比对，仅在 `\r\n → \n` 归一后**完全相同**（`True`）；② 科学内核 8 文件 mtime 全部早于本轮（最晚 `manifest.py` 14:33，本轮首个改动 15:40），且 8 个 sha256 前缀记录如下: `schema 11160dfff4fc / rules 98a5606ebe0a / audit aa78408f71ac / status be3bfa57fe59 / bundle 531c96e77ff3 / evidence bc63260561c8 / compute 0bb11b3178c2 / manifest f70c48983be9`。

---

## 14. Quality gates

```text
PYTHONPATH="src;tests" python -X utf8 -m pytest -q                                     170 passed
PYTHONPATH="src;tests" python -X utf8 -m pytest -q -k "not generic and not phase5 and not cli"   76 passed
python -X utf8 -m ruff check .                                                          All checks passed!
python -X utf8 -m ruff format --check .                                                 28 files already formatted
python -X utf8 -m mypy                                                                  Success: no issues in 14 source files
```

format 计数 26 → 28 的原因: ruff 0.16 会处理根目录 Markdown 里的代码块，本轮新增 `CHANGELOG.md` 与 `release/HUMAN_ONBOARDING_RECORD.md`（二者无 Python 围栏，格式即合规）。非基线污染。
按简报 §20，核心未改 ⇒ 未重跑任何外部训练、未重跑 Phase 1/3/5 的历史大型验收（170 项测试已承载）。

---

## 15. Blocker table

| ID | 级别 | 事实 | 处置 |
| --- | --- | --- | --- |
| B-RC-1 | **P1** | `HUMAN_ONBOARDING = PENDING`，无真人首次使用证据 | 唯一阻断判定项。用 `release/HUMAN_ONBOARDING_RECORD.md` 找 1 名未参与者跑一遍；我不代跑、不模拟 |
| B-RC-2 | **P1** | 无 `LICENSE` 文件，`pyproject` 无 `license` 元数据，`pip show` License 为空 | **发布 blocker，但选择权在用户** —— 我不擅自猜 license。需一句授权（例如 MIT / Apache-2.0 / BSD-3）后再补文件+元数据 |
| B-RC-3 | **P1** | 该目录不是 git 仓库：无 branch/HEAD/log/tag，§24 要求的 candidate commit 无法产生，也无发布回滚点；且此前无 `.gitignore` | 需用户授权 `git init` + 首次提交（属发布执行准备，本轮未做）。本轮只补了 `.gitignore`，把 dist/缓存/egg-info/venv 排除模式固化 |
| B-RC-4 | P2 | sdist 收了 9 个测试文件却不含 `tests/generic_fixtures/`，解包后 `pytest` 必失败 | 后续二选一：sdist 排除 `tests`，或连 fixture 一起收。本轮不动（不影响安装与使用） |
| B-RC-5 | P2 | 若把整个目录当公开仓库发布，`phase4/` 会带走 13M 上游 yandex-research 代码**及其 `.git`**；本地工作树是稀疏检出（上游 `LICENSE` 在 git index 里被跟踪但未 materialize） | 发布仓库时应排除 `phase4/`（或改 submodule 并保留上游 LICENSE 与 pin commit 出处）。wheel/sdist 均不含它，故不阻断 PyPI 侧 |
| B-RC-6 | P2 | 4 个测试文件把归档根默认写死为 `F:\MLResearch\experiment-doctor\...`（共 8 行，随 sdist 公开） | 改法：默认值置空 + 依赖 `RD_*_ARCHIVE` 环境变量（已有 skipif）。代价是默认 `pytest` 会从"170 全跑"变成部分 skip，故本轮不改，留给用户定夺 |
| B-RC-7 | P2 | METADATA 的 Author / Home-page 为空 | 发布时随 license 决策一并补；不阻断安装 |
| B-RC-8 | P3 | `CHANGELOG.md` 未进 sdist | 一句 `MANIFEST.in` 可修，本轮不加构建机制 |
| B-RC-9 | P3 | sdist 内含 `result_doctor.egg-info`（构建残留，7 个小文件） | 同上；不影响安装 |
| B-RC-10 | P3 | README 的 `phase4/` `phase2/` 指针只对仓库检出内可读 | 随公开仓库结构一起处理 |
| P6-U2 / P6-U3 | 保持 P2/P3 | `where` 分隔符不一致；终端不打印 `question`/`rule_name` | 按简报 §5 **不提前修**：等真人测试观察是否真实阻断或造成误解，再定级 |

P0: 无。按简报 §21，我没有把"终端不够漂亮 / YAML 还能更短 / CLI 命令太少"升级为 blocker。

---

## 16. Known limitations（本轮审计自身的边界）

1. 真人首次使用未取得 ⇒ §28 至少一条不满足，判定必然 NOT_READY。
2. 本机是单平台（Windows / CPython 3.13.1）：跨平台字节确定性目前由"报告不再写 CR"+ 单测断言支撑，没有真在 Linux 上跑过构件。
3. 载荷扫描的凭证模式是常见形态集合（Bearer/API key/私钥头/云 AK/家目录），不是穷尽的 secret 扫描；本轮也未扫全机、未装任何安全 agent（简报 §12）。
4. 未做依赖版本上界与 lockfile 策略；`PyYAML>=6` 的兼容性证据只有一次解析安装。
5. `python -m build` 走隔离环境需要联网，本轮两次构建均命中网络；离线复现路径（`--no-isolation` + 本机 setuptools）未验证。

---

## 17. Release decision

```text
NOT_READY_FOR_RELEASE
```

理由（简报 §27 规定只能写这一条）:

```text
required human onboarding evidence pending
```

技术上可交付的部分已全部取证完毕: 装得上（wheel 与 sdist 两条路）、跑得通（真实 98 行 manifest 16 findings）、结果与 Python API 逐字节相同、输出确定、载荷无凭证无供应商仓库、170 测试 + 三项静态门禁全绿、schema 与 8 条规则零改动。剩下的是**证据缺口 + 两项用户决策**（license、是否纳入版本控制），不是代码缺口。

§28 的 READY 清单当前状态: 18 项里 16 项成立，`human onboarding completed` 与 `license resolved` 两项未成立（另 `working tree/release state understood` 已理解但处于"无 VCS"事实下）。

---

## 18. Exact authorized-next-action

```text
唯一下一步: 执行一次真人首次使用测试（B-RC-1）。
```

具体: 找 1 名未参与 Phase 0–6 的人，只交给 TA `README.md` + 已装好 `result-doctor 0.1.0` 的干净 venv +
`phase4/rtdl-revisiting-models/` 目录，按 `release/HUMAN_ONBOARDING_RECORD.md` 第 4 节的 13 格逐项抄录，
不得事前解释、不得事后由我补写。

拿回结果后只做一次判断: 真人被阻断 → 最小修 + 靶测试 + 全量门禁；真人顺畅 → 连同 license（B-RC-2）与
是否 `git init`（B-RC-3）一起，把唯一动作交回用户，即 `authorize release execution`。
本轮不 tag、不 push、不建 GitHub Release、不上传 PyPI。
