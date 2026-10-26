#!/usr/bin/env bash
set -euo pipefail

# ============================================================================
# sync-codeup-comment.sh — 将 MR review 结论同步到 Codeup MR 评论
#
# 依赖:
#   - curl, jq, git
#   - 环境变量 YUNXIAO_ACCESS_TOKEN (必填)
#
# 用法:
#   ./sync-codeup-comment.sh --meta /tmp/mr-xxx.meta.json --comment "review conclusion"
#   ./sync-codeup-comment.sh --file review.md --draft
#   ./sync-codeup-comment.sh --local-id 42 --comment "ok" --patchset-biz-id xxx
#
# 自动推断顺序 (均可手动 -- 覆盖):
#   organizationId -> YUNXIAO_ORG_ID -> GET /oapi/v1/platform/user
#   repositoryId   -> YUNXIAO_REPO_ID / --repo-id -> --repo-path -> git remote -> search API
#   localId        -> --local-id -> meta 文件 -> list_change_requests by sourceBranch
#   patchset_biz_id-> --patchset-biz-id -> list patchsets (MERGE_SOURCE)
# ============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib/codeup.sh"

usage() {
	cat <<'EOF'
Usage:
  sync-codeup-comment.sh --meta <meta.json> --comment <text>
  sync-codeup-comment.sh --file <review.md>
  sync-codeup-comment.sh --local-id <id> --repo-id <id> --comment <text>

Required (one of):
  --comment <text>       Comment body inline
  --file <path>          Read comment body from file

Options:
  --meta <path>          review-mr.sh produced meta.json (default: inferred from current branch)
  --local-id <id>        MR localId (skips auto-discovery)
  --repo-id <id>         Repository numeric ID (skips search)
  --repo-path <path>     Repository path, e.g. lsxd/ymt/marketing (used to find repoId)
  --org-id <id>          Organization ID (skips /platform/user)
  --patchset-biz-id <id> Patchset biz ID (skips list patches)
  --type <GLOBAL|INLINE> Comment type, default GLOBAL_COMMENT
  --draft                Post as draft comment
  --file-path <path>     Inline comment file path
  --line-number <num>    Inline comment line number
  --from-patchset <id>   Inline comment from patchset biz id
  --to-patchset <id>     Inline comment to patchset biz id
  -h, --help             Show this help
EOF
}

# ======================== main ========================

main() {
	local meta_file=""
	local comment=""
	local comment_file=""
	local local_id=""
	local repo_id=""
	local repo_path=""
	local org_id=""
	local patchset_biz_id=""
	local draft=false
	local comment_type="GLOBAL_COMMENT"
	local inline_file_path=""
	local inline_line_number=""
	local inline_from_patchset=""
	local inline_to_patchset=""
	local source_branch=""
	local target_branch=""

	while [[ $# -gt 0 ]]; do
		case "$1" in
		--meta)
			meta_file="$2"
			shift 2
			;;
		--comment)
			comment="$2"
			shift 2
			;;
		--file)
			comment_file="$2"
			shift 2
			;;
		--local-id)
			local_id="$2"
			shift 2
			;;
		--repo-id)
			repo_id="$2"
			shift 2
			;;
		--repo-path)
			repo_path="$2"
			shift 2
			;;
		--org-id)
			org_id="$2"
			shift 2
			;;
		--patchset-biz-id)
			patchset_biz_id="$2"
			shift 2
			;;
		--draft)
			draft=true
			shift
			;;
		--type)
			comment_type="$2"
			shift 2
			case "$comment_type" in
			GLOBAL_COMMENT | INLINE_COMMENT) ;;
			*) die "Invalid --type: $comment_type (allowed: GLOBAL_COMMENT, INLINE_COMMENT)" ;;
			esac
			;;
		--file-path)
			inline_file_path="$2"
			shift 2
			;;
		--line-number)
			inline_line_number="$2"
			shift 2
			;;
		--from-patchset)
			inline_from_patchset="$2"
			shift 2
			;;
		--to-patchset)
			inline_to_patchset="$2"
			shift 2
			;;
		-h | --help)
			usage
			exit 0
			;;
		*) die "Unknown option: $1" ;;
		esac
	done

	[[ -n "$API_TOKEN" ]] || die "YUNXIAO_ACCESS_TOKEN is not set."

	if [[ -n "$comment_file" ]]; then
		[[ -f "$comment_file" ]] || die "Comment file not found: ${comment_file}"
		comment=$(cat "$comment_file")
	fi
	[[ -n "$comment" ]] || die "Comment content is empty. Use --comment or --file."

	# INLINE 参数校验提前到 API 调用之前，避免缺参时白跑 resolve 链
	if [[ "$comment_type" == "INLINE_COMMENT" ]]; then
		[[ -n "$inline_file_path" ]] || die "INLINE_COMMENT requires --file-path"
		[[ -n "$inline_line_number" ]] || die "INLINE_COMMENT requires --line-number"
		[[ "$inline_line_number" =~ ^[0-9]+$ ]] || die "INLINE_COMMENT --line-number must be numeric"
		[[ -n "$inline_from_patchset" ]] || die "INLINE_COMMENT requires --from-patchset"
		[[ -n "$inline_to_patchset" ]] || die "INLINE_COMMENT requires --to-patchset"
	fi

	# 推断 meta 文件路径
	if [[ -z "$meta_file" ]]; then
		meta_file=$(infer_meta_path)
	fi

	if [[ -n "$meta_file" && -f "$meta_file" ]]; then
		info "Reading meta: ${meta_file}"
		extract_meta_branches "$meta_file"
		source_branch="$META_SOURCE_BRANCH"
		target_branch="$META_TARGET_BRANCH"
	elif [[ -n "$meta_file" ]]; then
		info "Meta file not found: ${meta_file} (continuing without it)"
	fi

	org_id=$(resolve_org_id "$org_id")
	info "organizationId: ${org_id}"

	repo_id=$(resolve_repo_id "$org_id" "$repo_id" "$repo_path")
	info "repositoryId: ${repo_id}"

	local_id=$(resolve_local_id "$org_id" "$repo_id" "$local_id" "$source_branch" "$target_branch")
	info "localId: ${local_id}"

	patchset_biz_id=$(resolve_patchset_biz_id "$org_id" "$repo_id" "$local_id" "$patchset_biz_id")
	info "patchset_biz_id: ${patchset_biz_id}"

	# 构建 payload
	local payload
	payload=$(jq -n \
		--arg content "$comment" \
		--arg type "$comment_type" \
		--argjson draft "$draft" \
		--arg psid "$patchset_biz_id" \
		'{comment_type: $type, content: $content, draft: $draft, resolved: false, patchset_biz_id: $psid}')

	if [[ "$comment_type" == "INLINE_COMMENT" ]]; then
		payload=$(echo "$payload" | jq \
			--arg fp "$inline_file_path" \
			--argjson ln "$inline_line_number" \
			--arg from "$inline_from_patchset" \
			--arg to "$inline_to_patchset" \
			'. + {file_path: $fp, line_number: $ln, from_patchset_biz_id: $from, to_patchset_biz_id: $to}')
	fi

	local encoded_repo_id
	encoded_repo_id=$(urlencode_slash "$repo_id")

	local endpoint="/oapi/v1/codeup/organizations/${org_id}/repositories/${encoded_repo_id}/changeRequests/${local_id}/comments"
	info "Endpoint: ${endpoint}"
	info "Payload:"
	echo "$payload" | jq .

	local resp
	resp=$(api_post_or_die "$endpoint" "$payload")

	local comment_biz_id
	comment_biz_id=$(echo "$resp" | jq -r '.comment_biz_id // empty')
	if [[ -n "$comment_biz_id" ]]; then
		echo "✅ Comment created. commentBizId=${comment_biz_id}"
	else
		echo "⚠️ Comment may have been created. Response:"
		echo "$resp" | jq .
	fi
}

main "$@"
