# 任务看板

`board.json` 是活动任务的唯一入口：`stage` 必须能在 `workflow/flow.json` 里找到，
`status` 只能是 `todo` / `doing` / `blocked` / `done`。

- 一个任务一行，`id` 与 MR、门记录里的引用一致。
- `done` 的任务不删，保留到本迭代结束再归档（归档不是删除，是移到 `board.archive.json`）。
- 看板不是进度流水：只记「还没做完什么」，不记「今天做了什么」。
