# ~/.agents 命令入口。自写技能的真身在 skills/，分发归 magpie（lmstudio 除外）。
# 规矩：真身只在 skills/，各 agent 目录只放软链。脚本不复制、不覆盖实体。

PYTHON ?= python3
S      := $(HOME)/.agents/bin/skills.py

.DEFAULT_GOAL := help
.PHONY: help link status check import unlink

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

check: ## 校验每个技能能否被加载（SKILL.md + frontmatter）
	@$(PYTHON) $(S) check

import: ## 收编一个技能目录：make import SRC=/path/to/skill
	@test -n "$(SRC)" || { echo '用法: make import SRC=/path/to/skill'; exit 2; }
	@$(PYTHON) $(S) import "$(SRC)"

unlink: ## 解除共享（真身保留）：make unlink NAME=skill-name
	@test -n "$(NAME)" || { echo '用法: make unlink NAME=skill-name'; exit 2; }
	@$(PYTHON) $(S) unlink "$(NAME)"
