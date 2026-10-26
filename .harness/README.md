# `~/.agents` 的 `.harness`

这是**这个仓库**的状态层，不是任何 skill 的载荷。

为什么放在仓库根、不放 skill 目录：设计记录（为什么这样设计、踩过什么坑）属于
**本机维护历史**——它解释的是「我为什么这么做」，不是「你拿去怎么用」。
`skills/harness-bootstrap/README.md` 的「分发边界」写着「只为本机服务的目录，不进这个目录」，
设计记录正好落在这一侧。曾经把它放进 skill 里，是错的，已移回（见 `memory/decisions.md` D-8）。

| 层 | 在这里是什么 |
| --- | --- |
| 入口 | `skills/harness-bootstrap/SKILL.md`（skill 规范，不是 `AGENTS.md`） |
| 流程 | `SKILL.md` §〇–§三（四段纪律） |
| 知识 | `skills/harness-bootstrap/references/` |
| 执行 | `skills/harness-bootstrap/scripts/audit.py` + `round.py` + `retro.py` |
| 状态 | 本目录 `memory/`；工单在 `archive/retro/tasks.json` |

**故意不建**：`deliverables/`（本仓库无阶段门）、`tasks/`（工单已在 `archive/retro/`，
不设第二个事实源）、`codebase-guide/`（代码索引是 `references/code-index.md`）、
`workflow/flow.json`（四段纪律是正文，不是状态机）、`scripts/verify.py`
（断言只有 `audit.py` 一套；复制一份就是「同一个断言写两处」）。
