# delivery-harness

> 本文件是**模板说明**，不是目标仓库的 README。拷进仓库时它叫 `TEMPLATE.md`，
> 就是为了不覆盖你原来的 `README.md`（早期版本叫 `README.md`，拷一次就把人家的覆盖了）。

交付流程 v1.2 的可执行门禁模板，布局是 `.harness/` 十件套。

- `AGENTS.md`：入口、命令、硬规则（每条带 scope 或「无断言」）、目录地图。
- `.harness/workflow/`：`flow.json`（阶段唯一事实源）、`transitions.json`（结果状态机）、
  `contract.json`（门记录字段与账本位置）、`README.md`（流程正文：RACI / 预期 / 执行 / 检查，在 `workflow/` 下）。
- `.harness/config.json`：阈值（覆盖率、任务人天、MR 行数、冒烟通过率）。
- `.harness/deliverables/`：`gates/` 门记录、`artifacts/` 证据、`ledgers/` 变更与例外、`reports/` 报告。
- `.harness/tasks/board.json`：任务看板；`.harness/memory/`：踩坑记忆与决策。
- `.harness/codebase-guide/index.json`：代码库索引，由 `scripts/gen_guide.py` 生成，禁手改。
- `.harness/scripts/`：`verify.py` 调度器（两套模板逐字节相同）+ `registry.py`（本套的 scope 清单）
  + 一组 scope（一个 scope 一个文件，见 `scopes/`）+ `gen_guide.py` + `check_commit.py`（提交消息：
  Conventional Commits + 一个提交一件事）+ `retro.py` / `retro_check.py` / `round.py`（复盘与环比）
  + `wt.py`（任务级 worktree：`new` / `finish` / `list`）。
- `.harness/git-hooks/pre-commit`：提交前跑 `make check`。
- `tests/reverse.py`：每个 scope 一条反向样本，验证真的会报 ERROR。

## 使用

把本目录内容复制到目标仓库根目录（或把 `.harness`、`AGENTS.md`、`Makefile` 合并过去），然后：

```bash
make init           # 装 pre-commit 钩子：提交前自动跑 check
make check          # 示例数据只产生 WARN；0 ERROR 即通过
make check-strict   # 示例数据按 ERROR 处理；替换真实证据后应变绿
make selftest       # 正向对照 + 11 个反向测试
```

当前 `.harness/deliverables/` 与 `.harness/tasks/`、`.harness/memory/` 里全部是示例数据
（证据带 `example: true`）。真实交付前逐项替换：

- `.harness/config.json` 的阈值如果团队不同，先改这里；
- `.harness/workflow/flow.json` 的阶段与交付物（改完同步门记录文件名）；
- `deliverables/gates/*.json` 的负责人、日期、证据 ID；
- `deliverables/artifacts/*.json` 的 PRD/任务/方案/覆盖率/联调/自测/CR/E2E/提测证据；
- `tasks/board.json` 的当前任务、`memory/lessons.md` 的真实踩坑；
- 最后跑 `python3 .harness/scripts/gen_guide.py` 刷新索引。

## 设计边界

- 机器判：产物存在、字段、阈值、状态、依赖、版本一致性、索引与磁盘一致。
- 人判：需求质量、方案合理性、代码质量、业务自洽、风险接受；见 `AGENTS.md` 的「人判项（无断言）」。
- 不连接 Jira/CI/测试平台：证据用 ID/链接记录；需要自动拉取时，在对应 scope 里加 adapter，
  不要把外部字段名兼职成第二个含义。
