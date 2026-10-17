# Review

Every new or refreshed pack is reviewed before delivery. Validators prove structure; review proves
the content is right and deep enough. Use an independent context when one is available: a worker
that receives the pack, its `facts/` and `outline/` files and this rubric, with research tools to
open cited sources. When none is available, review in the current context against the same rubric
and record `"independent": false` in `pack.json`.

## Rubric

1. **Claims.** Open the cited source for every MUST and MUST NOT rule, every `Outdated`
   anti-pattern and every `Breaking` or `Removed` change item. Confirm the source says it, for the
   documented version. Spot-check at least one recommendation per topic file the same way.
2. **Currency.** Nothing recommends an API, option or pattern that the covered window deprecated or
   removed. Every "since X.Y" annotation matches the release notes.
3. **Depth.** Every concept in `outline/<component>.md` is covered by a topic, an extra topic or an
   `na` with a reason. For each topic file, answer: could an agent implement ordinary work in this
   area correctly from this file alone? A section with a single generic recommendation where the
   official documentation has a chapter fails this test.
4. **Examples.** Verified blocks show the recommended pattern in full; `Do instead` blocks really
   replace their `Don't` blocks.
5. **Routing.** From `README.md`, every topic file is reachable in one step, and the "Where to look"
   tasks are phrased the way an agent would look for them.
6. **Seams** (stacks). Every seam file says which side owns what and shows the wiring; every
   component edge's reason is accurate.

Record findings in `review/<pack-id>.md`. Fix each finding, rerun the validators, and list anything
deliberately left open in `review.open_items`; a non-empty list triggers the next refresh.
