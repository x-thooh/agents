# harness-bootstrap

给一个 git 仓库搭建、移植、重做 `.harness` 工程层的抽象 skill。生成物布局以 `SKILL.md` §二.1 的
标准布局表为准——这里不抄第二份清单，抄出来的迟早和正文不一致。

- 正文：`SKILL.md`（每节只留判据：修改三段纪律、九条设计判据、六条原则、三个形状、五阶段、记忆树、断言坑、破坏性操作、验收、移植清单）
- 自身门禁：`scripts/audit.py` + `tests/fixtures/`——审本 SKILL.md（frontmatter / bash 围栏 / 交叉引用 / 相对链接 / 基线记账 / 版本保质期 / 宿主实测 / 双向对账 / 规范用语 / 调度器体征 / 目录形状 / 参考文件可达性（STRUCT003）/ 节与参考材料的 80/100 两档上限）+ references/*.md 里的跨文件 §X 引用（存在性），不依赖 git，不碰其他 skill；实现按 scope 分文件住 `scripts/scopes/`
- `references/`：**按需才读**的部分——判据的展开、失败态论证、笔记/归档/记忆树约定、额度与基线规格。
  入口只留判据与链接；`SECT002` 守住单个参考文件 ≤100 行（撞 80 记 WARN），所以它只能越拆越细，不能长成第二个手册

## 目录形状

标准四件照 skill 规范走，多出来的目录必须**声明理由**——没声明的目录会悄悄长成第二个入口，
下一个人不知道该读哪个。这条由 `STRUCT001` 判，不是靠自觉：

```text
harness-bootstrap/
├── SKILL.md          标准：入口与元数据（必需）
├── references/       标准：按需查的支撑文档，只放 .md，不建子目录（STRUCT002）
├── scripts/          标准：可执行代码（audit.py 调度 + report.py 输出 + cli.py 解析入口参数
│                     + hooks.py 每 scope 的 plan/reflect + round.py 一轮=一次提交的行为级对照
│                     + retro.py 复盘的事实底板（数字先算，AI 只许在数字上写）
│                     + scopes/ 一个 scope 一个文件
│                     + gen_code_index.py 生成清单 + check_strict.sh 判 strict）
├── agents/           标准：子 Agent 定义（本 skill 目前没有，不建空目录）
├── README.md         额外：维护者入口，给人看，不进 skill 上下文
├── Makefile          额外：统一命令入口（所有命令从 make 走）
├── tests/            额外：自身门禁的引擎（`fixtures.py`）+ 期望表（`cases.py`）+ 三道闸（`coverage.py`）+ 反向 fixture
└── templates/        额外：生成物模板（每套含 TEMPLATE.md 模板说明 + AGENTS.md 入口），拷进目标仓库用，不是参考文档
```

「额外」不是随便加的：每一个都在 `scripts/scopes/struct.py` 的 `EXTRAS` 里带一句理由。
`reference/`（单数）、`script/`、`agent/` 这类近似拼写一律按错报——名字一歪，谁也不知道该往哪找。

### 分发边界：这个目录会被整体链接到四个 agent

magpie 把本目录**整体软链**到 `~/.pi/agent/skills`、`~/.qoder/skills`、`~/.workbuddy-ai/skills`、
`~/.lmstudio/skills`。所以「提交什么」与「分发出去什么」不是同一件事：

| 目录 | 在 git 里 | 跟着软链分发 | 处理 |
| --- | --- | --- | --- |
| `.git/` | — | 是 | 已知污染：不在仓库内另写副本，接受它被看到 |
| `.idea/`、`.ruff_cache/`、`__pycache__/` | 否 | 是 | 同上；`.gitignore` 只防提交，防不了软链 |
| `.workbuddy-ai/` | 曾是 | 是 | **已移出**（存档在 `~/.agents/archive/`）：本地工作记忆不属于 skill 载荷 |

规矩一句话：**只为本机服务的目录，不进这个目录。** 工程层工作记忆、会话日志、临时笔记一律放在仓库之外——
`STRUCT001` 不再为 `.workbuddy-ai` 开豁免，它回来就会报错。

## 安装：拷贝就是安装

没有包管理器、没有版本号文件、没有 `install.sh`——这个 skill 的载荷是一个目录，装法就是把
目录放到宿主读得到的地方（或让 magpie 软链过去）。所以「怎么装」与「怎么升级」只有一条路径：

```bash
git clone <远端>/agents.git ~/.agents          # 首次
cd ~/.agents && git pull --ff-only             # 升级；本 skill 无运行时状态，回滚就是 git revert
```

边界写清楚，免得有人等一个不存在的安装器：

- **装的是目录，不是包**：拷走后没有相对外部的引用（`make check-all` 在副本里同样能跑通）。
- **升级靠 git**：不维护 `VERSION` 文件，仓库提交号就是版本；`SKILL.md` 的 `rules_version` 是
  规则集保质期，不是包版本。
- **许可**：[MIT](LICENSE)。没有许可声明时，默认是「保留所有权利」——拷贝给别人用需要授权，
  这正是本 skill 的使用方式，所以许可与正文同样算交付物。
- **不做的事**：不写目标仓库之外的路径、不联网取模板、不在安装时改宿主配置。

## 本仓库自己的门禁

这个仓库自己也是一份 harness——它管别人怎么建 harness，所以得先过自己的关。命令只从 `make` 走：

```bash
make check          # 核心：技能自审 + fixture 断言表 + 两套模板 verify + 两套反向测试
make check-all      # 全部：check + check-strict + check-boot + lint-python。**提交前与 CI 都跑这一条**
make check-strict   # 断言 --strict 能拦下模板自带的示例数据
make check-boot     # 把模板拷进临时空仓库，验它装上之后是否仍然诚实（行为层）
make check-sample   # 样例 Go 模块 vet + test（需要 Go 工具链）
make lint           # 工具层：golangci-lint（需要 Go 工具链）
make lint-python    # 工具层：ruff 检查全部 Python（需要 ruff，配置在 pyproject.toml）
make guide          # 重新生成两套 codebase-guide/index.json
```

两级不是为了宽松，是为了「改一行还能快跑」：`check` 秒级，`check-all` 多两条模板不变量。
但**提交前和 CI 必须是同一条**——否则「本地绿、CI 红」只是时间问题。

仓库根（`~/.agents`）的 `.github/workflows/verify.yml` 跑的是同一串命令，
每个 job 的 `working-directory` 指向本目录——workflow 只能在仓库根被 GitHub 读到。pre-commit 能被 `git commit --no-verify` 绕过，
CI 不能——这是 CI 唯一的职责。它**不新增断言**：目录齐不齐由模板的 `GATE00x` 判，
索引对不对由 `GUIDE001` 判；同一个断言写两处，就有两个地方会漂。CI 的两个 job 按依赖分：
`gate` 故意不装 Go（「verify 只做词法检查」这句话在那里被真实执行），`sample` 装 Go 跑
`check-sample` 与 `lint`。CI 的 `gate` job 跑 `make check-all`，与本地的提交前命令一致。

反向测试里有两处需要说清，否则下一个人会以为门禁在偷工：

- **`--dispatch`**：只为 LAYOUT001 存在，把「调度器」换成一份长成实现的源码去审合规样本。
- **`--link-status URL=CODE`**：只为 LINK002/LINK003 存在。公网链接的「4xx / 不可达」不可能靠真请求来判（那就是让门禁依赖网络抖动），不请求则这两条断言永不执行。所以把「取状态码」这一步做成可注入的，判定逻辑本身没绕过。值写错时报用法错误（退出码 2），不 traceback。

## 模板（`templates/`）

模板是「某个业务域的答案」，不是通用解。拷进目标仓库后按真实阈值与证据替换示例数据。
选型与共同骨架见 [`templates/README.md`](templates/README.md)。

| 目录 | 管什么 | 阶段 / scope |
| --- | --- | --- |
| `templates/delivery-harness/` | 交付流程：需求 → 方案 → 开发 → 联调 → 自测 → CR → 自洽 → 提测 | 8 / 9 |
| `templates/go-dev-harness/` | Golang 研发的日常：契约 → 设计 → 编码（形状/错误/并发）→ 测试 → 评审 → 发布 | 6 / 9 |

两者都自带 `tests/reverse.py`（每个 scope 至少一条违规样本，外加 `--fix` 的边界样本）、
`make check-strict`（示例数据判 ERROR）和 `make fix`（只修派生数据，前置条件按目标文件排除）。
每套还有一个 `TEMPLATE.md`：模板自己的说明，拷进目标仓库时**不改名成 README**（早期版本就该叫 `README.md`，
拷一次就把人家原来的覆盖了）。
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

期望清单只有一处——`tests/cases.py` 的 `CASES` 表，它跑在 `make check` 里。
README 和 `references/self-gates.md` 都不再抄第二份：抄出来的表迟早和第一份不一致，
而「表说这条规则有人守」的信用就建立在这上面。新增 scope 时改那张表。

audit.py 不判语义一致性（机器判不了）；语义项在 `SKILL.md` §六 的「判据」列标注为人判。

## 维护

改 SKILL.md：前后都跑 `make check-all`（0 ERROR 才算改完）；正文改动后按 §十 验收清单人工过一遍；概念变了先改 `SKILL.md` 再改用例，别反过来。
改模板：先跑 `make check` 立基准，改完再跑，数字必须能解释——变了就是变了，不许「看起来还绿」。
