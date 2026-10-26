# harness-bootstrap 自身的统一命令入口。
#
# 规矩：所有脚本都从这里走，不记散命令。CI 与本地跑的是同一串命令——
# 两边一旦分叉，「本地绿、CI 红」就只是时间问题。
#
# 边界：check 不依赖 Go 工具链（verify 只做词法检查），
#       需要编译器的检查单独放 check-sample，且缺工具链时报错而不是静默跳过。

PY ?= python3
GO ?= go
TPL := templates
DELIVERY := $(TPL)/delivery-harness
GODEV := $(TPL)/go-dev-harness

.PHONY: help check check-json check-skill fixtures check-templates selftest check-sample check-strict guide

help:
	@echo "make check            全部门禁：技能自审 + fixture 断言表 + 两套模板 + 两套反向测试（不需要 Go）"
	@echo "make check-json       同上，输出 JSON"
	@echo "make check-skill      只跑 scripts/audit.py"
	@echo "make fixtures         全部反向 fixture 逐条比对期望的 code"
	@echo "make check-templates  只跑两套模板的 .harness/scripts/verify.py"
	@echo "make selftest         只跑两套 tests/reverse.py"
	@echo "make check-sample     样例 Go 模块 vet + test（需要 Go 工具链）"
	@echo "make check-strict     断言 --strict 能拦下示例数据（模板自身的不变量）"
	@echo "make guide            重新生成两套 codebase-guide/index.json"

check: check-skill fixtures check-templates selftest
	@echo "== check 通过：技能自审 + fixture 断言表 + 两套模板 + 两套反向测试 =="

check-json:
	@$(PY) scripts/audit.py --json
	@$(PY) $(DELIVERY)/.harness/scripts/verify.py --json
	@$(PY) $(GODEV)/.harness/scripts/verify.py --json

check-skill:
	@$(PY) scripts/audit.py

fixtures:
	@$(PY) tests/fixtures.py

check-templates:
	@$(PY) $(DELIVERY)/.harness/scripts/verify.py
	@$(PY) $(GODEV)/.harness/scripts/verify.py

selftest:
	@$(PY) $(DELIVERY)/tests/reverse.py
	@$(PY) $(GODEV)/tests/reverse.py

check-sample:
	@command -v $(GO) >/dev/null 2>&1 || { \
	  echo "check-sample 需要 Go 工具链：make check-sample GO=/abs/path/to/go" >&2; exit 1; }
	@cd $(GODEV)/sample && $(GO) vet ./...
	@cd $(GODEV)/sample && $(GO) test ./...
	@echo "== 样例模块 vet + test 通过 =="

# 模板里带 example: true 的示例证据，--strict 必须把它们判成 ERROR。
# 这条断言证明 strict 真的在生效；示例被换成真实数据后本目标会失败，提醒同步改这里。
check-strict:
	@$(PY) $(DELIVERY)/.harness/scripts/verify.py --strict >/dev/null 2>&1; rc=$$?; \
	  if [ $$rc -eq 1 ]; then echo "  delivery-harness  --strict 拦下示例数据（预期）"; \
	  else echo "  delivery-harness --strict 期望退出码 1，实际 $$rc：example: true 被改掉，或 strict 失效" >&2; exit 1; fi
	@$(PY) $(GODEV)/.harness/scripts/verify.py --strict >/dev/null 2>&1; rc=$$?; \
	  if [ $$rc -eq 1 ]; then echo "  go-dev-harness    --strict 拦下示例数据（预期）"; \
	  else echo "  go-dev-harness --strict 期望退出码 1，实际 $$rc：example: true 被改掉，或 strict 失效" >&2; exit 1; fi

guide:
	@$(PY) $(DELIVERY)/.harness/scripts/gen_guide.py
	@$(PY) $(GODEV)/.harness/scripts/gen_guide.py
