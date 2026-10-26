# 本 skill 自己的 `.harness`

harness-bootstrap 管别人建 harness，它自己也该有一份——但**只到状态层**。

| 层 | 在这里是什么 | 为什么 |
| --- | --- | --- |
| 入口 | `../SKILL.md` | 它是 skill 规范，不是 `AGENTS.md`；再加一份入口就是两个事实源 |
| 流程 | `../SKILL.md` §〇–§三（四段纪律） | 流程正文只有一处 |
| 知识 | `../references/` | 参考材料已外置，不重复 |
| 执行 | `../scripts/audit.py` + `../scripts/{round,retro}.py` | **不在这里放 `verify.py`**：本 skill 的断言只有一套，复制一份就是「同一个断言写两处」，两份迟早对不上 |
| 状态 | 本目录 `memory/` | 设计决策与踩坑记忆 |

工单不在这里：它在 `../../../../archive/retro/tasks.json`（仓库根，本机维护历史、不随 skill 分发）。
按 `../README.md` 的「分发边界」——只为本机服务的目录不进 skill 载荷——而设计决策要跟着
skill 走：谁要改这套机制，得先知道自己站在什么取舍上。

所以这里**故意不是**标准十件套。缺的那些不是忘了，是这一层不需要：
`deliverables/`（本 skill 无阶段门）、`tasks/`（工单在外）、`codebase-guide/`（代码索引已是
`../references/code-index.md`）、`workflow/flow.json`（四段纪律是正文，不是状态机）。
`STRUCT001` 只为 `.harness` 开一条带理由的例外，不为这十件套开。
