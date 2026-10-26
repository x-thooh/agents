#!/usr/bin/env bash
# ==============================================================================
# smoke.sh — mr-review skill 冒烟测试（对应「Skill 测试调试」单测/Mock 思想）
#
# 用 mock 环境变量验证核心脚本关键路径，不触碰真实外部依赖（Codeup/钉钉）。
# 覆盖：
#   1. 语法检查（bash -n）
#   2. send-dingtalk.sh --check：关键词命中 / 关键词缺失 / 缺内容 三条路径
#   3. review-mr.sh 参数解析：--no-tests --no-codegen 快速路径可达（不真实跑）
#   4. sync-codeup-comment.sh --draft 缺参数时给出明确错误而非静默
#   5. get-mr-author.sh：@ 对象（MR 发起人）解析自检 + 缺 token 保护 + 未知参数保护
#
# 用法:
#   bash scripts/tests/smoke.sh
#   bash scripts/tests/smoke.sh -v      # verbose
# ==============================================================================
set -uo pipefail

# macOS 默认没有 coreutils 的 timeout：有则用，无则直接跑（避免 127 假失败）
_to() { # <秒> <命令...>
	local secs="$1"
	shift
	if command -v timeout >/dev/null 2>&1; then
		timeout "$secs" "$@"
	elif command -v gtimeout >/dev/null 2>&1; then
		gtimeout "$secs" "$@"
	else
		"$@"
	fi
}

SCRIPT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
PASS=0
FAIL=0
VERBOSE=0
[[ "${1:-}" == "-v" ]] && VERBOSE=1

ok() {
	PASS=$((PASS + 1))
	[[ $VERBOSE -eq 1 ]] && echo "  ✅ $1"
}
bad() {
	FAIL=$((FAIL + 1))
	echo "  ❌ $1"
}

# mock webhook：含 secret= 的是加签模式，不含的是关键词模式
MOCK_KEYWORD_WEBHOOK="https://oapi.dingtalk.com/robot/send?access_token=mock_token_for_smoke_test"
MOCK_SIGN_WEBHOOK="${MOCK_KEYWORD_WEBHOOK}&secret=mock_secret_for_smoke_test"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

echo "== 1. 语法检查 =="
if bash -n "$SCRIPT_DIR"/scripts/*.sh "$SCRIPT_DIR"/scripts/lib/*.sh 2>/dev/null; then
	ok "scripts/*.sh + lib/*.sh bash -n 通过"
else
	bad "bash -n 失败"
fi

echo "== 2. send-dingtalk.sh --check =="
# 2a. 关键词模式 + 消息含关键词 → 应 exit 0
if DINGTALK_WEBHOOK_UR="$MOCK_KEYWORD_WEBHOOK" bash "$SCRIPT_DIR/scripts/send-dingtalk.sh" \
	--keyword 提测 --title t --content "提测冒烟" --check >/dev/null 2>&1; then
	ok "关键词模式+含关键词 → exit 0"
else
	bad "关键词模式+含关键词 应 exit 0"
fi

# 2b. 关键词模式 + 消息缺关键词 → 应非零退出
if DINGTALK_WEBHOOK_UR="$MOCK_KEYWORD_WEBHOOK" bash "$SCRIPT_DIR/scripts/send-dingtalk.sh" \
	--keyword 提测 --title t --content "没有关键词的消息" --check >/dev/null 2>&1; then
	bad "缺关键词应失败（exit != 0）"
else
	ok "关键词缺失 → 非零退出（errcode 310000 预判）"
fi

# 2c. 缺消息内容 → 应非零退出
if DINGTALK_WEBHOOK_UR="$MOCK_KEYWORD_WEBHOOK" bash "$SCRIPT_DIR/scripts/send-dingtalk.sh" \
	--keyword 提测 --check >/dev/null 2>&1; then
	bad "缺内容应失败（exit != 0）"
else
	ok "缺内容 → 非零退出"
fi

# 2d. 加签模式（URL 含 secret=）→ 跳过关键词校验，应 exit 0（即使内容无关键词）
if DINGTALK_WEBHOOK_UR="$MOCK_SIGN_WEBHOOK" bash "$SCRIPT_DIR/scripts/send-dingtalk.sh" \
	--content "无关键词也通过" --check >/dev/null 2>&1; then
	ok "加签模式 → 跳过关键词校验，exit 0"
else
	bad "加签模式应 exit 0"
fi

echo "== 3. sync-codeup-comment.sh 缺参保护 =="
# 【重要】必须 env -u YUNXIAO_ACCESS_TOKEN：本机常已导出 token，若不禁用，脚本会真的解析出 MR
# 并 POST 一条真实评论（曾经发生——冒烟测试不得具有外部副作用）。
# 再叠 --draft 作为第二道保险（即便漏传 token 也不会发布为正式评论）。
if _to 10 env -u YUNXIAO_ACCESS_TOKEN bash "$SCRIPT_DIR/scripts/sync-codeup-comment.sh" \
	--comment "x" --draft >/dev/null 2>&1; then
	bad "缺 token 应失败"
else
	ok "缺 token → 非零退出（不静默、无外部副作用）"
fi

echo "== 4. scan-security.sh 自检（SecurityChecker） =="
# 4a. --self-test：mock 数据应命中 AKIA/私钥/危险命令，且跳过 example 误报
if bash "$SCRIPT_DIR/scripts/scan-security.sh" --self-test >/dev/null 2>&1; then
	ok "scan-security --self-test 通过（命中 3 类信号 + 误报过滤）"
else
	bad "scan-security --self-test 失败"
fi

# 4b. 无命中 diff → 输出未发现且 exit 0
CLEAN_DIFF=$(mktemp)
printf 'diff --git a/x b/x\n+++ b/x\n+const ok = 1\n' >"$CLEAN_DIFF"
if bash "$SCRIPT_DIR/scripts/scan-security.sh" "$CLEAN_DIFF" 2>/dev/null | grep -q "未发现"; then
	ok "scan-security 无命中 → 输出未发现"
else
	bad "scan-security 无命中应输出未发现"
fi
rm -f "$CLEAN_DIFF"

echo "== 5. get-mr-author.sh（钉钉 @ 对象 = MR 发起人） =="
# 5a. --self-test：映射优先级 / username 形态提取 / 邮箱不误抓 / --at 覆盖
if bash "$SCRIPT_DIR/scripts/get-mr-author.sh" --self-test >/dev/null 2>&1; then
	ok "get-mr-author --self-test 通过（7 条断言）"
else
	bad "get-mr-author --self-test 应通过"
fi

# 5b. 缺 YUNXIAO_ACCESS_TOKEN → 应给出明确错误且不 hang
GMA_ERR=$(_to 10 env -u YUNXIAO_ACCESS_TOKEN bash "$SCRIPT_DIR/scripts/get-mr-author.sh" \
	--local-id 91 --repo-id 7289138 2>&1) && GMA_RC=0 || GMA_RC=$?
if [[ $GMA_RC -ne 0 && "$GMA_ERR" == *YUNXIAO_ACCESS_TOKEN* ]]; then
	ok "缺 token → 非零退出且提示变量名（不静默、不 hang）"
else
	bad "缺 token 应非零退出且提示 YUNXIAO_ACCESS_TOKEN（rc=${GMA_RC}）"
fi

# 5c. 未知参数 → 应非零退出（die 而非忽略）
if bash "$SCRIPT_DIR/scripts/get-mr-author.sh" --no-such-flag >/dev/null 2>&1; then
	bad "未知参数应非零退出"
else
	ok "未知参数 → 非零退出"
fi

echo "== 6. merge-to-test.sh（提测合并）自检 =="
# 【重要】全部走「不触网、不写远端」的路径：--help / 缺 token / 未知参数。
# 6a. --help 无需凭据也能看用法（token 校验在参数解析之后）
if env -u YUNXIAO_ACCESS_TOKEN bash "$SCRIPT_DIR/scripts/merge-to-test.sh" --help 2>/dev/null | grep -q "提测分支"; then
	ok "merge-to-test.sh --help 无需 token 可达"
else
	bad "merge-to-test.sh --help 应输出用法且不要求 token"
fi

# 6b. 缺 YUNXIAO_ACCESS_TOKEN → 明确报错、非零退出、不 hang
MTT_ERR=$(_to 10 env -u YUNXIAO_ACCESS_TOKEN bash "$SCRIPT_DIR/scripts/merge-to-test.sh" \
	--source master --dry-run 2>&1) && MTT_RC=0 || MTT_RC=$?
if [[ $MTT_RC -ne 0 && "$MTT_ERR" == *YUNXIAO_ACCESS_TOKEN* ]]; then
	ok "缺 token → 非零退出且提示变量名"
else
	bad "缺 token 应非零退出且提示 YUNXIAO_ACCESS_TOKEN（rc=${MTT_RC}）"
fi

# 6c. 未知参数 → 非零退出
if bash "$SCRIPT_DIR/scripts/merge-to-test.sh" --no-such-flag >/dev/null 2>&1; then
	bad "未知参数应非零退出"
else
	ok "未知参数 → 非零退出"
fi

echo ""
echo "结果: ${PASS} passed, ${FAIL} failed"
[[ $FAIL -eq 0 ]] || exit 1
