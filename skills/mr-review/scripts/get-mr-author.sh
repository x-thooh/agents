#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# get-mr-author.sh — 解析「钉钉 @ 收件人手机号」列表
#
# 用途：Phase 10（钉钉通知）在**代码审查通过时**把结论推给相关人，并逐个 @。
#       收件人 = ① MR 发起人 ② 本 MR 全部提交者（去重） ③ 可选：测试人员
#
# @ 手机号来源（平台不提供成员手机号 API —— search_organization_members /
# get_organization_member_info(_by_user_id) / list_organization_members 用当前
# token 一律 403；list_commits 只有 authorName/authorEmail，无手机号字段）：
#   1. explicit     — 命令行 --at 显式追加（可多个，逗号分隔）
#   2. config       — 收件人映射文件，键 by_user_id / by_username / by_commit_email
#                     / by_email / by_name / by_commit_name（详见 config 模板）
#   3. username     — 云效 username 形如 `aliyun:<11位手机号>_xxx`
#   4. email        — 邮箱前缀即 11 位手机号（如 15339891972@163.com）
#   5. name         — 提交人姓名本身是 11 位手机号
#   6. none         — 取不到：该人不 @（并列入 unresolved 提示补映射），绝不猜号码
#
# 「本 MR 全部提交者」如何取（精确，不看整条分支历史）：
#   - 优先用**本地 git 两点差集**：`git log --format='%an\t%ae' <base>..<ref>`（= 分支独有提交；
#     不要用三点差集 `<base>...<ref>`：分支落后目标分支时会把 base 侧提交的作者一并串进来）
#     （--base 默认 origin/<MR targetBranch>，与 review-mr.sh 的 base 一致）
#   - git 不可用时回退标准 API：拉源分支提交 + 目标分支提交做 shortId 差集
#
# 「审查通过时 @ 测试人员」：`--with-tester` 依次查 `roles.tester.mobile`（收件人映射文件）
#   → profile 的 `tester.mobile`（仓库级配置）。未通过/未要求时不加。
#
# 用法：
#   get-mr-author.sh --local-id 120 --repo-id <repoId>
#   get-mr-author.sh --local-id 120 --repo-id <repoId> --with-tester
#   get-mr-author.sh --local-id 120 --base origin/release/v4.3.6 --json
#   get-mr-author.sh --local-id 120 --at 13800000000 --json     # 额外追加收件人
#   get-mr-author.sh --self-test                                # 离线自检（不触网）
#
# 输出（默认 key=value；--json 为纯 JSON）：
#   at_mobiles   ← 逗号分隔的手机号列表，直接喂给 send-dingtalk.sh --at
#   recipients   ← 每人 name/email(masked)/mobile/source/matched
#   unresolved   ← 已识别但无手机号的人（提示补映射）
#   at_text_hint ← markdown 正文里要写的 "@手机号" 文本（钉钉需正文含 @ 号才会渲染）
#
# 依赖：curl, jq, git；环境变量 YUNXIAO_ACCESS_TOKEN（--self-test 不需要）
# ==============================================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SKILL_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
# shellcheck source=lib/config.sh
source "${SCRIPT_DIR}/lib/config.sh"
# shellcheck source=lib/codeup.sh
source "${SCRIPT_DIR}/lib/codeup.sh"

# 覆盖 lib 的 info()：本脚本支持 --json，stdout 必须保持纯 JSON/key=value，故提示走 stderr。
info() { echo "[get-mr-author] $*" >&2; }

DEFAULT_CONFIG_PATHS=(
	"${MR_REVIEW_RECIPIENTS:-}"
	"${HOME}/.pi/mr-review-recipients.json"
	"${SKILL_DIR}/config/dingtalk-recipients.json"
)

MAX_RECIPIENTS="${MR_REVIEW_MAX_RECIPIENTS:-10}"

# ------------------------------------------------------------------ 纯函数区

is_mobile() { [[ "${1:-}" =~ ^1[3-9][0-9]{9}$ ]]; }

# 云效 username 形态 `aliyun:<11位手机号>_后缀` → 手机号（仅此形态，避免误抓）
# ⚠️ 必须先落本地变量：is_mobile 内部也会跑 [[ =~ ]]，会覆盖全局 BASH_REMATCH，
#    直接写 is_mobile "${BASH_REMATCH[1]}" && echo "${BASH_REMATCH[1]}" 会取到空值（set -u 下报未绑定）。
uname_to_mobile() {
	local uname="${1:-}"
	local phone=""
	if [[ "$uname" =~ ^aliyun:([0-9]{11})(_|$) ]]; then
		phone="${BASH_REMATCH[1]:-}"
	fi
	if [[ -n "$phone" ]] && is_mobile "$phone"; then
		echo "$phone"
	fi
	return 0
}

# 邮箱前缀即手机号（15339891972@163.com）→ 手机号；QQ号/英文名等不误抓
email_to_mobile() {
	local email="${1:-}"
	[[ "$email" == *"@"* ]] || return 0
	local localpart="${email%%@*}"
	is_mobile "$localpart" && echo "$localpart"
	return 0
}

mask_email() {
	local e="${1:-}"
	[[ "$e" == *"@"* ]] || {
		echo "$e"
		return 0
	}
	local n="${e%%@*}" d="${e##*@}"
	if ((${#n} > 2)); then
		echo "${n:0:1}***${n: -1}@${d}"
	else
		echo "${n:0:1}*@${d}"
	fi
}

# 单个人 → 手机号。入参：name email username userId cfg...
# 输出 `<mobile>\t<source>\t<matched>`；取不到时 mobile 为空、source=none
person_to_mobile() {
	local name="${1:-}" email="${2:-}" username="${3:-}" uid="${4:-}"
	shift 4 || true

	local cfg
	for cfg in "$@"; do
		[[ -n "$cfg" && -f "$cfg" ]] || continue
		local got
		got=$(jq -r --arg uid "$uid" --arg uname "$username" --arg cemail "$email" \
			--arg aemail "$email" --arg aname "$name" --arg cname "$name" '
			. as $c
			| [
				{ k: "by_user_id",      v: ($c.by_user_id[$uid]        // null) },
				{ k: "by_username",     v: ($c.by_username[$uname]     // null) },
				{ k: "by_commit_email", v: ($c.by_commit_email[$cemail] // null) },
				{ k: "by_email",        v: ($c.by_email[$aemail]       // null) },
				{ k: "by_name",         v: ($c.by_name[$aname]         // null) },
				{ k: "by_commit_name",  v: ($c.by_commit_name[$cname]  // null) }
			]
			| map(select(.v != null and (.v | tostring) != ""))
			| (first // null)
			| if . == null then empty else "\(.v)\t\(.k)" end
		' "$cfg" 2>/dev/null || true)
		if [[ -n "$got" ]]; then
			printf '%s\t%s\t%s\n' "${got%%$'\t'*}" "config" "${got##*$'\t'}"
			return 0
		fi
	done

	local m
	m=$(uname_to_mobile "$username")
	if [[ -n "$m" ]]; then
		printf '%s\t%s\t%s\n' "$m" "username" "author.username"
		return 0
	fi
	m=$(email_to_mobile "$email")
	if [[ -n "$m" ]]; then
		printf '%s\t%s\t%s\n' "$m" "email" "email前缀"
		return 0
	fi
	if is_mobile "$name"; then
		printf '%s\t%s\t%s\n' "$name" "name" "authorName"
		return 0
	fi
	printf '%s\t%s\t%s\n' "" "none" ""
	return 0
}

# 读取 roles.<role>.mobile（如 roles.tester）→ 输出 "mobile\tname"
role_mobile() {
	local role="${1:-}" cfg
	shift || true
	for cfg in "$@"; do
		[[ -n "$cfg" && -f "$cfg" ]] || continue
		local got
		got=$(jq -r --arg r "$role" '
			(.roles[$r] // null) | if . == null then empty else "\(.mobile // "")\t\(.name // "")" end
		' "$cfg" 2>/dev/null || true)
		if [[ -n "${got%%$'\t'*}" ]]; then
			echo "$got"
			return 0
		fi
	done
	return 0
}

# 本 MR 全部提交者（本地 git 两点差集 base..ref == 分支独有提交）
# 【坑】不要用三点差集 base...ref：那是对称差集，分支落后目标分支时会把 base 侧提交的作者一并串进来
# （实测：behind 107 的 MR 因此多@ 了 4 位无关同事）
collect_commit_authors_git() {
	local base="$1" ref="$2"
	[[ -n "$base" && -n "$ref" ]] || {
		echo "[]"
		return 0
	}
	local out
	out=$(git log --format='%an%x09%ae' "${base}..${ref}" 2>/dev/null | awk -F'\t' 'NF==2 && !seen[$2]++ {print}') || true
	if [[ -z "$out" ]]; then
		echo "[]"
		return 0
	fi
	printf '%s\n' "$out" | jq -R -s -c '[split("\n")[] | select(length>0) | split("\t") | {name: .[0], email: .[1]}]'
}

# 回退：用 Codeup API 取源分支提交（git 不可用时；退化为"整条分支的作者集合"）
collect_commit_authors_api() {
	local org="$1" repo="$2" ref="$3"
	[[ -n "$ref" ]] || {
		echo "[]"
		return 0
	}
	local enc resp
	enc=$(jq -rn --arg v "$ref" '$v|@uri')
	resp=$(api_get "/oapi/v1/codeup/organizations/${org}/repositories/${repo}/commits?refName=${enc}&perPage=100" 2>/dev/null || echo "")
	[[ -n "$resp" ]] || {
		echo "[]"
		return 0
	}
	echo "$resp" | jq -c '[.[] | {name: (.authorName // ""), email: (.authorEmail // "")}] | map(select(.email != "" or .name != "")) | unique_by(.email)' 2>/dev/null || echo "[]"
}

# ------------------------------------------------------------------ 自检
self_test() {
	local pass=0 fail=0 tmp
	tmp=$(mktemp -d)
	cat >"${tmp}/rec.json" <<'EOF'
{
  "by_user_id":      {"uid-1001": "13900000001"},
  "by_username":     {"aliyun:13800000009_X": "13900000003"},
  "by_commit_email": {"c@d.com": "13900000005", "rol@thooh.com": "13678235158"},
  "by_email":        {"a@b.com": "13900000004"},
  "by_name":         {"张三": "13900000002"},
  "by_commit_name":  {"lisi": "13900000006"},
  "roles":           {"tester": {"name": "Tester", "mobile": "13900000100"}}
}
EOF
	local R="${tmp}/rec.json"

	chk_person() { # desc want_mobile want_source name email username uid
		local desc="$1" want_m="$2" want_s="$3"
		[[ "$want_m" == "-" ]] && want_m=""
		local got m s
		got=$(person_to_mobile "$4" "$5" "$6" "$7" "$R")
		m="${got%%$'\t'*}"
		s=$(echo "$got" | cut -f2)
		if [[ "$m" == "$want_m" && "$s" == "$want_s" ]]; then
			pass=$((pass + 1))
			echo "  ✅ ${desc} (mobile='${m}' source=${s})"
		else
			fail=$((fail + 1))
			echo "  ❌ ${desc} 期望 '${want_m}'/${want_s}，实际 '${m}'/${s}"
		fi
	}

	echo "== get-mr-author.sh --self-test =="
	echo "-- 单人解析：映射优先级与内嵌来源 --"
	chk_person "by_user_id 命中" "13900000001" "config" "李四" "l@y.com" "aliyun:13700000000_A" "uid-1001"
	chk_person "by_username 命中" "13900000003" "config" "王五" "w@y.com" "aliyun:13800000009_X" "uid-x"
	chk_person "by_commit_email 命中（提交人邮箱）" "13900000005" "config" "c" "c@d.com" "" ""
	chk_person "by_name 命中" "13900000002" "config" "张三" "x@y.com" "" "uid-9999"
	chk_person "by_commit_name 命中" "13900000006" "config" "lisi" "x2@y.com" "" ""
	chk_person "username 内嵌手机号" "13911112222" "username" "赵六" "w@y.com" "aliyun:13911112222_Z" "uid-y"
	chk_person "邮箱前缀即手机号" "15339891972" "email" "fuzhongyun" "15339891972@163.com" "" ""
	chk_person "姓名即手机号" "13800000008" "name" "13800000008" "x@y.com" "" ""
	echo "-- 误抓防护 --"
	chk_person "QQ号前缀不误抓" "-" "none" "zhouyonggao" "1971162852@qq.com" "" ""
	chk_person "gmail 用户名不误抓" "-" "none" "wolter" "11@gmail" "" ""
	chk_person "毫无线索 → none" "-" "none" "who" "who@y.com" "aliyun:a@b.com_1" "uid-n"

	echo "-- 提交集口径（分支落后目标时不串入 base 侧作者）--"
	local grepo="${tmp}/gitrepo"
	git init -q "${grepo}" >/dev/null 2>&1 || true
	git -C "${grepo}" -c user.name=bob -c user.email=bob@x.com -c commit.gpgsign=false commit -qm base1 --allow-empty 2>/dev/null || true
	git -C "${grepo}" checkout -qb feature >/dev/null 2>&1 || true
	git -C "${grepo}" -c user.name=alice -c user.email=alice@x.com -c commit.gpgsign=false commit -qm feat1 --allow-empty 2>/dev/null || true
	git -C "${grepo}" checkout -q main >/dev/null 2>&1 || git -C "${grepo}" checkout -q master >/dev/null 2>&1 || true
	git -C "${grepo}" -c user.name=bob -c user.email=bob@x.com -c commit.gpgsign=false commit -qm base2 --allow-empty 2>/dev/null || true
	git -C "${grepo}" branch -M main >/dev/null 2>&1 || true
	local base_ref="main"
	git -C "${grepo}" rev-parse --verify main >/dev/null 2>&1 || base_ref="master"
	local gauthors gn gn0
	gauthors=$(cd "${grepo}" && collect_commit_authors_git "${base_ref}" feature)
	gn=$(printf '%s' "${gauthors}" | jq -r 'length' 2>/dev/null || echo 0)
	gn0=$(printf '%s' "${gauthors}" | jq -r '.[0].name // ""' 2>/dev/null || echo "")
	if [[ "${gn}" == "1" && "${gn0}" == "alice" ]]; then
		pass=$((pass + 1))
		echo "  ✅ 分支落后目标分支时只取分支独有提交（alice），不串入 base 侧作者（bob）"
	else
		fail=$((fail + 1))
		echo "  ❌ 提交集口径错误：期望仅 alice，实际 authors=${gauthors}"
	fi

	echo "-- 多人聚合（本 MR 全部提交者，去重且不跨人串号）--"
	local ca='[
		{"name":"fuzhongyun","email":"15339891972@163.com"},
		{"name":"lirui","email":"rol@thooh.com"},
		{"name":"zhouyonggao","email":"1971162852@qq.com"},
		{"name":"wolter","email":"11@gmail"},
		{"name":"lirui","email":"rol@thooh.com"}
	]'
	local mobiles="" unresolved="" seen=""
	while IFS=$'\t' read -r n e; do
		local got m
		got=$(person_to_mobile "$n" "$e" "" "" "$R")
		m="${got%%$'\t'*}"
		if [[ -n "$m" ]]; then
			[[ ",${seen}," == *",${m},"* ]] || {
				seen="${seen:+${seen},}${m}"
				mobiles="${mobiles:+${mobiles},}${m}"
			}
		else
			unresolved="${unresolved:+${unresolved},}${n}"
		fi
	done < <(jq -r '.[] | "\(.name)\t\(.email)"' <<<"$ca")

	if [[ "$mobiles" == "15339891972,13678235158" ]]; then
		pass=$((pass + 1))
		echo "  ✅ 聚合手机号=15339891972,13678235158（fuzhongyun 邮箱内嵌 + lirui 映射）"
	else
		fail=$((fail + 1))
		echo "  ❌ 聚合手机号 期望 15339891972,13678235158，实际 '${mobiles}'"
	fi
	if [[ "$unresolved" == "zhouyonggao,wolter" ]]; then
		pass=$((pass + 1))
		echo "  ✅ unresolved=zhouyonggao,wolter（无法解析者列出、不猜）"
	else
		fail=$((fail + 1))
		echo "  ❌ unresolved 期望 zhouyonggao,wolter，实际 '${unresolved}'"
	fi
	if [[ "$mobiles" != *"13900000005"* ]]; then
		pass=$((pass + 1))
		echo "  ✅ 不跨人串号（未把他人的映射手机号发给本人）"
	else
		fail=$((fail + 1))
		echo "  ❌ 出现跨人串号"
	fi

	echo "-- 测试人员角色（审查通过时 @）--"
	local t
	t=$(role_mobile "tester" "$R")
	if [[ "${t%%$'\t'*}" == "13900000100" ]]; then
		pass=$((pass + 1))
		echo "  ✅ roles.tester → 13900000100（${t##*$'\t'}）"
	else
		fail=$((fail + 1))
		echo "  ❌ roles.tester 解析失败（实际 '${t}'）"
	fi
	t=$(role_mobile "nonexistent" "$R")
	if [[ -z "$t" ]]; then
		pass=$((pass + 1))
		echo "  ✅ 不存在的角色 → 空（不报错）"
	else
		fail=$((fail + 1))
		echo "  ❌ 不存在的角色应为空，实际 '${t}'"
	fi

	rm -rf "$tmp"
	echo ""
	echo "结果: ${pass} passed, ${fail} failed"
	[[ $fail -eq 0 ]] || return 1
	return 0
}

# ------------------------------------------------------------------ main
main() {
	local meta_file="" local_id="" repo_id="" repo_path="" org_id=""
	local explicit_at="" config_path="" as_json=false with_tester=false
	local source_branch="" target_branch="" base_override="" ref_override=""
	local use_git=true

	while [[ $# -gt 0 ]]; do
		case "$1" in
		--meta)
			meta_file="$2"
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
		--at)
			explicit_at="$2"
			shift 2
			;;
		--config)
			config_path="$2"
			shift 2
			;;
		--base)
			base_override="$2"
			shift 2
			;;
		--ref)
			ref_override="$2"
			shift 2
			;;
		--with-tester)
			with_tester=true
			shift
			;;
		--no-git)
			use_git=false
			shift
			;;
		--json)
			as_json=true
			shift
			;;
		--self-test)
			self_test
			return $?
			;;
		-h | --help)
			grep '^#' "$0" | sed 's/^# \{0,2\}//' | grep -v '^='
			return 0
			;;
		*) die "未知参数: $1" ;;
		esac
	done

	if [[ -z "$meta_file" ]]; then
		meta_file=$(infer_meta_path || true)
	fi
	if [[ -n "$meta_file" && -f "$meta_file" ]]; then
		extract_meta_branches "$meta_file" || true
		source_branch="${META_SOURCE_BRANCH:-}"
		target_branch="${META_TARGET_BRANCH:-}"
		info "Reading meta: ${meta_file}"
	elif [[ -n "$meta_file" ]]; then
		info "warn: meta 文件不存在（${meta_file}）"
		meta_file=""
	fi

	mrcfg_init "${PWD}" >/dev/null 2>&1 || true
	[[ -n "$API_TOKEN" ]] || die "缺少环境变量 YUNXIAO_ACCESS_TOKEN"

	local org repo
	org=$(resolve_org_id "$org_id")
	repo=$(resolve_repo_id "$org" "$repo_id" "$repo_path")
	[[ -n "$local_id" ]] || local_id=$(resolve_local_id "$org" "$repo" "" "$source_branch" "$target_branch")
	info "organizationId: ${org}"
	info "repositoryId: ${repo}"
	info "localId: ${local_id}"

	local resp mr_author
	resp=$(api_get_or_die "/oapi/v1/codeup/organizations/${org}/repositories/${repo}/changeRequests/${local_id}") || exit 1
	mr_author=$(echo "$resp" | jq -c '.author // {}')
	[[ "$mr_author" != "{}" ]] || die "MR #${local_id} 无 author 字段"

	local a_name a_uid a_uname a_email
	a_name=$(jq -r '.name // ""' <<<"$mr_author")
	a_uid=$(jq -r '.userId // ""' <<<"$mr_author")
	a_uname=$(jq -r '.username // ""' <<<"$mr_author")
	a_email=$(jq -r '.email // ""' <<<"$mr_author")

	[[ -n "$source_branch" ]] || source_branch=$(echo "$resp" | jq -r '.sourceBranch // empty')
	[[ -n "$target_branch" ]] || target_branch=$(echo "$resp" | jq -r '.targetBranch // empty')
	local ref="${ref_override:-origin/${source_branch}}"
	local base="${base_override:-origin/${target_branch}}"

	# 本 MR 全部提交者
	local commit_json="[]" ca_count=0
	if [[ "$use_git" == true ]] && git rev-parse --git-dir >/dev/null 2>&1; then
		commit_json=$(collect_commit_authors_git "$base" "$ref")
	fi
	ca_count=$(jq -r 'length' <<<"$commit_json" 2>/dev/null || echo 0)
	if [[ "$ca_count" == "0" ]]; then
		commit_json=$(collect_commit_authors_api "$org" "$repo" "$source_branch")
		ca_count=$(jq -r 'length' <<<"$commit_json" 2>/dev/null || echo 0)
		info "commits: 使用 API 回退（git 不可用或差集为空），authors=${ca_count}"
	else
		info "commits: git 两点差集 ${base}..${ref}（分支独有提交），distinct_authors=${ca_count}"
	fi

	local cfg_candidates=()
	if [[ -n "$config_path" ]]; then
		cfg_candidates=("$config_path")
	else
		cfg_candidates=("${DEFAULT_CONFIG_PATHS[@]}")
		# profile 里配的收件人文件优先级最低，仅在其余候选都不存在时生效
		local _rf
		_rf="$(mrcfg_recipients_file)"
		if [[ -n "$_rf" && -f "$_rf" ]]; then
			cfg_candidates+=("$_rf")
		fi
	fi
	local used_cfg=""
	local c
	for c in "${cfg_candidates[@]}"; do
		[[ -n "$c" && -f "$c" ]] || continue
		used_cfg="$c"
		break
	done

	# 组装收件人：MR 发起人 + 提交者 +（可选）测试人员
	local rec_json="[]" unresolved_json="[]" mobiles="" seen=""

	# 加一个**已知手机号**的收件人（角色 / --at 用；不经 person_to_mobile 解析）
	add_known() { # name mobile source matched is_tester
		local n="${1:-}" m="${2:-}" s="${3:-}" k="${4:-}" t="${5:-false}"
		[[ -n "$m" ]] || return 0
		if [[ ",${seen}," == *",${m},"* ]]; then
			return 0
		fi
		seen="${seen:+${seen},}${m}"
		mobiles="${mobiles:+${mobiles},}${m}"
		rec_json=$(jq -c --arg n "$n" --arg m "$m" --arg s "$s" --arg k "$k" --arg t "$t" \
			'. + [{name:$n, email:"", mobile:$m, source:$s, matched:$k, is_tester:($t=="true")}]' <<<"$rec_json")
	}

	add_person() { # name email username uid is_tester
		local n="$1" e="$2" u="$3" id="$4" tester="${5:-false}"
		local got m s mk
		got=$(person_to_mobile "$n" "$e" "$u" "$id" "${cfg_candidates[@]}")
		m="${got%%$'\t'*}"
		s=$(echo "$got" | cut -f2)
		mk=$(echo "$got" | cut -f3)
		if [[ -z "$m" ]]; then
			unresolved_json=$(jq -c --arg n "$n" --arg e "$(mask_email "$e")" --arg t "$tester" \
				'. + [{name:$n, email:$e, is_tester:($t=="true")}]' <<<"$unresolved_json")
			return 0
		fi
		if [[ ",${seen}," == *",${m},"* ]]; then
			return 0
		fi
		seen="${seen:+${seen},}${m}"
		mobiles="${mobiles:+${mobiles},}${m}"
		rec_json=$(jq -c --arg n "$n" --arg e "$(mask_email "$e")" --arg m "$m" --arg s "$s" --arg k "$mk" --arg t "$tester" \
			'. + [{name:$n, email:$e, mobile:$m, source:$s, matched:$k, is_tester:($t=="true")}]' <<<"$rec_json")
	}

	add_person "$a_name" "$a_email" "$a_uname" "$a_uid" "false"
	while IFS=$'\t' read -r n e; do
		[[ -n "$n$e" ]] || continue
		add_person "$n" "$e" "" "" "false"
	done < <(jq -r '.[] | "\(.name)\t\(.email)"' <<<"$commit_json")

	if [[ "$with_tester" == true ]]; then
		local tm
		tm=$(role_mobile "tester" "${cfg_candidates[@]}")
		if [[ -n "${tm%%$'\t'*}" ]]; then
			add_known "${tm##*$'\t'}" "${tm%%$'\t'*}" "role" "roles.tester" "true"
		elif [[ -n "$(mrcfg_tester_mobile)" ]]; then
			add_known "$(mrcfg_tester_name)" "$(mrcfg_tester_mobile)" "role" "profile.tester" "true"
		else
			info "warn: --with-tester 但既无 roles.tester.mobile 也无 profile.tester.mobile"
		fi
	fi

	# --at：显式追加收件人（支持逗号分隔多个）；用于临时加人（如测试人员）
	if [[ -n "$explicit_at" ]]; then
		local _one
		IFS=',' read -ra _ats <<<"$explicit_at"
		for _one in "${_ats[@]}"; do
			_one=$(echo "$_one" | tr -d '[:space:]')
			add_known "--at(显式)" "$_one" "explicit" "--at" "false"
		done
	fi

	# 上限保护
	local total
	total=$(jq -r 'length' <<<"$rec_json")
	if [[ "$total" -gt "$MAX_RECIPIENTS" ]]; then
		info "warn: 收件人 ${total} 人超过上限 ${MAX_RECIPIENTS}，仅取前 ${MAX_RECIPIENTS} 人"
		rec_json=$(jq -c --argjson n "$MAX_RECIPIENTS" '.[0:$n]' <<<"$rec_json")
		mobiles=$(jq -r '[.[].mobile] | join(",")' <<<"$rec_json")
	fi

	local first_mobile first_source text_hint
	first_mobile=$(jq -r '.[0].mobile // ""' <<<"$rec_json")
	first_source=$(jq -r '.[0].source // "none"' <<<"$rec_json")
	text_hint=$(jq -r '[.[].mobile] | map("@" + .) | join(" ")' <<<"$rec_json")

	if [[ "$as_json" == true ]]; then
		jq -n \
			--argjson local_id "$local_id" \
			--arg a_name "$a_name" --arg a_uid "$a_uid" --arg a_uname "$a_uname" --arg a_email "$a_email" \
			--argjson recipients "$rec_json" --argjson unresolved "$unresolved_json" \
			--arg mobiles "$mobiles" --arg first "$first_mobile" --arg fsrc "$first_source" \
			--arg hint "$text_hint" --arg cfg "$used_cfg" --arg base "$base" --arg ref "$ref" \
			--argjson ca "$ca_count" --arg wt "$with_tester" \
			'{
				mr_local_id: $local_id,
				author_name: $a_name,
				author_user_id: $a_uid,
				author_username: $a_uname,
				author_email: $a_email,
				at_mobiles: $mobiles,
				at_mobile: $first,
				at_source: $fsrc,
				at_text_hint: $hint,
				recipients: $recipients,
				unresolved: $unresolved,
				commit_authors: $ca,
				commits_base: $base,
				commits_ref: $ref,
				with_tester: ($wt == "true"),
				recipients_config: $cfg
			}'
	else
		echo "mr_local_id: ${local_id}"
		echo "author_name: ${a_name}"
		echo "author_username: ${a_uname}"
		echo "author_email: ${a_email}"
		echo "at_mobiles: ${mobiles}"
		echo "at_mobile: ${first_mobile}"
		echo "at_source: ${first_source}"
		echo "at_text_hint: ${text_hint}"
		echo "commit_authors: ${ca_count}"
		echo "commits_base: ${base}"
		echo "commits_ref: ${ref}"
		echo "with_tester: ${with_tester}"
		echo "recipients_config: ${used_cfg}"
		echo "recipients: $(jq -r '.[] | "\(.name)<\(.email)>=\(.mobile)[\(.source)]"' <<<"$rec_json" | paste -sd'; ' -)"
		echo "unresolved: $(jq -r '.[] | "\(.name)<\(.email)>"' <<<"$unresolved_json" | paste -sd'; ' -)"
	fi

	if [[ -z "$mobiles" ]]; then
		{
			echo "[get-mr-author] warn: 未解析到任何 @ 手机号 → 本次不 @（仅发消息）。"
			echo "[get-mr-author] 说明：云效不提供成员手机号 API（成员类接口一律 403），"
			echo "[get-mr-author]       手机号只能来自 username/email 内嵌或收件人映射文件。"
			echo "[get-mr-author] 补齐：写入 ~/.pi/mr-review-recipients.json（键可用 by_user_id/by_username/"
			echo "[get-mr-author]       by_commit_email/by_email/by_name/by_commit_name），或发送时 --at 覆盖。"
		} >&2
	elif [[ "$(jq -r 'length' <<<"$unresolved_json")" != "0" ]]; then
		info "note: 以下人员已识别但无手机号（未 @）：$(jq -r '[.[] | "\(.name)<\(.email)>"] | join("; ")' <<<"$unresolved_json")"
		info "note: 可在 ~/.pi/mr-review-recipients.json 的 by_commit_email 中补映射"
	fi
	return 0
}

main "$@"
