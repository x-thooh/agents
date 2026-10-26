#!/usr/bin/env bash
set -euo pipefail

# ============================================================================
# merge-to-test.sh — 把源分支自动合入「提测分支」（默认 test）
#
# 为什么要有这一步：mr-review 的 Phase 7.5 只把 MR 合并到它自己的 target
# （通常是 release/vX.Y.Z）；提测还要再走 release/vX.Y.Z → test，
# 在 Codeup 上的历史形态就是 "Merge #N into test from release/vX.Y.Z"。
#
# 分支模型与合并方式（默认值来自 profile，可用 --test-branch/--merge-type 覆盖）：
#   - 提测分支（branches.test，默认 test）用普通合并（merge commit；Codeup API 取值
#     no-fast-forward，实测字面值 merge 会 403）；feature → release 等其他 MR 走 rebase
#   - allRequirementsPass=false 时先看 checkList：REVIEWER_APPROVED_CHECK 需评审 PASS、
#     COMMENTS_CHECK 需评论全部 resolved，MERGE_CONFLICT_CHECK 需先解决冲突
#   - 405 基本都是合入规则不满足，不是参数问题
#
# 用法：
#   merge-to-test.sh --source release/v4.3.6.2
#   merge-to-test.sh --source release/v4.3.6.2 --dry-run
#
# 选项：
#   --source <ref>        要提测的源分支（默认：当前分支）
#   --test-branch <name>  提测分支名，默认 test
#   --org-id <id>         组织 id（默认取 lastOrganization）
#   --repo-id <id>        Codeup 仓库 id（默认按 origin 远端路径解析）
#   --merge-type <t>      合并方式，默认 no-fast-forward（test 提测用普通合并；实测 merge 字面值 403）
#   --no-review-pass      合入规则要求评审通过时不自动提交 PASS
#   --dry-run             只打印计划，不做任何写操作
#   -h | --help
#
# 依赖：curl、jq、git、环境变量 YUNXIAO_ACCESS_TOKEN
# ============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/config.sh
source "${SCRIPT_DIR}/lib/config.sh"
# shellcheck source=lib/codeup.sh
source "${SCRIPT_DIR}/lib/codeup.sh"

RED=$'\033[0;31m'
GREEN=$'\033[0;32m'
YELLOW=$'\033[0;33m'
NC=$'\033[0m'
ok() { echo "${GREEN}✓${NC} $1"; }
warn() { echo "${YELLOW}⚠${NC} $1"; }
fail() { echo "${RED}✗${NC} $1"; }

for bin in curl jq git; do
	command -v "${bin}" >/dev/null 2>&1 || die "缺少依赖: ${bin}"
done

SOURCE=""
TEST_BRANCH=""
ORG_ID=""
REPO_ID=""
MERGE_TYPE=""
MERGE_TYPE_EXPLICIT=0
DO_REVIEW_PASS=1
DRY_RUN=0

while [ $# -gt 0 ]; do
	case "$1" in
	--source)
		SOURCE="$2"
		shift 2
		;;
	--test-branch)
		TEST_BRANCH="$2"
		shift 2
		;;
	--org-id)
		ORG_ID="$2"
		shift 2
		;;
	--repo-id)
		REPO_ID="$2"
		shift 2
		;;
	--merge-type)
		MERGE_TYPE="$2"
		MERGE_TYPE_EXPLICIT=1
		shift 2
		;;
	--no-review-pass)
		DO_REVIEW_PASS=0
		shift
		;;
	--dry-run)
		DRY_RUN=1
		shift
		;;
	-h | --help)
		sed -n '4,32p' "$0" | sed 's/^# \{0,2\}//'
		exit 0
		;;
	*)
		die "未知参数: $1（--help 看用法）"
		;;
	esac
done

# token 校验放到参数解析之后：--help 无需凭据也能看用法
if [ -z "${API_TOKEN:-}" ]; then
	die "缺少环境变量 YUNXIAO_ACCESS_TOKEN"
fi

cd "$(git rev-parse --show-toplevel)"
mrcfg_init "${PWD}" >/dev/null || die "无法定位仓库根"
# 默认值来自 profile：提测分支名 / 合并方式 / 仓库 id
[ -n "${TEST_BRANCH}" ] || TEST_BRANCH="$(mrcfg_test_branch)"
[ -n "${MERGE_TYPE}" ] || MERGE_TYPE="$(mrcfg_merge_type test)" # 提测用普通合并（merge commit）= no-fast-forward
[ -n "${REPO_ID}" ] || REPO_ID="$(mrcfg_repo_id)"
if [ -z "${SOURCE}" ]; then
	SOURCE="$(git rev-parse --abbrev-ref HEAD)"
fi

DRY_TXT=""
if [ "${DRY_RUN}" = "1" ]; then
	DRY_TXT=", dry-run"
fi
echo "=== merge-to-test: ${SOURCE} → ${TEST_BRANCH}（mergeType=${MERGE_TYPE}${DRY_TXT}）==="

# 源分支规范化：API 用分支名，git 比较用 origin/<branch>（避免误用本地过期分支，
# 实测本地 release/* 可能停在旧提交，直接比较会得出「已提测」的错误结论）。
SOURCE_BRANCH="${SOURCE#origin/}"
if ! git fetch origin "${TEST_BRANCH}" "${SOURCE_BRANCH}" >/dev/null 2>&1; then
	warn "git fetch origin ${TEST_BRANCH} ${SOURCE_BRANCH} 失败，按现有 refs 判断"
fi
SOURCE_REF="origin/${SOURCE_BRANCH}"
if ! git rev-parse --verify "${SOURCE_REF}" >/dev/null 2>&1; then
	SOURCE_REF="${SOURCE_BRANCH}"
fi
if git rev-parse --verify "origin/${TEST_BRANCH}" >/dev/null 2>&1; then
	AHEAD=$(git rev-list --count "origin/${TEST_BRANCH}..${SOURCE_REF}" 2>/dev/null || echo "?")
	info "origin/${TEST_BRANCH} 落后 ${SOURCE_REF} ${AHEAD} 个提交"
	if [ "${AHEAD}" = "0" ]; then
		ok "${SOURCE_BRANCH} 已全部包含在 ${TEST_BRANCH} 中，无需提测合并"
		exit 0
	fi
else
	warn "本地没有 origin/${TEST_BRANCH}，跳过「是否已合并」预检"
fi

# ---------- 1. 解析 org / repo ----------
_org="$(resolve_org_id "${ORG_ID}")"
_repo="$(resolve_repo_id "${_org}" "${REPO_ID}" "")"
info "org=${_org} repo=${_repo}"

BASE_PATH="/oapi/v1/codeup/organizations/${_org}/repositories/${_repo}"

# ---------- 2. 找（或建）source → test 的 MR ----------
MR_LIST="$(api_get_or_die "/oapi/v1/codeup/organizations/${_org}/changeRequests?projectIds=${_repo}&state=opened")"
LOCAL_ID="$(echo "${MR_LIST}" | jq -r --arg src "${SOURCE_BRANCH}" --arg tgt "${TEST_BRANCH}" \
	'[.[] | select(.sourceBranch == $src and .targetBranch == $tgt)] | first | .localId // empty')"

if [ -n "${LOCAL_ID}" ]; then
	info "复用进行中的 MR #${LOCAL_ID}（${SOURCE_BRANCH} → ${TEST_BRANCH}）"
elif [ "${DRY_RUN}" = "1" ]; then
	info "[dry-run] 将创建 MR：${SOURCE_BRANCH} → ${TEST_BRANCH}，随后以 ${MERGE_TYPE} 合并"
	exit 0
else
	info "未找到 ${SOURCE_BRANCH} → ${TEST_BRANCH} 的进行中 MR，创建之"
	TITLE="chore(${TEST_BRANCH}): 提测 ${SOURCE_BRANCH}"
	PAYLOAD="$(jq -n --arg t "${TITLE}" --arg s "${SOURCE_BRANCH}" --arg g "${TEST_BRANCH}" \
		--argjson pid "${_repo}" \
		'{title: $t, sourceBranch: $s, targetBranch: $g, sourceProjectId: $pid, targetProjectId: $pid, createFrom: "WEB"}')"
	CREATED="$(api_post_or_die "/oapi/v1/codeup/organizations/${_org}/repositories/${_repo}/changeRequests" "${PAYLOAD}")"
	LOCAL_ID="$(echo "${CREATED}" | jq -r '.localId // empty')"
	if [ -z "${LOCAL_ID}" ]; then
		die "创建 MR 失败：$(echo "${CREATED}" | head -c 300)"
	fi
	ok "已创建 MR #${LOCAL_ID}"
fi

# ---------- 3. 合入规则预检（405 的绝大多数根因） ----------
mr_get() { api_get_or_die "${BASE_PATH}/changeRequests/${LOCAL_ID}"; }

MR="$(mr_get)"
ALL_PASS="$(echo "${MR}" | jq -r '.allRequirementsPass // false')"
if [ "${ALL_PASS}" != "true" ]; then
	warn "allRequirementsPass=false，逐项检查合入规则："
	echo "${MR}" | jq -r '(.checkList.requirementRuleItems // [])[] | "  - \(.checkRequirementRuleCode // .code // "?"): pass=\(.pass // .status // "?")"'
	BLOCKING="$(echo "${MR}" | jq -r '(.checkList.requirementRuleItems // [])[] | select((.pass // false) == false) | (.checkRequirementRuleCode // .code // empty)')"

	case "${BLOCKING}" in
	*MERGE_CONFLICT_CHECK*)
		fail "存在合并冲突：先在本地 rebase origin/${TEST_BRANCH} 解决后 push"
		exit 1
		;;
	esac
	if printf '%s\n' "${BLOCKING}" | grep -q 'COMMENTS_CHECK'; then
		UNRES="$(echo "${MR}" | jq -r '.unResolvedCommentCount // 0')"
		fail "存在未解决评论（${UNRES} 条）→ COMMENTS_CHECK 不通过。"
		echo "  处理方式：逐条确认后在 Codeup 上 resolve（评审评论默认 unresolved，会阻塞合入）："
		echo "  GET ${API_BASE}${BASE_PATH}/changeRequests/${LOCAL_ID}/comments?resolved=false"
		exit 1
	fi
	if printf '%s\n' "${BLOCKING}" | grep -q 'REVIEWER_APPROVED_CHECK'; then
		if [ "${DO_REVIEW_PASS}" = "1" ]; then
			info "提交评审意见 PASS 以满足 REVIEWER_APPROVED_CHECK"
			api_post_or_die "${BASE_PATH}/changeRequests/${LOCAL_ID}/review" \
				"$(jq -n --arg c "自动提测合并（merge-to-test.sh）" '{reviewOpinion: "PASS", reviewComment: $c}')" >/dev/null
			MR="$(mr_get)"
			ALL_PASS="$(echo "${MR}" | jq -r '.allRequirementsPass // false')"
		else
			fail "需要评审通过（REVIEWER_APPROVED_CHECK），但已指定 --no-review-pass"
			exit 1
		fi
	fi
fi
if [ "${ALL_PASS}" != "true" ]; then
	fail "合入规则仍不满足，以下是当前 checkList 原始值："
	echo "${MR}" | jq '.checkList // {}'
	exit 1
fi
ok "合入规则全部满足（allRequirementsPass=true）"

# ---------- 4. 合并 ----------
# test 分支用普通合并（merge，产生 merge commit，与历史 "Merge #N into test from release/..." 一致）；
# 其余场景（feature → release 的 MR）走 rebase —— 见 SKILL.md「分支与合并路径」。
# Codeup 各版本对 mergeType 命名有差异：默认先用 merge；若被「不支持该合并方式」拒绝且用户未显式
# 指定 --merge-type，则退回 no-fast-forward（同为 merge commit 语义）。
# 实测（提测 MR #168）：mergeType=merge 被 403 拒结，no-fast-forward 才能产生 merge commit；
# 故默认用 no-fast-forward，未显式指定时保留一个候选兜底（防 API 命名变化）。
MERGE_CANDIDATES="${MERGE_TYPE}"
if [ "${MERGE_TYPE}" = "no-fast-forward" ] && [ "${MERGE_TYPE_EXPLICIT}" = "0" ]; then
	MERGE_CANDIDATES="no-fast-forward merge"
fi

MERGE_TMP="/tmp/merge-to-test-resp-$$.json"
trap 'rm -f "${MERGE_TMP}"' EXIT
HTTP_CODE=""
MERGE_BODY="{}"
USED_MERGE_TYPE=""
for _mt in ${MERGE_CANDIDATES}; do
	MERGE_PAYLOAD="$(jq -n \
		--arg m "chore(${TEST_BRANCH}): 提测合并 ${SOURCE_BRANCH} → ${TEST_BRANCH}" \
		--arg t "${_mt}" \
		'{mergeMessage: $m, mergeType: $t}')"
	HTTP_CODE="$(curl -sS -o "${MERGE_TMP}" \
		--max-time 30 --connect-timeout 10 \
		-X POST \
		-H "Accept: application/json" \
		-H "Content-Type: application/json" \
		-H "x-yunxiao-token: ${API_TOKEN}" \
		-d "${MERGE_PAYLOAD}" \
		-w "%{http_code}" \
		"${API_BASE}${BASE_PATH}/changeRequests/${LOCAL_ID}/merge")" || HTTP_CODE=000
	MERGE_BODY="$(cat "${MERGE_TMP}" 2>/dev/null || echo "{}")"
	if [[ "${HTTP_CODE}" =~ ^2[0-9][0-9]$ ]]; then
		USED_MERGE_TYPE="${_mt}"
		break
	fi
	# 仅当首个候选疑似「mergeType 命名不被接受」且还有候选时才继续
	if [ "${_mt}" = "${MERGE_TYPE}" ] && printf '%s' "${MERGE_BODY}" | grep -qE '不支持|not support|unknown|invalid|mergeType'; then
		warn "mergeType=${_mt} 被拒（HTTP ${HTTP_CODE}），改用下一个候选"
		continue
	fi
	break
done

if [ -z "${USED_MERGE_TYPE}" ]; then
	fail "合并失败（HTTP ${HTTP_CODE}）"
	case "${HTTP_CODE}" in
	400) echo "  400 = 参数缺/错（如 mergeType 取值不被识别）" ;;
	403) echo "  403 = 该分支不支持此合并方式" ;;
	405) echo "  405 = 合入规则不满足（回看 checkList：评审/评论/冲突）" ;;
	esac
	echo "  响应: $(echo "${MERGE_BODY}" | head -c 300)"
	exit 1
fi
info "合并方式: ${USED_MERGE_TYPE}"

# ---------- 5. 校验结果 ----------
FINAL="$(mr_get)"
STATUS="$(echo "${FINAL}" | jq -r '.status // "?"')"
MERGED_REV="$(echo "${FINAL}" | jq -r '.mergedRevision // empty')"
if [ "${STATUS}" = "MERGED" ]; then
	ok "MR #${LOCAL_ID} 已合并到 ${TEST_BRANCH}（mergedRevision=${MERGED_REV}）"
	echo "MR: $(echo "${FINAL}" | jq -r '.detailUrl // empty')"
	echo ""
	echo "提测后续：确认 CI/部署把 ${TEST_BRANCH} 发布到测试环境；"
	echo "最终合入主分支（master）走 release → master，仍需满足同一套合入规则（评审 PASS + 评论全 resolved + 无冲突）。"
else
	fail "合并后状态仍为 ${STATUS}（预期 MERGED），请人工确认 MR #${LOCAL_ID}"
	exit 1
fi
