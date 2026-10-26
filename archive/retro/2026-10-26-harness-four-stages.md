# 2026-10-26 四阶段改造复盘

> 数字由 `make retro` 算出（audit 0 ERROR / 0 WARN、fixtures 59 条 PASS、round 0 → 0）。
> 下面每一条结论都挂在那些数字或提交记录上。

## 现象

这一轮把「修改三段纪律」改造成 感知 / 规划 / 行动 / 反思 四章，并给四段补了文本级与行为级断言。
改造过程中，**新加的断言反复抓到我自己的新代码**：

- `DLV001` 三次：`hooks.py`、`round.py`、`retro.py`——每个新交付物第一次出现都没被文档点名
- `LINK004` 一次：迁移的 32 处锚点，小节漏 `N. ` 前缀、章节漏章节号，全部指错
- `DOC001` 一次：`LOOP001`–`LOOP004` 进了代码没进对照表
- `CODEINDEX001` 一次：`hooks.py` 里作为数据列出的 code 被当成声明
- `STRUCT003` 一次：新增 `references/` 文件没人链
- `BUDGET001` 四次：reformat 把 `audit.py` / `links.py` / `deliverable.py` 顶过 150 行
- `LOOP004` 一次：`hooks.py` 生成时把单元素元组写成 `("SCOPE001")`（字符串，`set()` 拆成字符）

## 根因

**加断言的人最容易忘的是「新东西也要被旧断言覆盖」。** 每次新增一个交付物（`hooks.py`、
`round.py`、`retro.py`），我都在写机制本身，而没有同时更新「谁点名它」——`DLV001` 三次全中，
说明这不是偶然，是这类工作的默认失效模式。

`LINK004` 那次更值得记：**断言存在 ≠ 断言覆盖到**。锚点校验写进 `links` 之后，
`check_relative_links` 拿的仍是 `ctx["text"]`（只有 SKILL.md 一个文件），
32 处 references 锚点当时**一条都没被查**，而门禁全绿。

## 断言

- 新交付物 → 立刻跑 `python3 scripts/audit.py`，`DLV001` 会点名（三次都是它抓的）
- 新断言 → 先想「它读的是哪些文件」，再想「它判什么」。`ctx["text"]` 只有一个文件这件事，
  在写第二个消费方（references）时就该发现
- 加机制的同时更新文档三边：`acceptance.md`（载体）/ 自身 `Makefile` 与 `README`（入口）/ 断言表

## 拦到：DLV001×3、LINK004×1、DOC001×1、CODEINDEX001×1、STRUCT003×1、BUDGET001×4、LOOP004×1

## 工单：R-1

本 skill 自己没有 `tasks/board.json`（故工单改记在 `archive/retro/tasks.json`）（那是它生成给目标仓库的），所以工单栏填不了结构化 id。
这是 `origin=reflect` 机制在本仓库**落不了地**的那一格——若要落地，需要给 ~/.agents 也建一个看板，
或在复盘里改用自由文本待办。此处如实记下，不假装有工单。
