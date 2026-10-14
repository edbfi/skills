#!/usr/bin/env bash
# GraphQL variables ($owner, $endCursor, ...) are meant to stay literal.
# shellcheck disable=SC2016
# pr-ops.sh: the GitHub side of the babysit-pr loop.
#
# reply, react, resolve and retrigger implement references/github-operations.md
# exactly; status, wait and comment build on the same helpers. Every write
# asserts the returned actor, value and target with jq -e, so a zero exit
# status means GitHub stored what was asked for.
#
# Exit codes: 0 ok, 1 GitHub/jq failure, 2 usage error, 3 refused (would
# duplicate a reply or comment; pass --force to override), 124 wait timed out.
set -euo pipefail

GH_API_VERSION="2026-03-10"

usage() {
  cat <<'EOF'
usage: pr-ops.sh <command> [--repo owner/name] [--pr N] [options]

  status    [--since CURSOR]               JSON snapshot: PR state, head checks,
                                           reviewers, unanswered threads, feedback
  wait      [--since CURSOR] [--timeout S] [--interval S] [--settle S]
                                           block until new activity, finished
                                           checks, a new head or a closed PR
  reply     --comment CID [--force]        reply to an inline review comment;
                                           body on stdin
  react     --comment CID --verdict V      V: VALID (+1), INVALID (-1),
                                           'OUT OF SCOPE' (+1)
  resolve   CID [CID...]                   resolve the threads holding these
                                           comments
  comment   --ack ID [--ack ID...] [--force]
                                           top-level PR comment answering
                                           feedback IDs (pullrequestreview-N,
                                           issuecomment-N); body on stdin
  retrigger --trigger TEXT                 post the exact trigger comment, or
                                           reuse an active one

--repo and --pr default to the current checkout's repository and branch PR.
EOF
}

die() { printf 'pr-ops: %s\n' "$*" >&2; exit 2; }

gh_rest() {
  gh api \
    -H 'Accept: application/vnd.github+json' \
    -H "X-GitHub-Api-Version: ${GH_API_VERSION}" \
    "$@"
}

fetch_pages() {
  gh_rest "$1" --paginate --slurp
}

COMMAND=${1:-}
[ -n "${COMMAND}" ] || { usage >&2; exit 2; }
shift
case "${COMMAND}" in
  -h|--help|help) usage; exit 0 ;;
esac

REPO=""; PR_ID=""; CID=""; VERDICT=""; TRIGGER_COMMENT=""; SINCE=""
TIMEOUT=1800; INTERVAL=60; SETTLE=30; FORCE=0; ACKS=""; CIDS=""
while [ $# -gt 0 ]; do
  case "$1" in
    --repo) REPO=${2:?--repo needs a value}; shift 2 ;;
    --pr) PR_ID=${2:?--pr needs a value}; shift 2 ;;
    --comment) CID=${2:?--comment needs a value}; shift 2 ;;
    --verdict) VERDICT=${2:?--verdict needs a value}; shift 2 ;;
    --trigger) TRIGGER_COMMENT=${2:?--trigger needs a value}; shift 2 ;;
    --since) SINCE=${2?--since needs a value}; shift 2 ;;
    --timeout) TIMEOUT=${2:?--timeout needs a value}; shift 2 ;;
    --interval) INTERVAL=${2:?--interval needs a value}; shift 2 ;;
    --settle) SETTLE=${2:?--settle needs a value}; shift 2 ;;
    --ack) ACKS="${ACKS} ${2:?--ack needs a value}"; shift 2 ;;
    --force) FORCE=1; shift ;;
    -h|--help) usage; exit 0 ;;
    --*) die "unknown option: $1" ;;
    *) CIDS="${CIDS} $1"; shift ;;
  esac
done

for tool in gh jq; do
  command -v "${tool}" >/dev/null 2>&1 || die "${tool} is not on PATH"
done
for n in "${TIMEOUT}" "${INTERVAL}" "${SETTLE}"; do
  case "${n}" in ''|*[!0-9]*) die "--timeout, --interval and --settle take whole seconds" ;; esac
done

if [ -z "${REPO}" ]; then
  [ -z "${PR_ID}" ] || die "--pr needs --repo"
  REPO=$(gh repo view --json nameWithOwner --jq '.nameWithOwner') \
    || die "not in a GitHub checkout; pass --repo and --pr"
fi
case "${REPO}" in */*) ;; *) die "--repo must be owner/name" ;; esac
OWNER=${REPO%%/*}
NAME=${REPO#*/}

need_pr() {
  if [ -z "${PR_ID}" ]; then
    PR_ID=$(gh pr view --json number --jq '.number') \
      || die "no PR for the current branch; pass --pr"
  fi
  case "${PR_ID}" in ''|*[!0-9]*) die "--pr must be a PR number" ;; esac
}

need_cid() {
  case "$1" in ''|*[!0-9]*) die "$2 must be a numeric review-comment ID" ;; esac
}

read_body() {
  local body
  body=$(cat)
  [ -n "${body//[[:space:]]/}" ] || die "empty body on stdin"
  printf '%s' "${body}"
}

GH_USER=$(gh api user --jq '.login')

WORK=$(mktemp -d "${TMPDIR:-/tmp}/pr-ops.XXXXXX")
trap 'rm -rf "${WORK}"' EXIT

# --- shared reads -----------------------------------------------------------

# GitHub's own clock (the Date header), as a GitHub timestamp. Cursors come from
# here rather than from item timestamps, so feedback that lands while a snapshot
# is being read is never skipped, and never from the local clock.
server_now() {
  local now
  now=$(gh api -i rate_limit | tr -d '\r' | sed -n 's/^[Dd]ate: //p' | head -n 1 \
    | jq -Rr 'strptime("%a, %d %b %Y %H:%M:%S GMT") | mktime | todate')
  [ -n "${now}" ] || { printf 'pr-ops: could not read GitHub server time\n' >&2; exit 1; }
  printf '%s' "${now}"
}

# rootComment identifies the thread; comments(last: 100) keeps the newest
# replies even in threads longer than one page.
fetch_threads() {
  gh api graphql --paginate --slurp \
    -f owner="${OWNER}" \
    -f repo="${NAME}" \
    -F pr="${PR_ID}" \
    -f query='
      query(
        $owner: String!
        $repo: String!
        $pr: Int!
        $endCursor: String
      ) {
        repository(owner: $owner, name: $repo) {
          pullRequest(number: $pr) {
            reviewThreads(first: 100, after: $endCursor) {
              nodes {
                id
                isResolved
                isOutdated
                path
                line
                rootComment: comments(first: 1) {
                  nodes {
                    fullDatabaseId
                    author { __typename login }
                    url
                  }
                }
                comments(last: 100) {
                  totalCount
                  nodes {
                    fullDatabaseId
                    author { __typename login }
                    body
                    createdAt
                    url
                  }
                }
              }
              pageInfo { hasNextPage endCursor }
            }
          }
        }
      }
    '
}

# gh pr checks exits 8 while checks are pending and 1 when any fail or none
# exist, and still prints the JSON. Accept that JSON, or gh's "no checks
# reported" message as an empty list; anything else (auth, network, rate limit)
# is a real failure and must not read as "no checks".
fetch_checks() {
  local out rc=0
  out=$(gh pr checks "${PR_ID}" --repo "${REPO}" "$@" \
    --json name,state,bucket,workflow,link 2>"${WORK}/checks.err") || rc=$?
  if jq -e 'type == "array"' <<<"${out:-null}" >/dev/null 2>&1; then
    printf '%s' "${out}"
  elif grep -q -E '^no (required )?checks reported' "${WORK}/checks.err"; then
    printf '[]'
  else
    printf 'pr-ops: gh pr checks failed (exit %s): %s\n' "${rc}" "$(cat "${WORK}/checks.err")" >&2
    exit 1
  fi
}

# Latest non-self activity across issue comments (created or edited), submitted
# reviews and inline comments, as a GitHub timestamp ("" when there is none).
latest_activity() {
  fetch_pages "repos/${REPO}/issues/${PR_ID}/comments?per_page=100" >"${WORK}/a-issue.json"
  fetch_pages "repos/${REPO}/pulls/${PR_ID}/reviews?per_page=100" >"${WORK}/a-reviews.json"
  fetch_pages "repos/${REPO}/pulls/${PR_ID}/comments?per_page=100" >"${WORK}/a-inline.json"
  jq -nr \
    --arg user "${GH_USER}" \
    --slurpfile issue "${WORK}/a-issue.json" \
    --slurpfile reviews "${WORK}/a-reviews.json" \
    --slurpfile inline "${WORK}/a-inline.json" '
      [
        ($issue[0][][] | select(.user.login != $user) | .created_at, .updated_at),
        ($reviews[0][][]
          | select(.user.login != $user and .submitted_at != null)
          | .submitted_at),
        ($inline[0][][] | select(.user.login != $user) | .created_at)
      ]
      | max // ""
    '
}

# --- status -------------------------------------------------------------------

read_snapshot() {
  gh pr view "${PR_ID}" --repo "${REPO}" --json \
    number,title,url,state,isDraft,mergeable,mergeStateStatus,reviewDecision,headRefName,headRefOid,baseRefName,isCrossRepository,headRepository \
    >"${WORK}/pr.json"
  fetch_checks >"${WORK}/checks.json"
  fetch_checks --required >"${WORK}/required.json"
  fetch_threads >"${WORK}/threads.json"
  fetch_pages "repos/${REPO}/issues/${PR_ID}/comments?per_page=100" >"${WORK}/issue.json"
  fetch_pages "repos/${REPO}/pulls/${PR_ID}/reviews?per_page=100" >"${WORK}/reviews.json"
}

cmd_status() {
  need_pr
  local cursor head_before head_after attempt=0
  # A push during the reads would mix two heads in one snapshot; read again.
  while :; do
    cursor=$(server_now)
    read_snapshot
    head_before=$(jq -r '.headRefOid' "${WORK}/pr.json")
    head_after=$(gh pr view "${PR_ID}" --repo "${REPO}" --json headRefOid --jq '.headRefOid')
    [ "${head_before}" != "${head_after}" ] || break
    attempt=$((attempt + 1))
    [ "${attempt}" -lt 3 ] || { printf 'pr-ops: PR head keeps moving; try again later\n' >&2; exit 1; }
  done

  jq -n \
    --arg me "${GH_USER}" \
    --arg since "${SINCE}" \
    --arg cursor "${cursor}" \
    --arg repo "${REPO}" \
    --slurpfile pr "${WORK}/pr.json" \
    --slurpfile checks "${WORK}/checks.json" \
    --slurpfile required "${WORK}/required.json" \
    --slurpfile threads "${WORK}/threads.json" \
    --slurpfile issue "${WORK}/issue.json" \
    --slurpfile reviews "${WORK}/reviews.json" '
      def norm: sub("\\[bot\\]$"; "");
      def who: .author.login // "ghost";
      def thread_view:
        (.comments.nodes | map(select(who != $me)) | last) as $latest
        | {
            thread_id: .id,
            root_comment_id: (.rootComment.nodes[0].fullDatabaseId | tostring),
            latest_comment_id: ($latest.fullDatabaseId | tostring),
            root_author: (.rootComment.nodes[0] | who),
            root_bot: (.rootComment.nodes[0].author.__typename == "Bot"),
            path, line, isOutdated,
            url: .rootComment.nodes[0].url,
            earlier_comments_omitted: (.comments.totalCount - (.comments.nodes | length)),
            comments: [
              .comments.nodes[]
              | {
                  id: (.fullDatabaseId | tostring),
                  author: who,
                  bot: (.author.__typename == "Bot"),
                  createdAt,
                  body
                }
            ]
          };
      def last_is_me: (.comments.nodes | last | who) == $me;

      $pr[0] as $p
      | $checks[0] as $ch
      | ($required[0] | map(.name)) as $req
      | [$threads[0][].data.repository.pullRequest.reviewThreads.nodes[]] as $t
      | [$issue[0][][]] as $ic
      | [$reviews[0][][] | select(.submitted_at != null)] as $rv
      # Each feedback ID with the time of our latest comment that answered it.
      | (
          [
            $ic[]
            | select(.user.login == $me)
            | .created_at as $at
            | .body
            | scan("<!-- babysit-pr:ack ([^>]*?) -->")
            | .[0]
            | splits(" +")
            | select(length > 0)
            | {key: ., value: $at}
          ]
          | group_by(.key)
          | map({key: .[0].key, value: (map(.value) | max)})
          | from_entries
        ) as $acked
      | {
          pr: ($p | {
            number, title, url, state, isDraft, mergeable, mergeStateStatus,
            reviewDecision, headRefName, baseRefName, head_sha: .headRefOid,
            base_repo: $repo, head_repo: .headRepository.nameWithOwner, isCrossRepository
          }),
          me: $me,
          checks: {
            counts: ($ch | group_by(.bucket) | map({key: .[0].bucket, value: length}) | from_entries),
            failing: [
              $ch[]
              | select(.bucket == "fail" or .bucket == "cancel")
              | {name, workflow, state, link, required: (.name as $n | $req | index($n) != null)}
            ],
            pending: [$ch[] | select(.bucket == "pending") | .name],
            required_reported: $req
          },
          reviewers: (
            [
              ($rv[] | select(.user.login != $me)
                | {login: (.user.login | norm), bot: (.user.type == "Bot"),
                   review_commit: .commit_id, at: .submitted_at}),
              ($t[].comments.nodes[] | select(who != $me)
                | {login: who, bot: (.author.__typename == "Bot"), at: .createdAt})
            ]
            | group_by(.login)
            | map({
                login: .[0].login,
                bot: any(.[]; .bot),
                reviewed_head: any(.[]; .review_commit == $p.headRefOid),
                last_review_commit: (map(select(.review_commit != null)) | max_by(.at) | .review_commit),
                last_activity_at: (map(.at) | max)
              })
          ),
          pending_threads: [
            $t[] | select((.isResolved | not) and (last_is_me | not)) | thread_view
          ],
          unfinished_threads: [
            $t[] | select((.isResolved | not) and last_is_me and .rootComment.nodes[0].author.__typename == "Bot")
            | thread_view
          ],
          awaiting_humans: [
            $t[] | select((.isResolved | not) and last_is_me and .rootComment.nodes[0].author.__typename != "Bot")
            | {thread_id: .id, url: .rootComment.nodes[0].url, root_author: (.rootComment.nodes[0] | who)}
          ],
          followups: [
            $t[]
            | select(.isResolved and any(.comments.nodes[]; who == $me))
            | (.comments.nodes | last) as $last
            | select(($last | who) != $me and $last.createdAt >= $since)
            | thread_view
          ],
          feedback: (
            [
              $rv[]
              | select(.user.login != $me and (.body // "") != "" and .submitted_at >= $since)
              | {kind: "review", ack_id: "pullrequestreview-\(.id)", author: (.user.login | norm),
                 bot: (.user.type == "Bot"), state, commit_id, created_at: .submitted_at,
                 revised_at: .submitted_at, url: .html_url, body}
            ]
            + [
              $ic[]
              | select(.user.login != $me and .updated_at >= $since)
              | {kind: "issue_comment", ack_id: "issuecomment-\(.id)", author: (.user.login | norm),
                 bot: (.user.type == "Bot"), created_at, revised_at: .updated_at,
                 edited: (.updated_at != .created_at), url: .html_url, body}
            ]
            # Answered feedback stays hidden until its author edits it again.
            | map(select(($acked[.ack_id] // "") < .revised_at))
            | sort_by(.created_at)
          ),
          cursor: $cursor
        }
    '
}

# --- wait ---------------------------------------------------------------------

snapshot_line() {
  local pr checks
  pr=$(gh pr view "${PR_ID}" --repo "${REPO}" --json state,headRefOid)
  checks=$(fetch_checks)
  jq -nr --argjson pr "${pr}" --argjson checks "${checks}" '
    [
      $pr.state,
      $pr.headRefOid,
      ([$checks[] | select(.bucket == "pending")] | length | tostring),
      ($checks | map("\(.name)=\(.bucket)") | sort | join(","))
    ]
    | join("\t")
  '
}

cmd_wait() {
  need_pr
  local since start head pending fp now_state now_head now_pending now_fp
  local activity reason deadline
  since=${SINCE}
  [ -n "${since}" ] || since=$(server_now)
  start=$(snapshot_line)
  IFS=$'\t' read -r _ head pending fp <<<"${start}"
  deadline=$((SECONDS + TIMEOUT))
  reason=""

  while [ "${SECONDS}" -lt "${deadline}" ]; do
    sleep "${INTERVAL}"
    IFS=$'\t' read -r now_state now_head now_pending now_fp <<<"$(snapshot_line)"
    activity=$(latest_activity)
    if [ "${now_state}" != "OPEN" ]; then
      reason="pr-${now_state}"
    elif [ "${now_head}" != "${head}" ]; then
      reason="head-changed"
    elif [ -n "${activity}" ] && [[ ! "${activity}" < "${since}" ]]; then
      reason="new-activity"
      # Bots often post a review and its follow-ups seconds apart.
      sleep "${SETTLE}"
    elif [ "${now_pending}" = 0 ] && { [ "${pending}" != 0 ] || [ "${now_fp}" != "${fp}" ]; }; then
      reason="checks-finished"
    fi
    [ -z "${reason}" ] || break
  done

  jq -nc \
    --arg reason "${reason:-timeout}" \
    --arg since "${since}" \
    --arg latest "${activity:-}" \
    --arg head "${now_head:-${head}}" \
    '{reason: $reason, since: $since, latest_activity: $latest, head_sha: $head}'
  [ -n "${reason}" ] || exit 124
}

# --- 1. reply -----------------------------------------------------------------

cmd_reply() {
  need_pr
  need_cid "${CID}" "--comment"
  local REPLY_BODY COMMENT_JSON ROOT_CID REPLY_JSON REPLY_ID LAST_AUTHOR
  REPLY_BODY=$(read_body)

  COMMENT_JSON=$(gh_rest "repos/${REPO}/pulls/comments/${CID}")
  ROOT_CID=$(jq -er '(.in_reply_to_id // .id) | tostring' <<<"${COMMENT_JSON}")

  # The reply endpoint is not idempotent. Refuse when the thread already ends
  # with our reply, so a retried call cannot post the same answer twice.
  if [ "${FORCE}" != 1 ]; then
    LAST_AUTHOR=$(fetch_pages "repos/${REPO}/pulls/${PR_ID}/comments?per_page=100" \
      | jq -r --arg root "${ROOT_CID}" '
          [.[][] | select(((.in_reply_to_id // .id) | tostring) == $root)]
          | max_by(.created_at)
          | .user.login // ""
        ')
    if [ "${LAST_AUTHOR}" = "${GH_USER}" ]; then
      printf 'pr-ops: thread %s already ends with a reply from %s; not posting (use --force)\n' \
        "${ROOT_CID}" "${GH_USER}" >&2
      exit 3
    fi
  fi

  REPLY_JSON=$(gh_rest --method POST \
    "repos/${REPO}/pulls/${PR_ID}/comments/${ROOT_CID}/replies" \
    -f body="${REPLY_BODY}")

  REPLY_ID=$(jq -er \
    --arg root "${ROOT_CID}" \
    --arg body "${REPLY_BODY}" \
    --arg user "${GH_USER}" '
      select(
        ((.in_reply_to_id | tostring) == $root) and
        (.body == $body) and
        (.user.login == $user)
      )
      | .id
    ' <<<"${REPLY_JSON}")

  jq -c --arg root "${ROOT_CID}" '{reply_id: .id, root_comment_id: $root, url: .html_url}' \
    <<<"${REPLY_JSON}"
  : "${REPLY_ID}"
}

# --- 2. react -----------------------------------------------------------------

cmd_react() {
  need_cid "${CID}" "--comment"
  local REACTION REACTION_JSON REACTION_ID
  # The reaction says whether we agree with the substance of the finding.
  case "${VERDICT}" in
    VALID|'OUT OF SCOPE'|OUT_OF_SCOPE) REACTION='+1' ;;
    INVALID)                           REACTION='-1' ;;
    *) printf 'Unknown verdict: %s\n' "${VERDICT}" >&2; exit 2 ;;
  esac

  REACTION_JSON=$(gh_rest --method POST \
    "repos/${REPO}/pulls/comments/${CID}/reactions" \
    -f content="${REACTION}")

  REACTION_ID=$(jq -er \
    --arg content "${REACTION}" \
    --arg user "${GH_USER}" '
      select(.content == $content and .user.login == $user)
      | .id
    ' <<<"${REACTION_JSON}")

  jq -nc --arg id "${REACTION_ID}" --arg content "${REACTION}" --arg cid "${CID}" \
    '{reaction_id: ($id | tonumber), content: $content, comment_id: $cid}'
}

# --- 3. resolve ---------------------------------------------------------------

cmd_resolve() {
  need_pr
  [ -n "${CIDS// /}" ] || die "resolve needs at least one comment ID"
  local THREADS_JSON COMMENT_JSON ROOT_CID THREAD_ID RESOLVE_JSON cid
  for cid in ${CIDS}; do need_cid "${cid}" "comment ID"; done

  THREADS_JSON=$(gh api graphql --paginate --slurp \
    -f owner="${OWNER}" \
    -f repo="${NAME}" \
    -F pr="${PR_ID}" \
    -f query='
      query(
        $owner: String!
        $repo: String!
        $pr: Int!
        $endCursor: String
      ) {
        repository(owner: $owner, name: $repo) {
          pullRequest(number: $pr) {
            reviewThreads(first: 100, after: $endCursor) {
              nodes {
                id
                comments(first: 1) {
                  nodes { fullDatabaseId }
                }
              }
              pageInfo { hasNextPage endCursor }
            }
          }
        }
      }
    ')

  for cid in ${CIDS}; do
    COMMENT_JSON=$(gh_rest "repos/${REPO}/pulls/comments/${cid}")
    ROOT_CID=$(jq -er '(.in_reply_to_id // .id) | tostring' <<<"${COMMENT_JSON}")

    THREAD_ID=$(jq -er --arg cid "${ROOT_CID}" '
      [
        .[].data.repository.pullRequest.reviewThreads.nodes[]
        | select(
            ((.comments.nodes[0].fullDatabaseId | tostring) == $cid)
          )
      ]
      | if length == 1 then .[0].id
        elif length == 0 then error("review thread not found")
        else error("multiple review threads matched")
        end
    ' <<<"${THREADS_JSON}")

    RESOLVE_JSON=$(gh api graphql \
      -f threadId="${THREAD_ID}" \
      -f query='
        mutation($threadId: ID!) {
          resolveReviewThread(input: {threadId: $threadId}) {
            thread { id isResolved }
          }
        }
      ')

    jq -e --arg threadId "${THREAD_ID}" '
      .data.resolveReviewThread.thread
      | select(.id == $threadId and .isResolved == true)
    ' <<<"${RESOLVE_JSON}" >/dev/null

    jq -nc --arg cid "${cid}" --arg thread "${THREAD_ID}" \
      '{comment_id: $cid, thread_id: $thread, resolved: true}'
  done
}

# --- top-level comment (answers feedback that has no inline thread) -----------

cmd_comment() {
  need_pr
  [ -n "${ACKS// /}" ] || die "comment needs at least one --ack ID"
  local id body marker ISSUE_COMMENTS_JSON POST_JSON ack_json
  for id in ${ACKS}; do
    case "${id}" in
      pullrequestreview-[0-9]*|issuecomment-[0-9]*)
        case "${id#*-}" in *[!0-9]*) die "bad --ack ID: ${id}" ;; esac ;;
      *) die "--ack takes pullrequestreview-N or issuecomment-N, not ${id}" ;;
    esac
  done
  # shellcheck disable=SC2086 # ACKS is a space-separated list of checked IDs.
  ack_json=$(printf '%s\n' ${ACKS} | jq -R . | jq -sc 'unique')
  body=$(read_body)
  marker="<!-- babysit-pr:ack $(jq -r 'join(" ")' <<<"${ack_json}") -->"
  body="${body}"$'\n\n'"${marker}"

  if [ "${FORCE}" != 1 ]; then
    ISSUE_COMMENTS_JSON=$(fetch_pages "repos/${REPO}/issues/${PR_ID}/comments?per_page=100")
    if jq -e --arg user "${GH_USER}" --argjson want "${ack_json}" '
        [
          .[][]
          | select(.user.login == $user)
          | .body
          | scan("<!-- babysit-pr:ack ([^>]*?) -->")
          | .[0]
          | splits(" +")
        ] as $done
        | all($want[]; . as $id | $done | index($id) != null)
      ' <<<"${ISSUE_COMMENTS_JSON}" >/dev/null; then
      printf 'pr-ops: every --ack ID is already answered by %s; not posting (use --force)\n' \
        "${GH_USER}" >&2
      exit 3
    fi
  fi

  POST_JSON=$(gh_rest --method POST \
    "repos/${REPO}/issues/${PR_ID}/comments" \
    -f body="${body}")

  jq -ec --arg user "${GH_USER}" --arg body "${body}" '
    select(.user.login == $user and .body == $body)
    | {comment_id: .id, url: .html_url}
  ' <<<"${POST_JSON}"
}

# --- 4. retrigger -------------------------------------------------------------

cmd_retrigger() {
  need_pr
  [ -n "${TRIGGER_COMMENT}" ] || die "retrigger needs --trigger"
  local ISSUE_COMMENTS_JSON REVIEWS_JSON REVIEW_COMMENTS_JSON LAST_TRIGGER_TIME
  local LAST_REVIEWER_ISSUE_COMMENT LAST_REVIEWER_REVIEW LAST_REVIEWER_INLINE_COMMENT
  local LAST_REVIEWER_ACTIVITY TRIGGER_ACTIVE TRIGGER_TIME POST_JSON POSTED

  ISSUE_COMMENTS_JSON=$(fetch_pages \
    "repos/${REPO}/issues/${PR_ID}/comments?per_page=100")
  REVIEWS_JSON=$(fetch_pages \
    "repos/${REPO}/pulls/${PR_ID}/reviews?per_page=100")
  REVIEW_COMMENTS_JSON=$(fetch_pages \
    "repos/${REPO}/pulls/${PR_ID}/comments?per_page=100")

  LAST_TRIGGER_TIME=$(jq -r \
    --arg user "${GH_USER}" \
    --arg body "${TRIGGER_COMMENT}" '
      [.[][] | select(.user.login == $user and .body == $body)]
      | max_by(.created_at).created_at // ""
    ' <<<"${ISSUE_COMMENTS_JSON}")

  LAST_REVIEWER_ISSUE_COMMENT=$(jq -r --arg user "${GH_USER}" '
    [.[][] | select(.user.login != $user) | .created_at]
    | max // ""
  ' <<<"${ISSUE_COMMENTS_JSON}")

  LAST_REVIEWER_REVIEW=$(jq -r --arg user "${GH_USER}" '
    [
      .[][]
      | select(.user.login != $user and .submitted_at != null)
      | .submitted_at
    ]
    | max // ""
  ' <<<"${REVIEWS_JSON}")

  LAST_REVIEWER_INLINE_COMMENT=$(jq -r --arg user "${GH_USER}" '
    [.[][] | select(.user.login != $user) | .created_at]
    | max // ""
  ' <<<"${REVIEW_COMMENTS_JSON}")

  LAST_REVIEWER_ACTIVITY=$(jq -nr \
    --arg issue "${LAST_REVIEWER_ISSUE_COMMENT}" \
    --arg review "${LAST_REVIEWER_REVIEW}" \
    --arg inline "${LAST_REVIEWER_INLINE_COMMENT}" '
      [$issue, $review, $inline]
      | map(select(length > 0))
      | max // ""
    ')

  TRIGGER_ACTIVE=$(jq -nr \
    --arg trigger "${LAST_TRIGGER_TIME}" \
    --arg activity "${LAST_REVIEWER_ACTIVITY}" '
      ($trigger != "") and
      ($activity == "" or $activity < $trigger)
    ')

  if [ "${TRIGGER_ACTIVE}" = true ]; then
    TRIGGER_TIME="${LAST_TRIGGER_TIME}"
    POSTED=false
    printf 'Trigger already active at %s -- reusing it.\n' "${TRIGGER_TIME}" >&2
  else
    POST_JSON=$(gh_rest --method POST \
      "repos/${REPO}/issues/${PR_ID}/comments" \
      -f body="${TRIGGER_COMMENT}")

    TRIGGER_TIME=$(jq -er \
      --arg user "${GH_USER}" \
      --arg body "${TRIGGER_COMMENT}" '
        select(.user.login == $user and .body == $body)
        | .created_at
      ' <<<"${POST_JSON}")
    POSTED=true
    printf 'Posted new trigger at %s.\n' "${TRIGGER_TIME}" >&2
  fi

  jq -nc --arg t "${TRIGGER_TIME}" --argjson posted "${POSTED}" \
    '{trigger_time: $t, posted: $posted}'
}

case "${COMMAND}" in
  status) cmd_status ;;
  wait) cmd_wait ;;
  reply) cmd_reply ;;
  react) cmd_react ;;
  resolve) cmd_resolve ;;
  comment) cmd_comment ;;
  retrigger) cmd_retrigger ;;
  *) usage >&2; exit 2 ;;
esac
