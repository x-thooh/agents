#!/usr/bin/env bash
set -euo pipefail

# ============================================================================
# codeup.sh — 共享 Codeup OpenAPI 工具函数
#
# 被以下脚本引用：
#   scripts/mr-platform-info.sh
#   scripts/sync-codeup-comment.sh
#
# 依赖:
#   - curl, jq, git
#   - 环境变量 YUNXIAO_ACCESS_TOKEN (必填)
#   - 可选: YUNXIAO_API_BASE_URL, YUNXIAO_ORG_ID, YUNXIAO_REPO_ID
# ============================================================================

# 统一临时响应文件（$$ = 主 shell PID；trap 保证任何退出路径都会清理）
API_RESP_TMP="/tmp/codeup_api_resp_$$.json"
trap 'rm -f "${API_RESP_TMP}"' EXIT

# 复用 git 侧工具（infer_meta_path / extract_meta_branches / extract_repo_path）
_GIT_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${_GIT_LIB_DIR}/git.sh"

if [[ -z "${API_BASE:-}" ]]; then
	API_BASE="${YUNXIAO_API_BASE_URL:-https://openapi-rdc.aliyuncs.com}"
fi
if [[ -z "${API_TOKEN:-}" ]]; then
	API_TOKEN="${YUNXIAO_ACCESS_TOKEN:-}"
fi

# ---------- HTTP ----------

# GET；响应体写入 $API_RESP_TMP，stdout 只输出 HTTP 状态码。调用方需自行读取 $API_RESP_TMP。
api_get_with_status() {
	local path="$1"
	curl -sS -o "$API_RESP_TMP" \
		--max-time 30 \
		--connect-timeout 10 \
		-X GET \
		-H "Accept: application/json" \
		-H "Content-Type: application/json" \
		-H "x-yunxiao-token: ${API_TOKEN}" \
		-w "%{http_code}" \
		"${API_BASE}${path}" || true
}

# 统一 HTTP 失败报错（带状态码与可操作提示）
api_die() {
	local method="$1" path="$2" http_code="$3" body="$4"
	local hint=""
	case "${http_code:-000}" in
	401 | 403) hint="YUNXIAO_ACCESS_TOKEN 无效或已过期。" ;;
	404) hint="资源不存在（localId / repoId / patchset 可能错误）。" ;;
	000) hint="网络连接失败。" ;;
	esac
	die "API ${method} ${path} failed (HTTP ${http_code}). ${hint}响应: $(echo "${body}" | head -c 200)"
}

# GET；失败时带 HTTP 状态码/提示退出，成功时 stdout 输出响应体。
api_get_or_die() {
	local path="$1"
	local http_code body
	http_code=$(api_get_with_status "$path")
	[[ -n "$http_code" ]] || http_code=000
	body=$(cat "$API_RESP_TMP" 2>/dev/null || echo "{}")
	[[ "$http_code" =~ ^2[0-9][0-9]$ ]] || api_die "GET" "$path" "$http_code" "$body"
	echo "$body"
}

# POST；失败时带 HTTP 状态码/提示退出，成功时 stdout 输出响应体。
api_post_or_die() {
	local path="$1" data="$2"
	local http_code body
	http_code=$(curl -sS -o "$API_RESP_TMP" \
		--max-time 30 \
		--connect-timeout 10 \
		-X POST \
		-H "Accept: application/json" \
		-H "Content-Type: application/json" \
		-H "x-yunxiao-token: ${API_TOKEN}" \
		-d "$data" \
		-w "%{http_code}" \
		"${API_BASE}${path}") || true
	[[ -n "$http_code" ]] || http_code=000
	body=$(cat "$API_RESP_TMP" 2>/dev/null || echo "{}")
	[[ "$http_code" =~ ^2[0-9][0-9]$ ]] || api_die "POST" "$path" "$http_code" "$body"
	echo "$body"
}

# 向后兼容：无状态码检查的 GET（供可容忍失败的调用使用，如 pipelines/members）
api_get() {
	local path="$1"
	curl -sS -f \
		--max-time 30 \
		--connect-timeout 10 \
		-X GET \
		-H "Accept: application/json" \
		-H "Content-Type: application/json" \
		-H "x-yunxiao-token: ${API_TOKEN}" \
		"${API_BASE}${path}"
}

# 向后兼容：无状态码检查的 POST
api_post() {
	local path="$1"
	local data="$2"
	curl -sS -f \
		--max-time 30 \
		--connect-timeout 10 \
		-X POST \
		-H "Accept: application/json" \
		-H "Content-Type: application/json" \
		-H "x-yunxiao-token: ${API_TOKEN}" \
		-d "$data" \
		"${API_BASE}${path}"
}

# ---------- helpers ----------

# 仅编码除 / 以外的特殊字符（repo_id 数字场景为 no-op；路径场景保留 /）
urlencode_slash() {
	echo "${1:-}" | jq -rn --arg v "$1" '$v|@uri' | sed 's/%2F/\//g'
}

die() {
	echo "ERROR: $*" >&2
	exit 1
}

info() {
	echo "[codeup-lib] $*"
}

# ---------- resolvers ----------

resolve_org_id() {
	local explicit="$1"
	if [[ -n "$explicit" ]]; then
		echo "$explicit"
		return 0
	fi
	if [[ -n "${YUNXIAO_ORG_ID:-}" ]]; then
		echo "${YUNXIAO_ORG_ID}"
		return 0
	fi
	local resp org
	resp=$(api_get_or_die "/oapi/v1/platform/user") || exit 1
	org=$(echo "$resp" | jq -r '.lastOrganization // empty')
	[[ -n "$org" ]] || die "Cannot resolve organizationId. Pass --org-id or set YUNXIAO_ORG_ID."
	echo "$org"
}

resolve_repo_id() {
	local org_id="$1"
	local explicit_repo_id="$2"
	local explicit_repo_path="$3"

	if [[ -n "$explicit_repo_id" ]]; then
		echo "$explicit_repo_id"
		return 0
	fi
	if [[ -n "${YUNXIAO_REPO_ID:-}" ]]; then
		echo "${YUNXIAO_REPO_ID}"
		return 0
	fi

	local repo_path="$explicit_repo_path"
	if [[ -z "$repo_path" ]]; then
		local remote_url
		remote_url=$(git remote get-url origin 2>/dev/null || echo "")
		if [[ -n "$remote_url" ]]; then
			# 兼容多级路径：git@host:org/repo.git / https://host/org/repo.git / https://host/org/team/repo.git
			repo_path=$(extract_repo_path "$remote_url")
		fi
	fi
	[[ -n "$repo_path" ]] || die "Cannot resolve repository path. Pass --repo-id or --repo-path."

	local search_term
	search_term=$(basename "$repo_path" | sed 's/\.git$//')
	local resp
	resp=$(api_get_or_die "/oapi/v1/codeup/organizations/${org_id}/repositories?search=${search_term}") || exit 1

	local found_id
	found_id=$(echo "$resp" | jq -r --arg exact "$repo_path" '
		[.[] | select(.path == $exact)] | first | .id // empty
	')
	if [[ -z "$found_id" ]]; then
		echo "[codeup-lib] warn: exact path '${repo_path}' 未命中，使用搜索结果第一条（同名仓库可能选错，建议 --repo-id 指定）" >&2
		found_id=$(echo "$resp" | jq -r '.[0].id // empty')
	fi
	[[ -n "$found_id" ]] || die "Cannot resolve repositoryId for path '${repo_path}'. Pass --repo-id."
	echo "$found_id"
}

resolve_local_id() {
	local org_id="$1"
	local repo_id="$2"
	local explicit_local_id="$3"
	local source_branch="$4"
	local target_branch="$5"

	if [[ -n "$explicit_local_id" ]]; then
		echo "$explicit_local_id"
		return 0
	fi
	[[ -n "$source_branch" ]] || die "Cannot resolve localId. Pass --local-id or ensure meta has remote_branch."

	local resp
	resp=$(api_get_or_die "/oapi/v1/codeup/organizations/${org_id}/changeRequests?projectIds=${repo_id}&state=opened") || exit 1

	local found_id
	if [[ -n "$target_branch" ]]; then
		found_id=$(echo "$resp" | jq -r --arg src "$source_branch" --arg tgt "$target_branch" '
			[.[] | select(.sourceBranch == $src and .targetBranch == $tgt)] | first | .localId // empty
		')
	fi
	if [[ -z "$found_id" ]]; then
		found_id=$(echo "$resp" | jq -r --arg src "$source_branch" '
			[.[] | select(.sourceBranch == $src)] | first | .localId // empty
		')
	fi
	[[ -n "$found_id" ]] || die "Cannot resolve localId for source=${source_branch}. Pass --local-id."
	echo "$found_id"
}

resolve_patchset_biz_id() {
	local org_id="$1"
	local repo_id="$2"
	local local_id="$3"
	local explicit_ps="$4"

	if [[ -n "$explicit_ps" ]]; then
		echo "$explicit_ps"
		return 0
	fi
	local resp
	resp=$(api_get_or_die "/oapi/v1/codeup/organizations/${org_id}/repositories/${repo_id}/changeRequests/${local_id}/diffs/patches") || exit 1

	local found_id
	found_id=$(echo "$resp" | jq -r '
		[.[] | select(.relatedMergeItemType == "MERGE_SOURCE")] | sort_by(.createTime // "") | reverse | first | .patchSetBizId // empty
	')
	if [[ -z "$found_id" ]]; then
		found_id=$(echo "$resp" | jq -r '.[0].patchSetBizId // empty')
	fi
	[[ -n "$found_id" ]] || die "Cannot resolve patchset_biz_id. Pass --patchset-biz-id."
	echo "$found_id"
}
