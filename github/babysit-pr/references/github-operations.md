# GitHub PR Review Bot Operations

This is the contract that `scripts/pr-ops.sh` implements. Use the script; read this file when a
call fails, when you need to check exactly what a call asserts, or when you have to perform an
operation by hand.

| Section | Script command |
|---|---|
| 1. Reply to an inline review comment | `reply --comment CID` (body on stdin) |
| 2. Add the verdict reaction | `react --comment CID --verdict V` |
| 3. Resolve the matching review threads | `resolve CID [CID...]` |
| 4. Post or reuse the retrigger comment | `retrigger --trigger TEXT` |

The script keeps every API call and `jq` assertion below unchanged. It differs from the snippets
only in these deliberate ways:

- `reply` refuses (exit 3) when the thread already ends with a reply from `GH_USER`, because the
  reply endpoint is not idempotent and a retried call would otherwise post the answer twice.
- An unknown verdict in `react` is a usage error, so the script exits 2 rather than section 2's
  `exit 1`.
- `comment --ack ID` posts a top-level PR comment for feedback that has no inline thread, with a
  hidden `<!-- babysit-pr:ack ID ... -->` marker. `status` uses the markers to hide answered
  feedback until its author edits it, and `comment` refuses (exit 3) to answer IDs whose latest
  revision is already answered.

---

This is the narrow, agent-facing reference for the four GitHub operations in the code-review
loop: reply to an inline comment, add the verdict reaction, resolve its review thread, and post or
reuse the retrigger comment.

## Shared setup

```bash
set -euo pipefail

# Required inputs:
# REPO="owner/repo"
# PR_ID="123"
# TRIGGER_COMMENT="<exact trigger text the repository documents>"

GH_API_VERSION="2026-03-10"
GH_USER=$(gh api user --jq '.login')
OWNER=${REPO%%/*}
NAME=${REPO#*/}

gh_rest() {
  gh api \
    -H 'Accept: application/vnd.github+json' \
    -H "X-GitHub-Api-Version: ${GH_API_VERSION}" \
    "$@"
}
```

Use `--method POST` explicitly for writes. Use `-f` for string fields and `-F` only for typed
numeric/boolean fields. A successful `gh api` call is not enough: every write below asserts the
returned actor, value, and target with `jq -e`.

## 1. Reply to an inline review comment

Use the dedicated reply endpoint. GitHub's supported contract requires the top-level comment ID,
so normalize a reply ID through `in_reply_to_id` first.

```bash
# Inputs: CID, REPLY_BODY
COMMENT_JSON=$(gh_rest "repos/${REPO}/pulls/comments/${CID}")
ROOT_CID=$(jq -er '(.in_reply_to_id // .id) | tostring' <<<"${COMMENT_JSON}")

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
```

This operation is **not idempotent**: every call creates another reply. Invoke it once per newly
processed comment. Do not use the older generic create-comment form with `in_reply_to`; the
dedicated `/comments/{comment_id}/replies` route expresses the operation exactly.

## 2. Add the verdict reaction

React to the exact review comment (`CID`), not the normalized root comment.

```bash
case "${VERDICT}" in
  VALID)            REACTION='+1' ;;
  INVALID)          REACTION='-1' ;;
  'OUT OF SCOPE')   REACTION='confused' ;;
  *) printf 'Unknown verdict: %s\n' "${VERDICT}" >&2; exit 1 ;;
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
```

Creating the same reaction again is idempotent: GitHub returns the existing reaction (`200`) rather
than creating a duplicate (`201`). It does not remove a previously added opposite reaction.

## 3. Resolve the matching review threads

REST exposes review-comment IDs; GraphQL resolves thread node IDs. Fetch all thread pages once,
map each processed comment to its root comment, then resolve the matching thread. Using
`fullDatabaseId` avoids GraphQL `Int`-width assumptions.

```bash
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

for CID in "${PROCESSED_COMMENT_IDS[@]}"; do
  COMMENT_JSON=$(gh_rest "repos/${REPO}/pulls/comments/${CID}")
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
done
```

`--paginate` requires the `$endCursor` variable and `pageInfo` selection. `--slurp` is also required:
it turns the separately emitted page objects into the outer array consumed by `.[]`. Resolving an
already resolved thread is idempotent.

## 4. Post or reuse the retrigger comment

The GitHub API is the state store. A trigger is active when the latest exact trigger from
`GH_USER` exists and no non-self issue comment, submitted PR review, or inline review comment is
newer. Exact equality (`.body == $body`) is intentional; do not interpret the trigger as a regex.

```bash
fetch_pages() {
  gh_rest "$1" --paginate --slurp
}

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
  printf 'Trigger already active at %s -- reusing it.\n' "${TRIGGER_TIME}"
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

  printf 'Posted new trigger at %s.\n' "${TRIGGER_TIME}"
fi
```

`TRIGGER_TIME` always comes from GitHub's `created_at`, never the local clock. GitHub timestamps use
a lexically sortable UTC representation. Strict `<` makes equal-second reviewer activity
conservatively invalidate the old trigger. Including inline comments covers standalone inline
replies that may not produce a later submitted-review timestamp.

## Verified behavior

Validated on 2026-07-20 with GitHub CLI 2.96.0 against a disposable PR:

- multiline inline reply preserved exactly and targeted the normalized root comment;
- `+1` and `-1` reactions succeeded, and repeating a reaction produced no duplicate;
- root/reply comment IDs mapped to one thread, and repeated resolution remained resolved;
- a trigger containing regex metacharacters was posted once and reused on re-entry;
- the `jq` filters passed empty, multi-page, older/equal/newer timestamp, and missing/duplicate-thread
  fixtures.

Official contracts: [review-comment replies](https://docs.github.com/en/rest/pulls/comments),
[review-comment reactions](https://docs.github.com/en/rest/reactions/reactions),
[GraphQL mutations](https://docs.github.com/en/graphql/reference/mutations), and
[issue comments](https://docs.github.com/en/rest/issues/comments).
