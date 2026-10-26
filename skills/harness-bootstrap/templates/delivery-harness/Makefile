.PHONY: init check check-json check-strict fix selftest

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
