.PHONY: init init-lefthook check check-json check-strict fix build vet test race evidence lint selftest retro retro-check round task-new task-done task-list

PY ?= python3
GO ?= go
GO_SRC := $(shell $(PY) -c 'import json; print(json.load(open(".harness/config.json"))["go_src"])')

# 原生钩子：core.hooksPath 指到 .harness/git-hooks，git 直接调那两个脚本。
init:
	@git config core.hooksPath .harness/git-hooks
	@chmod +x .harness/git-hooks/*
	@echo "钩子已装：core.hooksPath=.harness/git-hooks（pre-commit + commit-msg）"
	@test ! -f lefthook.yml || echo "注意：lefthook.yml 在，core.hooksPath 会让 lefthook 的钩子失效——两套只留一套" >&2

# lefthook 钩子：先摘掉 core.hooksPath，否则 git 只看那个目录，lefthook 的转发脚本永远不会被调用。
init-lefthook:
	@command -v lefthook >/dev/null 2>&1 || { \
	  echo "init-lefthook 需要 lefthook：https://lefthook.dev/installation/" >&2; exit 1; }
	@git config --unset core.hooksPath 2>/dev/null || true
	@lefthook install

check:
	@python3 .harness/scripts/verify.py

check-json:
	@python3 .harness/scripts/verify.py --json

check-strict:
	@python3 .harness/scripts/verify.py --strict

fix:
	@python3 .harness/scripts/verify.py --fix

# 构建/测试层：需要 Go 工具链。它们不进 make check（check 仍只读 JSON）。
build:
	@command -v $(GO) >/dev/null 2>&1 || { echo "build 需要 Go 工具链" >&2; exit 1; }
	@cd "$(GO_SRC)" && $(GO) build ./...

vet:
	@command -v $(GO) >/dev/null 2>&1 || { echo "vet 需要 Go 工具链" >&2; exit 1; }
	@cd "$(GO_SRC)" && $(GO) vet ./...

test:
	@command -v $(GO) >/dev/null 2>&1 || { echo "test 需要 Go 工具链" >&2; exit 1; }
	@cd "$(GO_SRC)" && $(GO) test ./...

race:
	@command -v $(GO) >/dev/null 2>&1 || { echo "race 需要 Go 工具链" >&2; exit 1; }
	@cd "$(GO_SRC)" && $(GO) test -race ./...

# 产证据：跑真实命令，全部 exit 0 才写 impl.json / test.json。
evidence:
	@$(PY) .harness/scripts/evidence.py

# 工具层：需要 golangci-lint（可选）。跑在 config.json 的 go_src 上，路径不写第二份。
lint:
	@command -v golangci-lint >/dev/null 2>&1 || { \
	  echo "lint 需要 golangci-lint：https://golangci-lint.run/welcome/install/" >&2; exit 1; }
	@cd "$(GO_SRC)" && golangci-lint run ./...

# 自测：断言本身也要有反向测试，否则「全绿」可能只是断言没跑。
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
