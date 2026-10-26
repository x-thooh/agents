#!/usr/bin/env bash
# ==============================================================================
# scan-security.sh — MR diff 安全检查（对应「代码审查 Skill」SecurityChecker 子 Skill）
#
# 职责：扫描 diff 中的新增行，检测高危信号，输出分级提示供 Agent 人工判断。
# 定位：轻量前置扫描，不替代 AI 实质审查；只提示不阻断（exit 0 恒成立），
#       命中行让 Agent 核对，确认属实后按 P1/P2 写入审查结论。
#
# 覆盖：
#   1. HIGH  — 私钥块 / 真实样式密钥（AWS AKIA、长 token 赋值）
#   2. MEDIUM — 可疑密钥/口令赋值、危险命令（强制 push、删库、rm -rf /）
#   3. MEDIUM — 敏感文件新增（.env / *.pem / *.p12 / *.key 等）
#   4. 误报控制：example/mock/fake/test/your_ 等示例值跳过
#
# 用法:
#   scan-security.sh <diff-file> [--out <file>]
#   scan-security.sh /tmp/mr-feature_x.diff              # 输出到 stdout
#   scan-security.sh /tmp/mr-feature_x.diff --out /tmp/mr-x.security.txt
#   scan-security.sh --self-test                          # mock 数据自检（冒烟）
#
# 依赖: python3（扫描逻辑全部在 python3 内，避免 bash 正则与中文编码坑）
# ==============================================================================
set -uo pipefail

DIFF_FILE=""
OUT_FILE=""
SELF_TEST=0

while [ $# -gt 0 ]; do
	case "$1" in
	--out)
		OUT_FILE="$2"
		shift 2
		;;
	--self-test)
		SELF_TEST=1
		shift
		;;
	-h | --help)
		grep '^#' "$0" | sed 's/^# \{0,2\}//' | grep -v '^='
		exit 0
		;;
	-*)
		echo "未知参数: $1" >&2
		exit 1
		;;
	*)
		DIFF_FILE="$1"
		shift
		;;
	esac
done

if [ "${SELF_TEST}" = "1" ]; then
	DIFF_FILE="-"
elif [ -z "${DIFF_FILE}" ]; then
	echo "用法: $0 <diff-file> [--out <file>] | --self-test" >&2
	exit 1
fi

RESULT=$(
	python3 - "${DIFF_FILE}" <<'PYEOF'
import re
import sys

SELF_TEST = sys.argv[1] == "-"

def scan(diff: str):
    """扫描 diff 中新增行（以 + 开头且非 +++ 头），返回命中列表。"""
    hits = []
    for lineno, line in enumerate(diff.splitlines(), 1):
        if not line.startswith("+"):
            continue
        if line.startswith("+++"):
            continue
        content = line[1:].strip()
        if not content or content.startswith("#") or content.startswith("//"):
            continue
        # 误报过滤：示例/测试/mock 值
        if re.search(r"(example|mock|fake|dummy|your_|xxx|changeme|placeholder)", content, re.I):
            continue
        # ---- HIGH: 私钥块 / AWS AKIA ----
        if re.search(r"-----BEGIN [A-Z ]*PRIVATE KEY-----", content):
            hits.append((lineno, "HIGH", "私钥块", content))
            continue
        if re.search(r"AKIA[0-9A-Z]{16}", content):
            hits.append((lineno, "HIGH", "AWS AccessKey 样式", content))
            continue
        # ---- MEDIUM: 密钥/口令赋值（值长度 >= 12）----
        m = re.search(r"\b(access[_-]?key|secret[_-]?key|api[_-]?key|password|passwd|token|secret|credential)\b\s*[:=]\s*['\"]?([A-Za-z0-9_\-+/]{12,})", content, re.I)
        if m:
            if re.search(r"(sk-(test|example)|test(ing)?[-_]?(key|token)|your[-_]?(key|token))", content, re.I):
                continue
            hits.append((lineno, "MEDIUM", f"密钥赋值({m.group(1)})", content))
            continue
        # ---- MEDIUM: 危险命令（支持 shell 与 Go exec.Command 带引号写法）----
        if re.search(r"git\s+push.*--force|rm[^A-Za-z0-9]*-rf[^A-Za-z0-9]*/|DROP\s+(TABLE|DATABASE)\b|TRUNCATE\s+(TABLE|DATABASE)\b|chmod\s+777|sudo\s+rm\b", content, re.I):
            hits.append((lineno, "MEDIUM", "危险命令", content))
            continue
        # ---- MEDIUM: 敏感文件新增 ----
        if re.search(r"\.(env|pem|p12|pfx|key|keystore|jks|p8)\s*$", line, re.I):
            hits.append((lineno, "MEDIUM", "敏感文件新增", content))
            continue
    return hits

if SELF_TEST:
    mock = """diff --git a/app/order/service/internal/biz/x.go b/app/order/service/internal/biz/x.go
--- a/app/order/service/internal/biz/x.go
+++ b/app/order/service/internal/biz/x.go
@@ -1,6 +1,8 @@
 package biz
+
+const accessKey = "AKIA1234567890ABCDEF"
+
+func run() {
+  exec.Command("rm", "-rf", "/")
+}
+
+const privateKey = "-----BEGIN RSA PRIVATE KEY-----"
+
+const exampleToken = "sk-example-123456"
"""
    hits = scan(mock)
    kinds = [h[2] for h in hits]
    content_all = " ".join(h[3] for h in hits)
    assert any("AccessKey" in k for k in kinds), f"应命中 AKIA, got: {kinds}"
    assert any("私钥块" in k for k in kinds), f"应命中私钥, got: {kinds}"
    assert any("危险命令" in k for k in kinds), f"应命中危险命令, got: {kinds}"
    assert "exampleToken" not in content_all, f"example 不应命中: {kinds}"
    print(f"SELF-TEST OK: {len(hits)} hits -> {' '.join(kinds)}")
    sys.exit(0)

try:
    diff = open(sys.argv[1], encoding="utf-8", errors="replace").read()
except FileNotFoundError:
    print(f"diff 文件不存在: {sys.argv[1]}", file=sys.stderr)
    sys.exit(1)

hits = scan(diff)
if not hits:
    print("SECURITY SCAN: 未发现明显安全问题")
else:
    print(f"SECURITY SCAN: 发现 {len(hits)} 处可疑信号（供 Agent 人工核对，非自动结论）")
    print("级别 | 类型 | diff行 | 内容")
    print("---- | ---- | ---- | ----")
    for lineno, level, kind, content in hits:
        c = content if len(content) <= 100 else content[:97] + "..."
        print(f"{level} | {kind} | {lineno} | {c}")
PYEOF
)

if [ -n "${OUT_FILE}" ]; then
	echo "${RESULT}" >"${OUT_FILE}"
	echo "security: ${OUT_FILE}"
else
	echo "${RESULT}"
fi
