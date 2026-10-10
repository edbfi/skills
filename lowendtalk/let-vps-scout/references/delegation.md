# Delegation

The coordinator plans, assigns, merges, ranks, rechecks and publishes. Workers do bounded browsing or analysis and return a worker file. Worker completion alone is not proof of coverage: the coordinator reconciles every assignment against the ledger.

## Roles

| Role | Scope of one assignment | Reads | Returns |
|---|---|---|---|
| Listing reader | A contiguous range of listing pages | [discovery](research-method.md#discovery-and-thread-reading) | `listings` and `threads` rows |
| Thread reader | A set of unread discussion IDs | [discovery](research-method.md#discovery-and-thread-reading) | `threads` rows, new `providers` rows with coupons and links, provisional `candidates` |
| Provider investigator | One provider, with all its known threads, links and coupons | [provider investigation](research-method.md#provider-investigation) | `providers` outcome, provisional `candidates` |
| Finalist verifier | One or a few shortlisted candidates | [purchase verification](research-method.md#shortlisting-and-purchase-verification), [pricing](research-method.md#pricing-and-currency) | verified or blocked `candidates`, `gaps` |

Every worker also reads [worker files](workspace.md#worker-files), the run backend's section of [browser backends](browser-backends.md) and that backend's own guide (the ego-browser skill, or `agent-browser skills get core`).

The coordinator keeps listing-batch planning, provider deduplication, FX rates, the stopping rule, rechecks and the report. Give each provider's catalogue and cart work to exactly one owner at a time, handing over everything already known about it so nothing is investigated twice.

## Sizing and parallelism

- Keep assignments bounded and non-overlapping: roughly 10-25 threads per thread reader, one provider per investigator (batch several tiny providers together if they have no plausible qualifying plan), a few finalists per verifier.
- Choose the number of workers, models and reasoning settings from the workload and cost. Routine browsing and extraction suit faster models; purchase verification, policy interpretation and ranking deserve the strongest reasoning.
- Register every assignment in `assignments.csv` as `pending`, set it `active` when handed out, and `complete` or `blocked` after merging.

## Browser contexts

The whole run shares one browser, opened by the coordinator: an ego-browser TaskSpace, or an agent-browser host session that workers attach to over CDP. Each worker owns its own browsing context, recorded in the assignment's `pages` column. For ego-browser that is one or more Page labels (`p2`, `p3`, ...). For agent-browser it is a session name (`letvps-<suffix>-<assignment>`) holding one pinned tab.

- A context has exactly one owner at a time and is never driven by two agents at once. Workers reuse their context for every URL rather than opening new ones.
- Never run more concurrent browsing workers than the browser can hold: ego-browser's Page budget, or about four to six tabs for agent-browser. If concurrent browsing turns out unsafe or unavailable, browse one worker at a time and parallelise only the analysis of saved evidence.
- Workers never tear the browser down. They release only their own context (agent-browser: `tab close`, then `close`, both with `--cdp` so nothing new is launched). The coordinator tears the browser down once, after every worker is done.

The exact commands for each backend are in [browser backends](browser-backends.md).

## Worker brief

Give each worker a compact brief rather than the whole skill, conversation or ledger:

```
You are a <role> for let-vps-scout run <run folder>.
Assignment: <id> (<scope>)
Brief: <effective requirements, one paragraph>
Known inputs: <thread IDs / provider links / coupons / candidate IDs>
Browser: <backend>. ego-browser: TaskSpace <spaceId>, your Pages <labels>. agent-browser: --session <letvps-suffix-A0NN> --cdp <CDP URL>, start with `--pin-tab tab new <url>`.
Read: <skill dir>/references/browser-backends.md#<ego-browser|agent-browser> and that backend's own guide first, then <skill dir>/references/<file>#<section>, <skill dir>/references/workspace.md#worker-files
Write only: <run>/workers/<id>_<type>_<scope>.md and <run>/evidence/<your scope>/
Never: buy, submit orders, create accounts, enter personal or payment data, contact providers, tear down the shared browser, touch another agent's context.
Return: the worker file path and a two-line summary.
```

## What comes back

Workers return the worker file path and a very short summary: new contenders, blockers, and unresolved gaps. Supporting page text stays in `evidence/`. Avoid relaying full page text, the complete ledger or long narratives between agents; it wastes context and invites drift between copies.
