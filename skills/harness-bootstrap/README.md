# harness-bootstrap

给一个 git 仓库搭建、移植、重做 `.harness` 工程层的抽象 skill。生成物布局是 `.harness/` 十件套
（workflow / specs / deliverables / tasks / memory / codebase-guide / scripts / git-hooks / stack-templates / config.json）。

- 正文：`SKILL.md`（修改三段纪律、设计思想、UHP 六条原则与章节对照、DSH 三形状、五阶段、记忆树、断言规范、移植清单）
- 自身门禁：`scripts/audit.py` + `tests/fixtures/`——审本 SKILL.md（frontmatter / bash 围栏 / 交叉引用 / 相对链接 / 基线记账 / 版本保质期 / 宿主实测 / 双向对账 / 规范用语 / 调度器体征 / 目录形状）+ references/*.md 里的跨文件 §X 引用（存在性），不依赖 git，不碰其他 skill；实现按 scope 分文件住 `scripts/scopes/`
- `references/`：SKILL.md 放不下也没必要放的东西（坑清单、笔记骨架、验收命令），按 §二.5 阈值外置，入口只留判据与链接
- 评测：`evals/`（skill-up 套件，custom local 引擎直连 magpie，脚本判分）——验「按 SKILL.md 干活」的行为，不验 SKILL.md 自身的文字合规

## 目录形状

标准四件照 skill 规范走，多出来的目录必须**声明理由**——没声明的目录会悄悄长成第二个入口，
下一个人不知道该读哪个。这条由 `STRUCT001` 判，不是靠自觉：

```
harness-bootstrap/
├── SKILL.md          标准：入口与元数据（必需）
├── references/       标准：按需查的支撑文档，只放 .md，不建子目录（STRUCT002）
├── scripts/          标准：可执行代码（audit.py + 一个 scope 一个文件）
├── agents/           标准：子 Agent 定义（本 skill 目前没有，不建空目录）
├── README.md         额外：维护者入口，给人看，不进 skill 上下文
├── Makefile          额外：统一命令入口（所有命令从 make 走）
├── evals/            额外：skill-up 评测套件，验行为不验文字
├── tests/            额外：自身门禁的反向 fixture + 期望表
└── templates/        额外：生成物模板，拷进目标仓库用，不是参考文档
```

「额外」不是随便加的：每一个都在 `scripts/scopes/struct.py` 的 `EXTRAS` 里带一句理由。
`reference/`（单数）、`script/`、`agent/` 这类近似拼写一律按错报——名字一歪，谁也不知道该往哪找。

## 本仓库自己的门禁

这个仓库自己也是一份 harness——它管别人怎么建 harness，所以得先过自己的关。命令只从 `make` 走：

```bash
make check          # 技能自审 + 两套模板 verify + 两套反向测试（不需要 Go）
make check-strict   # 断言 --strict 能拦下模板自带的示例数据
make check-sample   # 样例 Go 模块 vet + test（需要 Go 工具链）
make lint           # 工具层：golangci-lint（需要 Go 工具链）
make guide          # 重新生成两套 codebase-guide/index.json
```

`.github/workflows/verify.yml` 跑的是同一串命令。pre-commit 能被 `git commit --no-verify` 绕过，
CI 不能——这是 CI 唯一的职责。它**不新增断言**：目录齐不齐由模板的 `GATE00x` 判，
索引对不对由 `GUIDE001` 判；同一个断言写两处，就有两个地方会漂。CI 的两个 job 按依赖分：
`gate` 故意不装 Go（「verify 只做词法检查」这句话在那里被真实执行），`sample` 装 Go 跑
`check-sample` 与 `lint`。

## 模板（`templates/`）

模板是「某个业务域的答案」，不是通用解。拷进目标仓库后按真实阈值与证据替换示例数据。
选型与共同骨架见 [`templates/README.md`](templates/README.md)。

| 目录 | 管什么 | 阶段 / scope |
| --- | --- | --- |
| `templates/delivery-harness/` | 交付流程：需求 → 方案 → 开发 → 联调 → 自测 → CR → 自洽 → 提测 | 8 / 9 |
| `templates/go-dev-harness/` | Golang 研发的日常：契约 → 设计 → 编码（形状/错误/并发）→ 测试 → 评审 → 发布 | 6 / 9 |

两者都自带 `tests/reverse.py`（每个 scope 至少一条违规样本，外加 `--fix` 的边界样本）、
`make check-strict`（示例数据判 ERROR）和 `make fix`（只修派生数据，前置条件按目标文件排除）。
`go-dev-harness` 另有 `.harness/scripts/check_commit.py` 与 `tests/commit_msg.py`（提交消息按
Conventional Commits 判）、`.golangci.yml`（工具层，`make lint`）和可选的 `lefthook.yml`
（调度层，只委托 `.harness/git-hooks/` 的脚本）。
阶段定义只在 `.harness/workflow/flow.json` 一处。它们与 `SKILL.md` 单向无关：模板不引用正文，
正文也不描述模板的具体规则。

断言条数不在这里写：写死的数字迟早和文件不一致，数出来的值问文件自己
（`python3 templates/go-dev-harness/tests/reverse.py | grep -c PASS`）。

## 改 SKILL.md 的门禁

`make check` 里已经包含这一步；单独跑等价于：

```bash
python3 scripts/audit.py                    # 0 ERROR 才算改完（WARN 可接受）
python3 scripts/audit.py --check-links      # 真查外部链接，默认只报一条未检查 WARN
```

反向 fixture 一件一个缺陷，code 必须精确对上；第一条是正对照（证明「0 条发现」不等于「检查器没跑」）：

```bash
make fixtures       # = python3 tests/fixtures.py：全部 fixture 逐条比对期望的 code
```

期望清单只有一处——`tests/fixtures.py` 的 `CASES` 表，它跑在 `make check` 里。
README 和 `references/acceptance.md` 都不再抄第二份：抄出来的表迟早和第一份不一致，
而「表说这条规则有人守」的信用就建立在这上面。新增 scope 时改那张表。

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

- `skills.include` 只收 glob，**不收目录**：写 `references` 不会打包，必须写 `references/*`。漏了不报错，只在沙箱里留一堆悬空链接，agent 会跑去找。SKILL.md 新增外部引用时必须同步这里。
- `run_shell` 的围栏在引擎里，不在 skill-up 里：`contain_violation()` 只放行工作区内路径（加 `/dev/null` 类白名单），挡 `..` 路径段与 `~`。第一轮没这道栅时，被测 agent 读到了 `evals/cases` 和 judge 脚本本身，那一轮结果作废。判分前先确认轨迹里没出现 skill 真身目录。
- 模型选型（实测踩过）：OpenRouter 中转模型会撞 HTTP 402（余额只够 8k tokens，引擎默认请求 65536）；workbuddy/opencode-zen 直连源被 429 全封；`nvidia/z-ai/glm-5.3-flash` 每步约 10 分钟，40 分钟超时只走了 4 步。目前可用且够快的是 `ollama-cloud/nemotron-3-ultra`（约 4s/步）和 `groq/qwen/qwen3.8-27b`（约 1s/步）。换模型前先拿一条带 tools 的小请求探延迟。

## 两个用例

| case | 验什么 |
| --- | --- |
| `empty-bootstrap` | 空仓库从零建五层：结构断言 + 五阶段留痕 |
| `harness-regression` | 已有 harness 改一条规则：改前基准、分批改、改后 `make check` 变绿、反向测试 |

判分一律用 `evals/fixtures/scripts/*.sh`（script judge），不用 agent judge——同一引擎自评没有信号。

## 维护

改 SKILL.md：前后都跑 `make check`（0 ERROR 才算改完）；正文改动后重跑评测；概念变了先改 `SKILL.md` 再改用例，别反过来。
改模板：先跑 `make check` 立基准，改完再跑，数字必须能解释——变了就是变了，不许「看起来还绿」。
