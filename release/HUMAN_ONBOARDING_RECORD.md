# Result Doctor - 真人首次使用记录（HUMAN_ONBOARDING）

```text
test status:              COMPLETED
HUMAN_ONBOARDING:         PASS
记录日期:                  2026-09-28
证据来源:                  项目所有者回报（"找了一名未参与 Phase 0–6 的同学，在一台陌生电脑上操作"）
采集者:                    项目所有者；Qoder 未在场、未直接观察
记录表（本协议由谁执行）:     release/HUMAN_ONBOARDING_RECORD.md 的空白模板由 RC 审计轮准备
```

**证据边界（务必照此引用本文件）**：下面第 3 节的每一格要么来自所有者的直接回报，要么写 `UNKNOWN`。
Qoder 没有观察该次运行，因此未回报的细节一律不补全、不推断、不打分数。

---

## 1. tester

```text
- 未参与 Result Doctor Phase 0–6                 : 回报确认
- 不了解 Result Doctor 内部设计                   : 回报确认
- 姓名 / 身份 / 专业背景                          : UNKNOWN
- 是否有 ML 工程经验（Python / venv / pip 熟悉度）  : UNKNOWN
```

## 2. environment

```text
- 非开发机（另一台电脑）                           : 回报确认
- 操作系统 / Python 版本 / 网络状况                 : UNKNOWN
- 安装方式（本地 wheel / pip install . / 其它）      : UNKNOWN（"可以安装 Result Doctor" 被回报为成功）
```

## 3. provided materials（只允许这些）

```text
- README.md                                      : 已提供
- 已安装的 result-doctor CLI 或安装指引              : 已提供
- Phase 4 试点项目目录                              : 已提供
- 目录内已有的 result-doctor.yml                    : 已提供

禁止提供（未违反，按回报执行）:
- phase0–phase6 报告 / 内部 schema 说明 / rules.py   : 未提供
- 口头解释内部设计                                   : 未提供
- 预先告知命令或参数                                  : 未提供
```

## 4. observed outcome（所有者回报的 7 项，全部为肯定）

```text
1. 安装成功                                        : YES
2. 依据 README 独立找到正确的 audit 命令              : YES
3. audit 运行完成                                   : YES
4. 终端输出可被理解                                  : YES
5. JSON report 导出成功                             : YES
6. 整个流程可独立完成（无需外部帮助）                   : YES
7. 无需重写 manifest、无需读 Phase 0–6、无需改源码      : YES（本轮只测"首次使用已准备好的工具"）
```

## 5. 13 格可观察项 —— 未被回报的写 UNKNOWN

| # | 观察项 | 记录 |
| --- | --- | --- |
| 1 | 是否独立找到正确命令 | YES（回报） |
| 2 | 第一条命令原文 | UNKNOWN |
| 3 | 第一次执行的退出码 | UNKNOWN（audit 被回报为"运行完成"） |
| 4 | 出现的错误（原文） | UNKNOWN（未回报任何错误） |
| 5 | 查 README 的次数 / 章节 | UNKNOWN |
| 6 | 对 `PASS` 的复述 | UNKNOWN（仅回报"输出可被理解"） |
| 7 | 对 `FAIL` 的复述，是否误读为实验/论文失败 | UNKNOWN |
| 8 | 对 `INCONCLUSIVE` 的复述，是否误读为工具出错 | UNKNOWN |
| 9 | 对 `NOT_APPLICABLE` / `NOT_RUN` 的复述 | UNKNOWN |
| 10 | JSON 生成 + 是否打开查看内容 | 生成 YES；是否打开查看 UNKNOWN |
| 11 | 是否误解为 overall paper verdict | **未回报任何此类误解**（按"无受影响证据"处理，见第 6 节） |
| 12 | 主动提出的问题 | UNKNOWN |
| 13 | 需要外部帮助的地方 | 无（回报为独立完成） |

## 6. 两个已登记缺口的判定

```text
P6-U2  `where` 分隔符不一致      → 未被回报为造成任何阻断或误解  ⇒ 保持 non-blocking（P2）
P6-U3  终端不打印 question/rule_name → 同上                      ⇒ 保持 non-blocking（P3）
```

判定依据是"所有者回报流程独立完成、输出可被理解"，而不是这两项已被证明无害。
若后续真人测试逐格填了第 5 节，应以其为准更新本节。

## 7. 明确不做

```text
不打 1–10 usability 分   : 未打
不打 trust score         : 未打
不打满意度总分            : 未打
不记录"几分钟上手"         : 未记录（本轮无时间 measurement）
开放反馈原文              : 无（所有者未转述任何原话，故此处留空而非补写）
```

## 8. 结论

```text
HUMAN_ONBOARDING = PASS
```

依据: 第 4 节的 7 项被项目所有者回报为肯定，且第 5 节 #11 未出现 overall-verdict 误解的证据。
限制: 第 5 节多数格为 UNKNOWN，因此这份证据证明的是"**真人能独立完成首次 audit**"，
不证明"五档状态语义已被逐条正确复述"。后者若需要，只能再做一次逐格采集。
