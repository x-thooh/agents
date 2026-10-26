#!/usr/bin/env bash
set -euo pipefail

# ============================================================================
# send-dingtalk.sh — 发送钉钉群机器人通知（markdown / text）
#
# 供 mr-review skill 审查结论同步后通知团队使用，也可独立调用。
#
# 依赖:
#   - python3（构造 UTF-8 payload —— 重要：bash 内联中文 payload 会编码异常，
#     导致关键词模式机器人的关键词匹配失败，必须经 python3 json.dumps 编码）
#   - curl（仅 fallback 路径使用）
#   - 环境变量 DINGTALK_WEBHOOK_UR 或 DINGTALK_WEBHOOK_URL（优先 URL，回退 UR；
#     注意本仓库环境变量拼写是 DINGTALK_WEBHOOK_UR，少一个 L）
#
# 用法:
#   send-dingtalk.sh --title "MR #16 审查" --content "markdown 文本"
#   send-dingtalk.sh --title "MR #16 审查" --file /tmp/review.md
#   send-dingtalk.sh --text "纯文本消息"
#   send-dingtalk.sh --keyword 提测 --title "..." --file ...   # 发送前校验消息含关键词
#   send-dingtalk.sh --webhook https://oapi.dingtalk.com/robot/send?access_token=... --title ... --content ...
#   send-dingtalk.sh --at 15708432566 --title "..." --file ...   # @ 指定成员（手机号，逗号分隔多个；正文需含 @手机号 文本）
#   send-dingtalk.sh --check     # 只打印 webhook 模式与关键词校验结果，不发送
#
# 钉钉机器人安全模式（由 URL 判断）:
#   - URL 含 secret= 参数 → 加签模式：自动计算 timestamp + HMAC-SHA256 签名
#   - 否则 → 自定义关键词模式：消息必须包含管理员配置的关键词，
#     否则返回 errcode 310000（关键词不匹配）。未知关键词先问用户，勿盲目试词。
# ============================================================================

# ---------- 参数解析 ----------
TITLE=""
CONTENT=""
TEXT=""
FILE=""
KEYWORD=""
WEBHOOK=""
AT_MOBILES=""
CHECK_ONLY=false

while [[ $# -gt 0 ]]; do
	case "$1" in
	--title)
		TITLE="${2:-}"
		shift 2
		;;
	--content)
		CONTENT="${2:-}"
		shift 2
		;;
	--text)
		TEXT="${2:-}"
		shift 2
		;;
	--file)
		FILE="${2:-}"
		shift 2
		;;
	--keyword)
		KEYWORD="${2:-}"
		shift 2
		;;
	--webhook)
		WEBHOOK="${2:-}"
		shift 2
		;;
	--at)
		AT_MOBILES="${2:-}"
		shift 2
		;;
	--check)
		CHECK_ONLY=true
		shift
		;;
	-h | --help)
		sed -n '2,30p' "$0" | sed 's/^# \{0,1\}//'
		exit 0
		;;
	*)
		echo "错误：未知参数 $1" >&2
		exit 2
		;;
	esac
done

# ---------- webhook 探测 ----------
if [[ -z "$WEBHOOK" ]]; then
	# 优先正确拼写 DINGTALK_WEBHOOK_URL，回退本仓库实际的 DINGTALK_WEBHOOK_UR
	WEBHOOK="${DINGTALK_WEBHOOK_URL:-${DINGTALK_WEBHOOK_UR:-}}"
fi
if [[ -z "$WEBHOOK" ]]; then
	echo "错误：未找到钉钉 webhook。请设置 DINGTALK_WEBHOOK_URL / DINGTALK_WEBHOOK_UR，或 --webhook 指定。" >&2
	exit 2
fi
# 不泄露完整 webhook 到日志
echo "webhook: $(echo "$WEBHOOK" | sed -E 's#(https?://[^/]+).*#\1/...（已隐藏 token）#')"

# ---------- 输入源解析 ----------
if [[ -n "$FILE" ]]; then
	if [[ ! -f "$FILE" ]]; then
		echo "错误：文件不存在 $FILE" >&2
		exit 2
	fi
	CONTENT="$(cat "$FILE")"
fi
if [[ -n "$TEXT" && -z "$TITLE" ]]; then
	# text 类型：title 非必填；content 就是 text
	CONTENT="$TEXT"
fi
if [[ -z "$CONTENT" ]]; then
	echo "错误：缺少消息内容。用 --content / --file / --text 提供。" >&2
	exit 2
fi

# ---------- 关键词校验（关键词模式才有意义） ----------
MODE="keyword"
if echo "$WEBHOOK" | grep -q 'secret='; then
	MODE="sign"
fi
echo "安全模式: ${MODE}（$([[ "$MODE" == "sign" ]] && echo "加签，无需关键词" || echo "自定义关键词，消息必须含关键词")）"

if [[ "$MODE" == "keyword" && -n "$KEYWORD" ]]; then
	if ! printf '%s' "$CONTENT" | grep -qF "$KEYWORD"; then
		echo "错误：消息不包含机器人关键词「${KEYWORD}」，发送必然失败（errcode 310000）。请在内容中加上关键词后重试。" >&2
		[[ "$CHECK_ONLY" == true ]] && exit 1 || exit 2
	fi
	echo "关键词校验: ✅ 消息包含「${KEYWORD}」"
fi

if [[ "$CHECK_ONLY" == true ]]; then
	exit 0
fi

# ---------- 发送（python3 构造 UTF-8 payload） ----------
# 环境变量传参给 python3，避免命令行内联中文编码问题
DT_WEBHOOK="$WEBHOOK"
DT_TITLE="$TITLE"
DT_CONTENT="$CONTENT"
DT_IS_TEXT="$([[ -n "$TEXT" && -z "$TITLE" ]] && echo 1 || echo 0)"
DT_AT_MOBILES="$AT_MOBILES"
export DT_WEBHOOK DT_TITLE DT_CONTENT DT_IS_TEXT DT_AT_MOBILES

python3 - <<'PY'
import base64, hashlib, hmac, json, os, sys, time, urllib.parse, urllib.request

url = os.environ["DT_WEBHOOK"]
title = os.environ.get("DT_TITLE", "")
content = os.environ["DT_CONTENT"]
is_text = os.environ.get("DT_IS_TEXT", "0") == "1"
at_mobiles = [m.strip() for m in os.environ.get("DT_AT_MOBILES", "").split(",") if m.strip()]

# 加签模式：URL 带 secret= 时，附加 timestamp + sign
parsed = urllib.parse.urlparse(url)
query = dict(urllib.parse.parse_qsl(parsed.query))
if "secret" in query:
    secret = query.pop("secret")
    ts = str(round(time.time() * 1000))
    string_to_sign = f"{ts}\n{secret}"
    digest = hmac.new(secret.encode("utf-8"), string_to_sign.encode("utf-8"), digestmod=hashlib.sha256).digest()
    query["timestamp"] = ts
    query["sign"] = urllib.parse.quote_plus(base64.b64encode(digest))
    url = urllib.parse.urlunparse(parsed._replace(query=urllib.parse.urlencode(query)))

if is_text:
    payload = {"msgtype": "text", "text": {"content": content}}
else:
    payload = {"msgtype": "markdown", "markdown": {"title": title or "通知", "text": content}}
if at_mobiles:
    payload["at"] = {"atMobiles": at_mobiles, "isAtAll": False}

req = urllib.request.Request(
    url,
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json"},
)
try:
    resp = json.loads(urllib.request.urlopen(req, timeout=10).read().decode("utf-8"))
except Exception as e:  # noqa: BLE001
    print(f"DINGTALK_SEND_FAIL 网络/HTTP异常: {e}", file=sys.stderr)
    sys.exit(1)

if resp.get("errcode") != 0:
    hint = ""
    if resp.get("errcode") == 310000:
        hint = "（关键词不匹配：请确认消息包含机器人关键词；未知关键词先问群管理员，勿盲目试词）"
    print(f"DINGTALK_SEND_FAIL errcode={resp.get('errcode')} errmsg={resp.get('errmsg')}{hint}", file=sys.stderr)
    sys.exit(1)

print("DINGTALK_SEND_OK")
PY
