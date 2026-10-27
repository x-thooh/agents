.PHONY: init check check-json check-strict fix selftest retro retro-check round task-new task-done task-list

init:
	@git config core.hooksPath .harness/git-hooks
	@chmod +x .harness/git-hooks/*
	@echo "钩子已装：core.hooksPath=.harness/git-hooks（pre-commit + commit-msg）"

check:
	@python3 .harness/scripts/verify.py

check-json:
	@python3 .harness/scripts/verify.py --json

check-strict:
	@python3 .harness/scripts/verify.py --strict

fix:
	@python3 .harness/scripts/verify.py --fix

selftest:
	@python3 tests/reverse.py
	@python3 tests/commit_msg.py


# 复盘三件：事实底板 → 复盘正文校验 → 行为级环比。判据与理由见 SKILL 的「复盘」一节。
retro:
	@python3 .harness/scripts/retro.py

retro-check:
	@python3 .harness/scripts/retro_check.py

round:
	@python3 .harness/scripts/round.py

# 任务级隔离：一个任务一棵树。开工建树、收尾提交并删树——判据在 .harness/scripts/wt.py，
# 状态对不上由 worktree scope 报（WT001 任务完了还留着树 / WT002 树开了任务还是 todo）。
task-new:
	@test -n "$(TASK)" || { echo '用法: make task-new TASK=T-143' >&2; exit 2; }
	@python3 .harness/scripts/wt.py new $(TASK)

task-done:
	@test -n "$(TASK)" || { echo '用法: make task-done TASK=T-143' >&2; exit 2; }
	@python3 .harness/scripts/wt.py finish $(TASK)

task-list:
	@python3 .harness/scripts/wt.py list
