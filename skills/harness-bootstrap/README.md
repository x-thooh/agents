# harness-bootstrap

给一个 git 仓库搭建、移植、重做 `.harness` 工程层的抽象 skill。生成物布局是 `.harness/` 十件套
（workflow / specs / deliverables / tasks / memory / codebase-guide / scripts / git-hooks / stack-templates / config.json）。

- 正文：`SKILL.md`（修改三段纪律、设计思想、UHP 六条原则与章节对照、DSH 三形状、五阶段、记忆树、断言规范、移植清单）
- 自身门禁：`scripts/audit.py` + `tests/fixtures/`——审本 SKILL.md（frontmatter / bash 围栏 / 交叉引用 / 相对链接 / 基线记账 / 版本保质期 / 宿主实测 / 双向对账 / 规范用语 / 调度器体征）+ reference/*.md 里的跨文件 §X 引用（存在性），不依赖 git，不碰其他 skill；实现按 scope 分文件住 `scripts/scopes/`
- `reference/`：SKILL.md 放不下也没必要放的东西（坑清单、笔记骨架、验收命令），按 §二.5 阈值外置，入口只留判据与链接
- 评测：`evals/`（skill-up 套件，custom local 引擎直连 magpie，脚本判分）——验「按 SKILL.md 干活」的行为，不验 SKILL.md 自身的文字合规

## 模板（`templates/`）

模板是「某个业务域的答案」，不是通用解。拷进目标仓库后按真实阈值与证据替换示例数据。
选型与共同骨架见 [`templates/README.md`](templates/README.md)。

| 目录 | 管什么 | 阶段 / scope |
| --- | --- | --- |
| `templates/delivery-harness/` | 交付流程：需求 → 方案 → 开发 → 联调 → 自测 → CR → 自洽 → 提测 | 8 / 9 |
| `templates/go-dev-harness/` | Golang 研发的日常：契约 → 设计 → 编码（形状/错误/并发）→ 测试 → 评审 → 发布 | 6 / 9 |

两者都自带 `tests/reverse.py`（每个 scope 一条违规样本）和 `make check-strict`（示例数据判 ERROR），
阶段定义只在 `.harness/workflow/flow.json` 一处。它们与 `SKILL.md` 单向无关：模板不引用正文，
正文也不描述模板的具体规则。

## 改 SKILL.md 的门禁

```bash
python3 scripts/audit.py                    # 0 ERROR 才算改完（WARN 可接受）
python3 scripts/audit.py --check-links      # 真查外部链接，默认只报一条未检查 WARN
```

反向 fixture 一件一个缺陷，code 必须精确对上；末尾那条是正对照（证明「0 条发现」不等于「检查器没跑」）：

```bash
python3 scripts/audit.py --skill-dir tests/fixtures/bad-frontmatter   # 期待且仅期待 FM004
python3 scripts/audit.py --skill-dir tests/fixtures/bad-bash-block    # 期待且仅期待 BASH001
python3 scripts/audit.py --skill-dir tests/fixtures/bad-xref          # 期待且仅期待 XREF001
python3 scripts/audit.py --skill-dir tests/fixtures/bad-xref-table    # 期待且仅期待 XREF002
python3 scripts/audit.py --skill-dir tests/fixtures/bad-description      # 期待且仅期待 FM008
python3 scripts/audit.py --skill-dir tests/fixtures/bad-description-trigger  # 期待且仅期待 FM009
python3 scripts/audit.py --skill-dir tests/fixtures/bad-relative-link  # 期待且仅期待 LINK004
python3 scripts/audit.py --skill-dir tests/fixtures/bad-baseline-rule  # 期待且仅期待 BASE001
python3 scripts/audit.py --skill-dir tests/fixtures/bad-host-loading  # 期待且仅期待 HOST001
python3 scripts/audit.py --skill-dir tests/fixtures/bad-dual-ledger  # 期待且仅期待 DUAL001
python3 scripts/audit.py --skill-dir tests/fixtures/bad-scope-grading  # 期待且仅期待 SCOPE001
python3 scripts/audit.py --skill-dir tests/fixtures/bad-zero-baseline  # 期待且仅期待 BASE003
python3 scripts/audit.py --skill-dir tests/fixtures/bad-expiry-decor  # 期待且仅期待 BASE004
python3 scripts/audit.py --skill-dir tests/fixtures/bad-version-ungated  # 期待且仅期待 VER001
python3 scripts/audit.py --skill-dir tests/fixtures/bad-xref-ext  # 期待且仅期待 XREFDOC002（跨文件引用指向不存在的条目）
python3 scripts/audit.py --skill-dir tests/fixtures/ok-minimal --dispatch tests/fixtures/bad-inline-scope/scripts/audit.py  # 期待且仅期待 LAYOUT001
python3 scripts/audit.py --skill-dir tests/fixtures/ok-minimal   # 正对照：0 ERROR 0 WARN
```

audit.py 不判语义一致性（机器判不了）；语义项在 `SKILL.md` §六 的「判据」列标注为人判。

## 跑评测

```bash
cd ~/.agents/skills/harness-bootstrap
skill-up validate ./evals/eval.yaml
skill-up run ./evals/eval.yaml --output-dir /tmp/skillup-harness
```

引擎约定见 `evals/fixtures/engine/magpie_agent.py`：读 SessionInput → 工具循环直调
`$MAGPIE_BASE_URL/chat/completions` → 写 SessionResult。需要本地 magpie 网关在跑。

两条容易踩的评测机制（都实测踩过）：

- `skills.include` 只收 glob，**不收目录**：写 `reference` 不会打包，必须写 `reference/*`。漏了不报错，只在沙箱里留一堆悬空链接，agent 会跑去找。SKILL.md 新增外部引用时必须同步这里。
- `run_shell` 的围栏在引擎里，不在 skill-up 里：`contain_violation()` 只放行工作区内路径（加 `/dev/null` 类白名单），挡 `..` 路径段与 `~`。第一轮没这道栅时，被测 agent 读到了 `evals/cases` 和 judge 脚本本身，那一轮结果作废。判分前先确认轨迹里没出现 skill 真身目录。
- 模型选型（实测踩过）：OpenRouter 中转模型会撞 HTTP 402（余额只够 8k tokens，引擎默认请求 65536）；workbuddy/opencode-zen 直连源被 429 全封；`nvidia/z-ai/glm-5.3-flash` 每步约 10 分钟，40 分钟超时只走了 4 步。目前可用且够快的是 `ollama-cloud/nemotron-3-ultra`（约 4s/步）和 `groq/qwen/qwen3.8-27b`（约 1s/步）。换模型前先拿一条带 tools 的小请求探延迟。

## 两个用例

| case | 验什么 |
| --- | --- |
| `empty-bootstrap` | 空仓库从零建五层：结构断言 + 五阶段留痕 |
| `harness-regression` | 已有 harness 改一条规则：改前基准、分批改、改后 `make check` 变绿、反向测试 |

判分一律用 `evals/fixtures/scripts/*.sh`（script judge），不用 agent judge——同一引擎自评没有信号。

## 维护

改 SKILL.md：前后都跑 `python3 scripts/audit.py`，0 ERROR 才算改完；正文改动后重跑评测；概念变了先改 `SKILL.md` 再改用例，别反过来。
