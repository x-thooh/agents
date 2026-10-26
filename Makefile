# ~/.agents 命令入口。自写技能的真身在 skills/，分发归 magpie（lmstudio 除外）。
# 规矩：真身只在 skills/，各 agent 目录只放软链。脚本不复制、不覆盖实体。

PYTHON ?= python3
S      := $(HOME)/.agents/bin/skills.py
# 跨技能审查只用「通用子集」：判的是任何 skill 都该满足的事（frontmatter 合规、
# 围栏 bash 真能跑、相对链接存在、§X 引用存在）。`sections`/`budget`/`struct`/
# `baseline` 这些判的是**本仓库的约定**，拿它们审别人 = 拿别人家规则审（README 有说明）。
AUDIT   := $(PYTHON) skills/harness-bootstrap/scripts/audit.py
GENERIC := frontmatter,bash,links,xref,xrefdoc

.DEFAULT_GOAL := help
.PHONY: help link status check audit-skills import unlink

help: ## 列出所有目标
	@echo "自写技能仓库：$(HOME)/.agents/skills"
	@echo "分发：magpie library sync（pi/workbuddy/qoder）+ make link（lmstudio）"
	@echo ""
	@awk 'BEGIN {FS = ":.*## "}; /^[a-z][a-z0-9-]*:.*## / {printf "  %-10s %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo ""
	@echo "示例："
	@echo "  make status                      谁链了哪些技能 + magpie 账本漂移"
	@echo "  make import SRC=~/Downloads/foo  把一个技能目录收进仓库并铺开"

link: ## 铺 lmstudio（magpie 不认它）；五家 magpie 自己铺
	@$(PYTHON) $(S) link

status: ## 对照表：每个技能在各 agent 里的状态 + 漂移检查
	@$(PYTHON) $(S) status

check: audit-skills ## 校验每个技能：能否被加载 + 通用子集审查
	@$(PYTHON) $(S) check

audit-skills: ## 用通用子集审每个技能（真缺陷级：frontmatter / 围栏可跑 / 链接 / §引用）
	@fail=0; for d in skills/*/; do \
	  n=$$(basename "$$d"); \
	  if out=$$($(AUDIT) --skill-dir "$$d" --only $(GENERIC) 2>&1); then \
	    echo "PASS $$n"; \
	  else \
	    echo "FAIL $$n"; echo "$$out" | grep -E '^(ERROR|WARN)' | sed 's/^/    /'; fail=1; \
	  fi; \
	done; \
	if [ $$fail -ne 0 ]; then echo "audit-skills: 有技能未通过通用子集" >&2; exit 1; fi; \
	echo "== audit-skills 通过：$(words $(wildcard skills/*/)) 个技能 =="

import: ## 收编一个技能目录：make import SRC=/path/to/skill
	@test -n "$(SRC)" || { echo '用法: make import SRC=/path/to/skill'; exit 2; }
	@$(PYTHON) $(S) import "$(SRC)"

unlink: ## 解除共享（真身保留）：make unlink NAME=skill-name
	@test -n "$(NAME)" || { echo '用法: make unlink NAME=skill-name'; exit 2; }
	@$(PYTHON) $(S) unlink "$(NAME)"
