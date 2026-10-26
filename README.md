# ~/.agents —— 自写技能的仓库（分发归 magpie）

> **从 GitHub 来的访客看这里**：这个仓库是某个人的 agent 技能中心，其他目录讲的是本机分发
> （magpie 软链到 `~/.pi`/`~/.qoder` 等）。你要找的如果是那个工程层 skill，直接进
> [`skills/harness-bootstrap/`](skills/harness-bootstrap/)——它自带 `README.md`（安装 = 拷目录）、
> `SKILL.md`（正文）、`templates/`（拷进目标仓库的两套模板）与 `make check-all`（自身门禁）。
> 许可：[MIT](skills/harness-bootstrap/LICENSE)。下面这些 `~/.agents` 的路径不必对上你的机器。

2026-10-22 起，分发权归 magpie，这里只剩「自写技能的真身 + magpie 不认识的 agent」。

## 这一层就是 git 仓库的根

`git remote` 指向 `github.com/x-thooh/agents`，仓库根 = `~/.agents`。技能是子目录，
不是独立仓库：`skills/<名>/` 里没有 `.git`（`harness-bootstrap` 曾经有，2026-10-26 已重写历史并入本仓库）。

- CI 在仓库根的 `.github/workflows/verify.yml`——GitHub 只读根目录那一个 `.github/`；
  它每个 job 带 `working-directory: skills/harness-bootstrap`，因为 `make` 的入口在技能里。
- `note-record-evals/` 是评测沙箱产物（33M），在 `.gitignore` 里：只留脚本，不留跑出来的东西。
- 各技能自己的门禁仍在技能目录内跑：`cd skills/harness-bootstrap && make check-all`。

## 两块地界

| 位置 | 放什么 |
| --- | --- |
| `~/.agents/skills/` | **自写**技能的真身：`ai-chat-import`、`goland-bookmarks`、`harness-bootstrap`、`magpie-model-sync`、`mr-review`、`note-record` |
| `~/.config/magpie/library/skills/` | **上游**技能的真身：`grill-me`、`diagram-design`（GitHub 源，跟着上游走） |

上游技能的仓库里**不放指针**——软链指来指去只会多一跳。

## 谁铺给谁

| agent | 分发者 | 技能目录 |
| --- | --- | --- |
| pi | `magpie library sync` | `~/.pi/agent/skills` |
| WorkBuddy | `magpie library sync` | `~/.workbuddy-ai/skills` |
| qoder | `magpie library sync` | `~/.qoder/skills` |
| lmstudio | `make link` | `~/.lmstudio/skills` |

lmstudio 单独一行是因为 **magpie 不认它**（`magpie ls` 只看到 pi/qoder/WorkBuddy）。哪天 magpie 支持了，把 `bin/skills.py` 里的 `SELF_AGENTS` 那条挪进 `MAGPIE_AGENTS` 就完事。

## 四条规矩

1. **自写技能的真身只在 `~/.agents/skills/`。** 各 agent 目录里除了软链，不放别的东西。2. **上游技能跟着 magpie 库走，不要往这里搬。** 已有：`grill-me`（登记在 `bin/skills.py` 的 `EXTERNAL`）。
3. **新增自写技能 = 丢进 `skills/` → magpie 登记 → 铺开。** CLI 装不了技能，只能用 app 的 Library 页；`make import` 会把四步提示打出来。
4. **脚本只删自己建的软链。** 判断依据是「指向 `~/.agents/skills/` 且仓库里已无同名技能」。指向 magpie 库的软链（`diagram-design`、`grill-me`）归 magpie 记账，一律不碰——所以 `make status` 会把它们单独列一行。

## 常用命令

```bash
make status                      # 四家对照表 + magpie 账本漂移检查
make link                        # 只铺 lmstudio（改完技能跑一次）
make check                       # 每个技能能否被加载（SKILL.md + frontmatter）
make import SRC=~/Downloads/foo  # 收进仓库，并打印 magpie 登记步骤
make unlink NAME=foo             # 解除共享，真身保留
```

改完技能在 magpie 那三家里的生效方式：

```bash
magpie library sync              # 或 magpie library skill how link|copy <agent>
```

## 为什么不把真身放进 magpie 库

把 `~/.agents/skills/` 整体搬进 `~/.config/magpie/library/skills/` 再删掉这个目录，看起来能省一层，实际不行：

- `magpie library skill rm --all` 会把库里的技能连同各 agent 的软链一键清空；
- GitHub 源技能的 `magpie library skill update --replace-edits` 会覆盖手改内容——`mr-review` 有 39K 的 `SKILL.md` 加 `scripts/`，`note-record` 有 `references/`，经不起这种覆盖；
- 那是 app 私有目录，真身进 magpie 的加密备份、不进你能直接 `ls`、`diff`、`git` 的地方。

所以分工是：**真身留在纯文本目录，分发交给 magpie。**

## 为什么 magpie 的 folder 源指向这里

`~/.config/magpie/library.json` 里四个技能的登记是这样的：

```json
{ "name": "mr-review", "source": { "kind": "folder",
  "dir": "/Users/thooh/.agents/skills/mr-review" }, "agents": ["pi","qoder","workbuddy-ai"] }
```

magpie 只是**引用**这个目录（软链过去），不复制、不接管。所以：

- 改 `~/.agents/skills/mr-review/` 里的文件是原地生效的，`magpie library sync` 只会重铺软链；
- **删掉 `~/.agents` 会让 magpie 库里这四个技能的源路径全断**——依赖方向是 magpie → `~/.agents`，不是反过来。

## 和项目级技能的关系

这里只管**全局**技能。项目级（例如 `~/Notes/.workbuddy-ai/skills/`，只对那个库可见）不归这里管，也不受影响——`make link` 不会碰它们，因为它们指向的不是 `~/.agents/skills/`。

## 历史

- 2026-10-22 之前：`make link` 无条件铺全部六家 agent，与 magpie 的 Library 机制重复。
- 2026-10-22：magpie 接管 pi / WorkBuddy / qoder（每个技能 `agents` 收到 `pi,qoder,workbuddy-ai`），`make link` 收窄到 lmstudio；`grill-me` 的两级软链拉直成单跳；`backup-20261022/` 迁移快照（与仓库内容逐字节相同）删除。
- 2026-10-22 晚：alma、omp 弃用——magpie 账本里摘掉，`~/.config/alma`、`~/.omp` 删除（app 早已不在，`magpie ls` 里的 Alma hidden / omp 重启 magpie 后消失）。
