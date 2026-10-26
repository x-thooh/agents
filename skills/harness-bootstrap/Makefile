# harness-bootstrap 自身的统一命令入口。
#
# 规矩：所有脚本都从这里走，不记散命令。CI 与本地跑的是同一串命令——
# 两边一旦分叉，「本地绿、CI 红」就只是时间问题。
#
# 边界：check 不依赖 Go 工具链（verify 只做词法检查），
#       需要编译器的检查单独放 check-sample，且缺工具链时报错而不是静默跳过。
#       Python 静态检查（ruff）是 check-all 的一部分：本 skill 的自身门禁只审 SKILL.md
#       与派生物，审不到自己写的 Python——实测代价是同一段 if 被逐字写了两遍。

PY ?= python3
GO ?= go
TPL := templates
DELIVERY := $(TPL)/delivery-harness
GODEV := $(TPL)/go-dev-harness

.PHONY: help check check-all check-json check-skill fixtures check-templates check-boot selftest check-sample check-strict lint lint-python guide code-index

help:
	@echo "make check            核心门禁：技能自审 + fixture 断言表 + 两套模板 verify + 两套反向测试（不需要 Go）"
	@echo "make check-all        全部：check + check-strict + check-boot + lint-python（不需要 Go）。CI 跑的就是这一条"
	@echo "make check-json        只出三段 JSON：技能自审 + 两套模板（不含 fixtures/selftest/strict）"
	@echo "make check-skill       只跑 scripts/audit.py"
	@echo "make fixtures          全部反向 fixture 逐条比对期望的 code"
	@echo "make check-templates   只跑两套模板的 .harness/scripts/verify.py（自洽性）"
	@echo "make check-boot        把模板拷进临时空仓库，验它装上之后是否仍然诚实（行为）"
	@echo "make selftest          只跑两套 tests/reverse.py + 提交消息检查"
	@echo "make check-strict      断言 --strict 能拦下示例数据（模板自身的不变量）"
	@echo "make check-sample      样例 Go 模块 vet + test（需要 Go 工具链）"
	@echo "make lint              工具层：golangci-lint 跑样例模块（需要 Go 工具链）"
	@echo "make lint-python       工具层：ruff 检查全部 Python（需要 ruff；配置在 pyproject.toml）"
	@echo "make guide             重新生成两套 codebase-guide/index.json"
	@echo "make code-index        重新生成 references/code-index.md（全部 code 清单）"

# 两级：check 是跑得快的那一半，check-all 是全部门禁。
# 为什么不是「check 就是全部」：跑完一条改就要等 strict 的两个模板全量，
# 而 strict 验的是模板不变量，与本 skill 正文改动无关。分成两条，日常快、提交全。
# 但**两地跑的必须是同一条**：CI 用 check-all，你在本地提交前也用它。
check: check-skill fixtures check-templates selftest
	@echo "== check 通过：技能自审 + fixture 断言表 + 两套模板 + 两套反向测试 =="

round:
	@$(PY) scripts/round.py

retro:
	@$(PY) scripts/retro.py

retro-check:
	@$(PY) scripts/retro_check.py
	@$(PY) tests/retro_reverse.py

check-all: check check-strict check-boot lint-python retro-check
	@echo "== check-all 通过：以上 + strict 不变量 + 模板装上后的行为 + Python 静态检查 =="

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

# 行为层：文本 fixture 验不了「模板拷进真仓库后说什么」。
# 这一条就是那次假绿灯（strict 全绿而仓库代码里 panic 没被检查）的回归测试。
check-boot:
	@$(PY) tests/template_boot.py

selftest:
	@$(PY) $(DELIVERY)/tests/reverse.py
	@$(PY) $(GODEV)/tests/reverse.py
	@$(PY) $(GODEV)/tests/commit_msg.py
	@$(PY) $(DELIVERY)/tests/commit_msg.py

# Python 静态检查。为什么进 check-all 而不是「可选工具」：它抓到的是真缺陷
# （重复分支、未使用导入、漏了 check 的 subprocess、集合里的隐式拼接），
# 而不是文体偏好——不可选的检查才叫门禁。缺 ruff 时报错而不是静默跳过，
# 否则「本地没装」会静默退化成「没有这条门禁」。
# 规则集收窄在 pyproject.toml：select = ALL 会把中文标点算成 error，一千多条噪声
# 之后门禁就变成调规则。版本区间也写在那里，避免判定随 ruff 升级而漂移。
lint-python:
	@$(PY) -c 'import ruff' 2>/dev/null || python3 -m ruff --version >/dev/null 2>&1 || { \
	  echo "lint-python 需要 ruff：python3 -m pip install 'ruff>=0.17,<0.18'" >&2; exit 1; }
	@$(PY) -m ruff check .

# 工具层不在这里重写一遍：委托给模板自己的 lint 目标，
# go_src 从模板的 config.json 读，路径不写第二份。
lint:
	@command -v golangci-lint >/dev/null 2>&1 || { \
	  echo "lint 需要 golangci-lint：https://golangci-lint.run/welcome/install/" >&2; exit 1; }
	@$(MAKE) -s -C $(GODEV) lint

check-sample:
	@command -v $(GO) >/dev/null 2>&1 || { \
	  echo "check-sample 需要 Go 工具链：make check-sample GO=/abs/path/to/go" >&2; exit 1; }
	@cd $(GODEV)/sample && $(GO) vet ./...
	@cd $(GODEV)/sample && $(GO) test ./...
	@echo "== 样例模块 vet + test 通过 =="

# 模板里带 example: true 的示例证据，--strict 必须把它们判成 ERROR。
# 这条断言证明 strict 真的在生效；示例被换成真实数据后本目标会失败，提醒同步改这里。
# 判断本体在 scripts/check_strict.sh：Make 要把 $ 写成 $$，而 shellcheck 读的是
# Makefile 原文，`[ $$? -eq 1 ]` 会被它当成 PID 拼接（SC2255），先接变量又报 SC2034
# （「变量没用」）——绕标注不如把逻辑搬出 Make，顺带这段现在能单独跑。
check-strict:
	@bash scripts/check_strict.sh delivery-harness $(DELIVERY)/.harness/scripts/verify.py
	@bash scripts/check_strict.sh go-dev-harness $(GODEV)/.harness/scripts/verify.py

guide:
	@$(PY) $(DELIVERY)/.harness/scripts/gen_guide.py
	@$(PY) $(GODEV)/.harness/scripts/gen_guide.py

# 派生数据：清单只准脚本写。改完 scope 就跑一次，否则 codeindex scope 会报不一致。
code-index:
	@$(PY) scripts/gen_code_index.py
