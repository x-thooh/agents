.PHONY: init check check-json check-strict selftest

init:
	@git config core.hooksPath .harness/git-hooks
	@chmod +x .harness/git-hooks/pre-commit
	@echo "pre-commit 已装：core.hooksPath=.harness/git-hooks"

check:
	@python3 .harness/scripts/verify.py

check-json:
	@python3 .harness/scripts/verify.py --json

check-strict:
	@python3 .harness/scripts/verify.py --strict

selftest:
	@python3 tests/reverse.py
