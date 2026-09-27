# Delegation

The coordinator plans, assigns, merges, ranks, rechecks and publishes. Workers do bounded browsing or analysis and return a worker file. Worker completion alone is not proof of coverage: the coordinator reconciles every assignment against the ledger.

## Roles

| Role | Scope of one assignment | Reads | Returns |
|---|---|---|---|
| Listing reader | A contiguous range of listing pages | [discovery](research-method.md#discovery-and-thread-reading) | `listings` and `threads` rows |
| Thread reader | A set of unread discussion IDs | [discovery](research-method.md#discovery-and-thread-reading) | `threads` rows, new `providers` rows with coupons and links, provisional `candidates` |
| Provider investigator | One provider, with all its known threads, links and coupons | [provider investigation](research-method.md#provider-investigation) | `providers` outcome, provisional `candidates` |
| Finalist verifier | One or a few shortlisted candidates | [purchase verification](research-method.md#shortlisting-and-purchase-verification), [pricing](research-method.md#pricing-and-currency) | verified or blocked `candidates`, `gaps` |

Every worker also reads [worker files](workspace.md#worker-files) and the ego-browser skill.

The coordinator keeps listing-batch planning, provider deduplication, FX rates, the stopping rule, rechecks and the report. Give each provider's catalogue and cart work to exactly one owner at a time, handing over everything already known about it so nothing is investigated twice.

## Sizing and parallelism

- Keep assignments bounded and non-overlapping: roughly 10-25 threads per thread reader, one provider per investigator (batch several tiny providers together if they have no plausible qualifying plan), a few finalists per verifier.
- Choose the number of workers, models and reasoning settings from the workload and cost. Routine browsing and extraction suit faster models; purchase verification, policy interpretation and ranking deserve the strongest reasoning.
- Register every assignment in `assignments.csv` as `pending`, set it `active` when handed out, and `complete` or `blocked` after merging.

## ego-browser: one TaskSpace, owned Pages

- The coordinator creates the single TaskSpace for the whole goal and records its `spaceId` in `STATUS.md`. Workers resume that space by ID; nobody creates another space, even to recover from a stuck Page.
- Each worker is assigned specific Page labels (`p2`, `p3`, ...) recorded in the assignment's `pages` column. A Page has exactly one owner at a time and is never operated by two agents concurrently. Workers reuse their Pages with `goto()` rather than opening new ones.
- Respect the runtime's Page budget: never have more concurrent browsing workers than Pages available. If concurrent browsing turns out unsafe or unavailable, serialize browsing and parallelize only the analysis of saved evidence.
- Workers never call `finish()`. The coordinator finishes the TaskSpace once, after every worker is done.

## Worker brief

Give each worker a compact brief rather than the whole skill, conversation or ledger:

```
You are a <role> for let-vps-scout run <run folder>.
Assignment: <id> (<scope>)
Brief: <effective requirements, one paragraph>
Known inputs: <thread IDs / provider links / coupons / candidate IDs>
ego-browser: TaskSpace <spaceId>, your Pages: <labels>. Read the ego-browser skill first.
Read: <skill dir>/references/<file>#<section>, <skill dir>/references/workspace.md#worker-files
Write only: <run>/workers/<id>_<type>_<scope>.md and <run>/evidence/<your scope>/
Never: buy, submit orders, create accounts, enter personal or payment data, contact providers, finish the TaskSpace.
Return: the worker file path and a two-line summary.
```

## What comes back

Workers return the worker file path and a very short summary: new contenders, blockers, and unresolved gaps. Supporting page text stays in `evidence/`. Avoid relaying full page text, the complete ledger or long narratives between agents; it wastes context and invites drift between copies.
