---
name: seedream5-prompt-enhance
description: "Turn a rough image idea, edit request or reference-image brief into one ready-to-paste prompt for ByteDance Seedream 5.0 pro, 5.0 flash, 5.0 lite or a later 5.x model (Seedream 5.5 and on), following ByteDance's official ModelArk / Volcengine Ark prompt guides, plus the few API settings the request depends on. Use whenever the user types /seedream5-prompt-enhance or asks to write, improve, enhance, fix or translate a Seedream, Doubao Seedream (豆包) or Dola Seedream prompt, or wants a poster, infographic, product shot, portrait, UI mockup, sticker sheet, image edit, multi-reference composite or layer split prepared for Seedream via BytePlus, Volcengine, Jimeng (即梦) / Dreamina, WaveSpeed, fal, Replicate, Runware, Atlas Cloud, OpenRouter or another host, even if they don't name this skill. Not for Seedance video prompts or questions about pricing, quotas or API errors."
license: AGPL-3.0-or-later
metadata:
  author: edbfi
  version: "1.0.0"
  vendor: seedream
  upstream: "BytePlus ModelArk / Volcengine Ark Seedream 4.0-5.0 prompt guide, Seedream 5.0 pro / flash tutorial and interactive editing guide, Image generation API (retrieved 2026-11-08)"
---

# Seedream 5.x prompt enhance

Writes one prompt that Seedream 5.x can act on directly, following ByteDance's official guidance
for the 5.0 family. The condensed guidance, the capability table and every official example prompt
are in [references/official-guide.md](references/official-guide.md); read it when you need a
model limit, the exact coordinate or size rules, a host's parameter names, or the official wording
for a task type. Where reseller advice and ByteDance's docs differ, ByteDance's docs win.

## What "enhance" means here

Seedream runs its own prompt optimization (`optimize_prompt_options`, `standard` by default), and
ByteDance's guide says concise, precise prompts beat piles of ornate words. So the value of this
step is not length. It is:

1. **Structure the model reads well**: for new images, purpose and format first, then subject,
   action and setting, then composition, light, palette and style, then rendered text and
   constraints. Edits and layer splits lead with the operation instead.
2. **The syntax the model actually supports**: quoted text, `Image N` bindings, `<point>` /
   `<bbox>` tags, keep-unchanged clauses, aspect ratio in words.
3. **Filling the gaps that change the result**: where the user left format, composition or light
   open, choose concrete values a good art director would choose for that purpose.
4. **Routing to the right capability**: noticing when a request needs a parameter (layer
   decomposition, a set of images, a size) or something the target model can't do.

### What stays locked

These come from the user and are carried over exactly: subjects and their counts, actions and
relationships, named styles, colours (including hex codes), positions, every piece of text to
render, coordinates, the role the user gave each reference image, and anything they asked to keep
or exclude. Enhancement adds around these; it never swaps, drops or contradicts them.

### What you may add

- A purpose and format line when the request implies one ("for my bakery's opening" → a
  promotional poster).
- Composition and layout: framing, viewpoint, where things sit, reading order for designed pieces.
- Light (direction, hardness, colour), materials ("matte ceramic", "brushed steel") and palette,
  chosen to fit the purpose and the style the user named.
- The aspect ratio or shape in words, when the user gave one or the purpose fixes it (a phone
  wallpaper is vertical).
- **One central visual motif, only when the user named no visual subject at all** ("a poster for
  our book swap"): pick a single simple motif that fits the purpose (a stack of worn paperbacks
  tied with twine). When the user named a subject, add no other subjects or props beside it.

### What you never add

- Quoted text the user didn't write: no invented slogans, prices, dates, addresses or brand names.
  Arrange the user's own words; if a design clearly needs copy they didn't give, leave it out and
  add a `Note:` saying where it would go. The exception is content the user asked the model to
  produce: an infographic's factual labels, sample text in a wireframe render, a translation.
  Describe those by kind, without quotes ("each species labelled with its English and Chinese
  name").
- Quality boilerplate ("8K, masterpiece, best quality, ultra-detailed, trending on artstation")
  and stock negative lists. Seedream has no negative-prompt field; write only the exclusions the
  user asked for, as short plain sentences inside the prompt.
- Details of reference images you can't see, including assumed parts ("its cap and label"). Bind
  them by role and say what to take from them. If an image is attached and you can see it, use
  what you see to name targets unambiguously.
- Reference images the user didn't mention. If one would help (a mascot that must stay
  consistent), suggest it in the `Note:` line instead of writing `Image 1` into the prompt.
- The look of something the user already owns but didn't describe ("our mascot", "my dog", "our
  product"). Name it plainly ("the red panda mascot") and say in the `Note:` that a reference
  image or a short description would lock it.
- Characters, story or symbolism the user didn't ask for.

Rough size: most text-to-image prompts land around 40 to 150 words. Dense infographics, UI
mockups and multi-element scenes may need more; stay under ByteDance's recommended ceiling of 600
English words or 300 Chinese characters, beyond which the model starts dropping details.

## Pick the target model

Use the model the user names. If they name none, write for **5.0 pro / flash**: they share every
prompt feature and differ only in quality versus speed and cost, so one prompt serves both.

| Need | pro / flash | lite |
|---|---|---|
| Several images in one request (a set, series, storyboard) | not supported | `sequential_image_generation: auto`, up to 15 |
| `<point>` / `<bbox>` coordinates, layer decomposition | yes | no (marks drawn on the image still work) |
| Transparent background (`background: transparent`) | only when editing exactly one input PNG that already has alpha | no |
| Reference images | up to 10 | up to 14 |
| Prompt languages | Chinese, English + 14 more; native text rendering in those languages | Chinese and English |
| `size` | tiers `1K` / `1.5K` / `2K` (default `2K`) | tiers `2K` / `3K` / `4K`; **default is square `2048x2048`** |

**Transparent output from text.** For a logo or sticker "on a transparent background", don't set
`background`: the API rejects it for text-to-image. Ask for the subject isolated on a plain, flat
background in the prompt and say in a `Note:` that the alpha cut-out is a second pass (for
example, layer decomposition of the result on pro / flash).

**Later 5.x models (5.5 and on)**: plain natural-language guidance carries over, so write the same
way. Treat capability-dependent syntax and settings (sets, coordinates, layers, transparency,
languages, sizes) as unverified until that version's official tutorial on BytePlus ModelArk or
Volcengine Ark confirms them. If you have web access, check it; if you can't, use only plain
prompting for those needs and say in a `Note:` what you couldn't confirm.

## Workflow

### 1. Classify the task

| Task | What the prompt must carry |
|---|---|
| Text-to-image, photo or art | Purpose/format, subject + action + setting, composition, light, style |
| Designed piece (poster, logo, cover, packaging) | Purpose/format first, layout as a handoff (regions in reading order and what fills each), every user string quoted with its position and hierarchy |
| Knowledge visual (infographic, diagram, formula, chart, UI mockup) | Precise technical terms, the visualization form (named chart types and counts), layout and style; user titles quoted, generated labels described by kind |
| Edit of one image | The operation and the target named unambiguously, the change, and what stays unchanged |
| Region edit | The region as the user gave it (marks, words or coordinates), the change, what stays unchanged, "remove the marks" when the marks were drawn on the image |
| References (identity, product, style, outfit) | For each image: what to take from it. Then the new scene |
| Sketch, wireframe, floor plan → render | "Based on this <sketch>", the target result, what must match the source, "generate from the text in the image" if it has notes, drop sketch lines |
| Layer decomposition | `layer_decomposition: true`, one image; prompt names the elements or boxes them, or is omitted |
| Several images | lite: a set prompt. pro / flash: see "Sets on pro and flash" |

### 2. Lock the contract

List for yourself (not in the reply): subjects and counts, every string to render, the user's
style and colour words, positions, exclusions, the reference images with their roles,
coordinates, and the stated aspect ratio, size or purpose. Everything here must appear in the
prompt unchanged.

### 3. Write the prompt

For new images: **purpose and format → subject, action, setting → composition and layout →
light, material, palette → style → text to render → constraints**. For edits and layer splits:
**operation and target → change → what stays unchanged**. Write connected sentences, not a comma
list of tags. One idea per sentence keeps instructions from bleeding into each other.

**Text to render.** Put each string in straight double quotes and give it a position and role
("the headline "Brilla sin límites" across the top in a tall serif"). Strings the user quoted are
kept exactly, script and diacritics included. Text taken from their unquoted words may be trimmed
or re-cased ("grand opening this Saturday" → "Grand Opening", "Saturday") but never gains words.
For a language other than the prompt's, name the language once. Keep strings short; long fine
print renders worst, and ByteDance says fine text is still a weak spot.

**Aspect ratio and size.** ByteDance's recommended sizing is a resolution tier in `size` plus the
ratio or shape described in the prompt, so write it in words ("a vertical 9:16 phone wallpaper", "a
wide 21:9 banner"). On lite, also add a tier (`size: 2K`) to `Settings:`: the docs list a square
`2048x2048` default, and a tier lets the ratio in the prompt apply. Emit `size: WIDTHxHEIGHT` only
when the user asked for exact *output* pixels and they fit the model's range (pro / flash 921,600 to
4,624,220 total pixels; lite 3,686,400 to 16,777,216; ratio 1/16 to 16). Otherwise use a tier plus
the ratio in words, and say in a `Note:` that the final pixels need a resize. Never copy an input
image's dimensions into `size`; for edits that must keep the frame, write "keep the framing and
aspect ratio of Image 1". On hosts with an aspect-ratio control, the two must agree.

**Exclusions.** Only what the user asked to exclude, as short sentences: "No people in the frame.",
"No text other than the title." Don't repeat the positive description in negative form.

### 4. Bind references and regions

- Number images `Image 1`, `Image 2`, … in the order they are passed to the API, and keep the
  user's numbering. Chinese prompts use `图1`, `图2`. If the user names a host whose docs use
  another word (fal's examples say `Figure 1`), either works; keep one form throughout.
- One binding per subject: "The woman's face and hairstyle come from Image 1. The jacket comes from
  Image 2." When two references look alike, add a content word to the number ("the walnut desk in
  Image 3").
- For edits, end with what stays the same, scoped to the request: "Keep her pose, the lighting and
  the background unchanged." A bare "keep everything else the same" is fine for small edits.
- Name the target so no pronoun is ambiguous: "the tallest panda", "the person on the left".

Coordinates (pro / flash):

- `<point>x y</point>` or `<bbox>x1 y1 x2 y2</bbox>`, integers 0 to 999 on that image, top-left
  origin, `x1 < x2`, `y1 < y2`. This skill writes the image first:
  `Image 1 <bbox>120 180 640 760</bbox>`.
- Keep the user's normalized numbers exactly. If they gave pixels and the image size, convert with
  `round(px / size * 1000)` and clamp to 999. Never invent coordinates; if the user described the
  place in words, write it in words.
- When a box holds several things, name the target inside it. To protect an area, box it and say
  it stays unchanged.

### 5. Sets on pro and flash

Pro and flash return one image per request. When the user wants several images:

- **They want one sheet** (a storyboard, sticker sheet, icon grid, contact sheet): write one prompt
  for a single image laid out as an N-panel grid, describing panels in reading order.
- **They want separate files** (wallpapers, calendar months, ad variants): give each image its own
  ready-to-paste code block that repeats the shared base description and changes only the varying
  part, and say in a `Note:` that each is a separate request. If a character must stay
  consistent, add to the `Note:` that passing the user's artwork (or the first result) as a
  reference, with "The <character> comes from Image 1" added to each prompt, keeps it the same.
  Don't write that sentence into the prompts unless the user already has the reference.
- If they'd be better served by lite's native sets, mention it in the `Note:` line.

On lite, write the set request directly ("Generate a set of four …") and add
`sequential_image_generation: auto` and `sequential_image_generation_options.max_images: N` to
`Settings:` (reference images + N ≤ 15).

### 6. Check before delivering

- Every locked item is present and unchanged; quoted strings match the user's words, with
  user-quoted strings character for character.
- No invented copy, brands, references or extra subjects; no quality boilerplate.
- New images open with purpose or format; edits and layer splits open with the operation.
  Sentences, not a tag list.
- Reference numbers match the user's; each image has one stated role.
- Coordinates, if any, are valid and tied to an image.
- Edits name what stays unchanged.
- Every setting is valid for the target model (size range, transparency rules, sets on lite only).
- Under 600 English words / 300 Chinese characters.

## Reply format

Reply with the prompt in a `text` code block, then only the lines that apply:

````markdown
```text
<the prompt>
```

Settings: <API settings the prompt depends on, e.g. `size: 1.5K` · `layer_decomposition: true` · `sequential_image_generation: auto`>
Note: <one or two sentences: a capability limit, missing copy, input requirements, a separate-request plan, or an assumption that matters>
````

- No preamble, no explanation of the changes, no alternatives unless the user asked for options.
- `Settings:` holds parameters only, and only when they matter beyond the target model's defaults.
  Name them as ByteDance's API does; if the user said which host they use, use its names and
  endpoints (see the reseller section of the reference; fal and WaveSpeed, for example, have a
  separate layer-decomposition endpoint instead of a flag). Input requirements go in `Note:`.
- If the host forbids a prompt for the task (Runware's layer decomposition takes no
  `positivePrompt`), skip the code block and reply with the `Settings:` and `Note:` lines only;
  carry the user's element choices over only where that host accepts them.
- For several separate images, give each its own code block with a plain label above it
  (`Request 1: Spring`). Never label them `Image N`; that name belongs to reference images.
- **Language**: write the prompt in the language the user asked for; otherwise in the language of
  a draft prompt they pasted; otherwise in the language of their message. Fall back to English when
  the target model doesn't support that language. Pro / flash adapt faces, architecture and
  clothing to the prompt language, so when the scene's culture differs from the user's language
  (a Parisian café requested in Korean), prefer English. Quoted strings always stay in their
  original language.
- Ask a question only when the answer changes the core result and the request allows several
  equally good readings; then ask one question covering every doubt. Style, light and layout are
  never reasons to ask.

## Examples

Illustrative runs built on the official patterns.

**Text-to-image, designed piece.** Request: "poster for my bakery Golden Crumb, grand opening this
Saturday, cozy vibe, vertical"

```text
A vertical 3:4 promotional poster for the grand opening of a neighbourhood bakery. In the centre, a golden, crackled sourdough loaf rests on a flour-dusted wooden board, lit by warm low morning light from the left with soft shadows. Cream and toasted-brown palette with a hand-painted, cozy feel. Across the top, the bakery name "Golden Crumb" in a large rounded serif; below the bread, "Grand Opening" and then "Saturday" in smaller lettering.
```

**Region edit with coordinates.** Request: "Seedream 5 pro, Image 1 is my living room, box
120 180 640 760 is the old sofa, swap it for a green velvet one, keep the rest"

```text
Replace the sofa in Image 1 <bbox>120 180 640 760</bbox> with a deep green velvet sofa of similar size, facing the same way. Keep the walls, floor, other furniture, lighting and camera angle unchanged.
```

**Layer split.** Request: "split my poster into layers, I want the title, the woman and the logo
separately"

```text
Decompose the title text, the woman and the logo in Image 1 into separate layers.
```

Settings: `layer_decomposition: true`
Note: Pass the poster as the only input image (png or jpeg, at least 262,144 pixels, e.g. 512x512).

More official prompts for every task type are in
[references/official-guide.md](references/official-guide.md).
