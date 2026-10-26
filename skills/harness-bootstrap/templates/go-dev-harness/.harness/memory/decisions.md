# 决策记录（全仓级）

只放 `scope: *` 的决策。模块级决策进 `.harness/specs/`，用 `scope` 字段标归属——
不另建第二套目录树。每条带 `written_by`（哪次会话/哪个提交）、`version`、`supersedes`、`status`。
作废不删：`status: superseded` 保留痕迹，因为「当初为什么这么定」是这层唯一的存在理由。

## D-1 生成物统一到 `.harness/`

- 决策：模板与目标仓库的工程层统一为 `.harness/` 十件套（scripts / workflow / specs /
  deliverables / tasks / memory / codebase-guide / stack-templates / git-hooks / config.json）。
- 为什么：五层分目录把流程、知识、执行、状态拆成四处，跨目录找东西成本高；十件套按用途平铺。
- 代价：层间单向引用失去位置约束，改由断言守（`AGENTS.md` 规则 ↔ scope 对照）。
- written_by: session 2026-10-26 / version: 2 / supersedes: D-0（`.agents/` 五层布局）/ status: active

## D-2 覆盖率统计范围是 `./internal/...`

- 决策：总覆盖率只算 `internal/`，`cmd/` 不计；`core` 取承载业务规则的包。
- 为什么：把只做装配的 `cmd/` 计入总数，会让「入口要薄」这条规则反过来惩罚薄入口。
- written_by: session 2026-10-26 / version: 1 / supersedes: — / status: active
