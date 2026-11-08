# Seedream 5.x official guidance (condensed)

Condensed from ByteDance's own documentation, retrieved 2026-11-08. It records what the
documentation says; `SKILL.md` decides how the skill writes prompts from it. Example prompts are
quoted verbatim from the official pages.

Sources:

- BytePlus ModelArk, [Seedream 5.0 pro / flash tutorial](https://docs.byteplus.com/en/docs/ModelArk/seedream-5-0-pro)
  (Volcengine: [Doubao Seedream 5.0 pro / flash 教程](https://docs.volcengine.com/docs/ark/seedream-5-0-pro))
- BytePlus ModelArk, [Seedream 5.0 pro / flash interactive editing guide](https://docs.byteplus.com/en/docs/ModelArk/seedream-5-0-pro-editing-guide)
- BytePlus ModelArk, [Seedream 4.0-5.0 prompt guide](https://docs.byteplus.com/en/docs/ModelArk/seedream-4-0-5-0-prompt-guide)
  (Volcengine: [Seedream 4.0-5.0 提示词指南](https://docs.volcengine.com/docs/ark/seedream-4-0-5-0-prompt-guide),
  whose Chinese text names 5.0 lite explicitly)
- BytePlus ModelArk, [Image generation API](https://docs.byteplus.com/en/docs/ModelArk/1541523)
- ByteDance Seed, [Introducing Seedream 5.0 Pro](https://seed.bytedance.com/en/blog/beyond-generation-it-understands-design-introducing-seedream-5-0-pro)
  (2026-07-08)

Contents:

1. [Models and capabilities](#models-and-capabilities)
2. [General prompt rules](#general-prompt-rules)
3. [Text-to-image](#text-to-image)
4. [Image editing](#image-editing)
5. [Interactive editing with coordinates (pro / flash)](#interactive-editing-with-coordinates-pro--flash)
6. [Reference images and multi-image input](#reference-images-and-multi-image-input)
7. [Sketches, wireframes and floor plans](#sketches-wireframes-and-floor-plans)
8. [Multi-image output (lite only)](#multi-image-output-lite-only)
9. [Layer decomposition (pro / flash)](#layer-decomposition-pro--flash)
10. [Parameters that interact with the prompt](#parameters-that-interact-with-the-prompt)
11. [What resellers add](#what-resellers-add)

## Models and capabilities

| | 5.0 pro | 5.0 flash | 5.0 lite |
|---|---|---|---|
| BytePlus model ID | `dola-seedream-5-0-pro-260628` | `dola-seedream-5-0-flash-260915` | `seedream-5-0-lite-260128` (alias of `seedream-5-0-260128`) |
| Volcengine model ID | `doubao-seedream-5-0-pro-260628` | `doubao-seedream-5-0-flash-260915` | `doubao-seedream-5-0-260128` |
| Positioning | Highest image quality | Faster and cheaper | Earlier 5.0 release (2026-02) |
| Text-to-image, image-to-image, multi-image blending | yes | yes | yes |
| Reference images | up to 10 | up to 10 | up to 14 (inputs + outputs ≤ 15) |
| Interactive editing (`<point>`, `<bbox>`, marks) | yes | yes | marks only (arrows, boxes, doodles) |
| Layer decomposition | yes, base + up to 16 layers | yes | no |
| Transparent background (`background`) | edits of exactly one alpha PNG input | same as pro | no |
| Sequential image generation (sets) | **no**, one image per request | **no** | yes, up to 15 |
| Streaming | no | no | yes |
| Web search tool (`tools: web_search`) | no | no | Volcengine Ark only |
| Prompt languages | Chinese, English + 14 | Chinese, English + 14 | Chinese, English |
| Native text rendering in the 14 extra languages | advertised | advertised | not advertised |
| `size` tiers (default) | 1K, 1.5K, 2K (`2K`) | 1K, 1.5K, 2K (`2K`) | 2K, 3K, 4K (default is pixels: `2048x2048`) |
| `size` in pixels, total range | 921,600 to 4,624,220 | 921,600 to 4,624,220 | 3,686,400 to 16,777,216 |
| `optimize_prompt_options.mode` | `standard`, `fast` | `standard` | `standard` |

The 14 extra languages for pro and flash: Russian, Arabic, Filipino, Thai, Turkish, Korean, Malay,
Spanish, Portuguese, Indonesian, French, German, Vietnamese, Japanese. The Seed blog adds that the
model adapts architecture, faces and clothing to the culture of the prompt language and follows
each script's typography (right-to-left Arabic, Spanish accents such as "PASIÓN").

The Seed blog lists Pro's strengths as dense information visualization (infographics, charts,
timelines, flowcharts, UI mockups) with self-planned layouts, interactive precision editing,
photoreal light and skin, and native multilingual text. It also states the limits: "there is
still room to improve in finer-grained text rendering and pixel-level editing consistency."

## General prompt rules

From the 4.0-5.0 prompt guide; the 5.0 pro / flash tutorial says basic usage is the same as other
Seedream models.

1. **Describe the picture in clear natural language.** Write subject + action + environment in
   concise, coherent sentences. If aesthetics matter, add style, colour, lighting and composition
   in natural language or short phrases.
   - Recommended: "A girl in a lavish dress walking under a parasol along a tree-lined path, in the
     style of a Monet oil painting."
   - Avoid: "Girl, umbrella, tree-lined street, oil painting texture."
2. **State the application and purpose.** When the image has a use, name its purpose and type.
   - Recommended: "Design a logo for a gaming company. The logo features a dog playing with a game
     controller. The company name "PITBULL" is written on it."
   - Avoid: "An abstract image of a dog holding a controller, and the word PITBULL on it."
3. **Use precise style words or a style reference image** when a particular style is needed
   (examples given: picture-book style, children's book illustration style, a style reference
   image).
4. **Put text to render in double quotation marks.**
   - Recommended: "Generate a poster with the title "Seedream 4.5"."
   - Avoid: "Generate a poster titled Seedream 4.5."
5. **For edits, name the target and the change, avoid vague pronouns, and say what stays the
   same.**
   - Recommended: "Dress the tallest panda in pink Peking Opera costume and headgear, keeping its
     pose unchanged."
   - Avoid: "Put that one in pink clothes."

Length (API reference): use no more than 300 Chinese characters or 600 English words. Longer
prompts scatter the information, so the model may drop details and keep only the major elements.

## Text-to-image

Use clear, detailed natural language; for complex images, describe each element to control it.
The guide notes that 4.0 and later understand prompts well enough that **concise, precise prompts
usually beat stacking ornate vocabulary**.

Official detailed example: "A cluttered office desk. On the desk, there is an open laptop with a
screen displaying green code. Next to it, a mug with the word "Developer" on it, with steam rising
from the top. An open book lies on the desk, with pages showing a Venn diagram illustrating the
nesting relationships of three circles in gray, blue, and light green. [...] The background is a
blurred bookshelf. Sunlight shines from the right side, casting light and shadow on the desk."

Another uses spatial order to organize a dense scene: "Interior view of an open refrigerator: Top
shelf: On the left, there is a carton of milk [...] Middle shelf: [...] Bottom shelf: [...] On
the door shelves, there are bottles of ketchup and mayonnaise."

**Knowledge and infographics.** The model turns knowledge and reasoning into dense visuals
(formulas, diagrams, teaching illustrations). Use precise technical terms, and state the
visualization form, layout and style.

- "Draw the following system of binary linear equations and the corresponding solution steps on
  the blackboard: 5x + 2y = 26; 2x -y = 5."
- "Create an infographic showing the causes of inflation. Each cause should be presented
  independently with an icon."

Seed blog examples for Pro name the chart types and counts outright, e.g. an Antarctic research
station infographic with a development timeline, a bar chart comparing five stations, an
energy-source pie chart and a seven-step fieldwork flowchart; or "Generate a natural-science
infographic titled "A Beginner's Guide to Birdwatching"" with a grid of 8 species, each with an
illustration, English and Chinese names and identifying traits.

## Image editing

Supported operations: **add, delete, replace, modify**. Use clear, concise language that points
at the target and the change.

| Operation | Official prompt |
|---|---|
| Add | "Add matching silver earrings and a necklace to the girl in the image" |
| Delete | "Remove the girl's hat." |
| Replace | "Replace the largest bread man with a croissant man, keeping the action and expression unchanged." |
| Modify | "Turn the three robots into transparent crystal, colored red, yellow and green from left to right. Make the green one run, yellow walk, red stand." |

When the target is hard to describe in words, mark it on the image with **arrows, boxes or
doodles** and refer to the marks:

- "Insert a TV where the red area is marked and a sofa where the blue area is marked. Keep the
  original wooden style."
- "Enlarge the title to match the red box and change its style to match the saxophone icon."
- Pro / flash freeform example: "Edit the image based on the hand-drawn sketch. Add a stack of
  realistic magazines or art books in the marked area at the lower left, and add a ceramic cup of
  coffee with a saucer in the marked area on the right. Remove all sketch lines. Keep the
  composition unchanged. Let the newly added objects blend naturally into the original scene."

The Seed blog also shows colour edits with hex codes or a swatch image ("Using the material from
Image 1 and the color swatch from Image 2, modify the sofa in Image 3.") and isolated edits inside
differently coloured frames.

## Interactive editing with coordinates (pro / flash)

Two forms:

1. **Freeform marker + natural-language location**: draw on the image, then describe the marker and
   the edit ("Add a TV inside the blue box").
2. **Precise coordinates** in the prompt:
   - Point: `<point>x y</point>`. The model decides the affected area.
   - Box: `<bbox>x1 y1 x2 y2</bbox>`, top-left then bottom-right corner.

Coordinates are **normalized integers from 0 to 999** relative to one image: top-left `0 0`,
bottom-right `999 999`. Conversion from pixels: `x = round(x_px / width * 1000)`,
`y = round(y_px / height * 1000)`, using the displayed size of that image. Official prompts put the tag
both after ("Image 1 `<point>520 460</point>`") and before ("at `<point>520 460</point>` in Image 1") the
image name; either way, each tag belongs to one named image.

| Scenario | Official prompt |
|---|---|
| Point edit | `Replace the object at Image 1 <point>520 460</point> with a crown.` |
| Box edit | `Replace the area of Image 1 <bbox>120 180 640 760</bbox> with a garden.` |
| Cross-image | `Place the subject from Image 1 <bbox>179 283 796 986</bbox> at the position of Image 2 <bbox>118 331 933 871</bbox>.` |

Tips from the guide:

- When a box holds several subjects, name the target: `Replace the person on the left in Image 1
  <bbox>120 180 640 760</bbox> with a robot.`
- Box what must not change and say so: `Replace the area Image 1 <bbox>120 180 640 760</bbox> with
  a garden, and keep the area Image 1 <bbox>700 120 920 360</bbox> unchanged.`

## Reference images and multi-image input

From references the model extracts character design, style, product features and so on. State
two things:

- **Reference target**: what to take and keep from the reference (the character's look, the
  product's material).
- **Generated scene**: what the new picture shows, its scene and layout.

Official examples:

- "Based on the character in the reference image, create an anime figure and place it on a desk.
  [...] Position the figure on the left side of the image. The overall style should be consistent
  with the reference image, maintaining a cinematic photographic feel."
- "Referencing the linear minimalist style of icons, design 9 application icons for different
  scenarios, including: music, weather, calendar, camera, chat, map, alarm clock, shopping cart,
  and notebook, while maintaining a consistent color scheme."
- "Generate four tops in different materials and colors, based on the clothing style worn by the
  girl in the image. Show only the clothing."

With several inputs, say what to take or edit from each image:

- Replace: "Replace the subject in Image 1 with the subject from Image 2."
- Combine: "Dress the character in Image 1 with the outfit from Image 2."
- Style transfer: "Apply the style of Image 2 to Image 1."
- Seed blog (Pro): "Combine the people from Images 2 to Image 6 into a group photo referencing the
  positioning in Image 1."

Images are numbered in the order they are passed in the `image` array.

## Sketches, wireframes and floor plans

1. Provide a clear source image. If it contains written notes, say "Generate based on the text in
   the image".
2. State the subject and the requirement (a high-fidelity UI, a modern living room).
3. State what must match the reference (furniture placement, the prototype's layout).

Official example: "Based on this floor plan, generate a photorealistic image of a "modern
minimalist furnished living room + open dining area". The room layout and furniture placement
should exactly match the reference. [...] From front to back, the scene should include: sofa &
green plants, television, dining table & chairs, and floor-to-ceiling windows. Do not include any
text or hand-drawn edges from the original sketch."

## Multi-image output (lite only)

5.0 lite (and 4.x) generates sets with consistent characters and style when
`sequential_image_generation` is `auto`. Phrases like "a series", "a set", or a number of images
trigger it: "Generate four film storyboard images, corresponding to the following scenes: [...]".

**5.0 pro and flash do not support sequential image generation**: each request returns one image
(or one base image plus layers).

## Layer decomposition (pro / flash)

Set `layer_decomposition: true`, pass exactly one image (png or jpeg, 262,144 to 36,000,000 total pixels, e.g. at least 512x512 in area). The
prompt is optional:

| Goal | Prompt |
|---|---|
| Decompose the main elements | Omit the prompt (cURL, Java, Go). The Python and OpenAI SDKs need one: "Decompose the main visual elements into separate layers." |
| Choose the elements | Name them: "Decompose the person, title text, and decorative icon in the lower-right corner." Marks on the image also help. |
| Exact regions | `<bbox>` tags, e.g. "Decompose the image into seven layers, including six text groups at: `<bbox>180 64 812 198</bbox>`, [...]; and one parrot at `<bbox>347 305 642 997</bbox>`." |

Output: one base image (`z_index` 0) and up to 16 alpha PNG layers, each with `bounding_box`,
`name` and `description`. Asking for more layers than the limit may lose layers. A returned layer
can be edited on its own ("Change the parrot in the image into a peacock.") with
`background: "transparent"` and `output_format: "png"` to keep the alpha.

## Parameters that interact with the prompt

- **Size, method 1 (recommended):** set `size` to a resolution tier and **describe the aspect
  ratio, shape or purpose in the prompt**; the model picks the dimensions. Pro / flash tiers are
  `1K`, `1.5K` or `2K` (default `2K`; 1.5K costs the same as 1K and looks better). Lite tiers are
  `2K`, `3K` or `4K`, but the docs list lite's default as the pixel value `2048x2048`, so set a
  tier on lite to let a non-square ratio in the prompt apply. The pro tutorial's sizing example reads "Generate a set of four
  cohesive illustrations with a 3:2 aspect ratio, [...]" with `"size": "2K"`; on pro / flash, which
  can't return sets, that wording yields at most one composite image.
- **Size, method 2:** `size` as `WIDTHxHEIGHT`. Total pixels must be 921,600 to 4,624,220 on pro /
  flash and 3,686,400 to 16,777,216 on lite; aspect ratio 1/16 to 16 on all. Don't combine the two
  methods. Input images have their own, wider limits, so an input's dimensions aren't a valid
  output size by default.
- **Layer decomposition size:** tiers only (`1K`, `1.5K`, `2K`, `auto`; default `auto`).
- **Prompt optimization:** `optimize_prompt_options.mode` is `standard` by default (higher quality,
  slower); `fast` exists only on pro. The docs describe it only as prompt optimization with a
  quality / speed trade-off; resellers (WaveSpeed) describe it as a rewrite of the prompt.
- **Transparent background:** `background: "transparent"` only for image-to-image with exactly one
  alpha-channel input, png output. Text-to-image, several inputs, a jpeg input or jpeg output all
  return an error.
- **No negative prompt.** The API has no negative-prompt field; exclusions are written in the
  prompt, as the official floor-plan example does ("Do not include any text or hand-drawn edges
  from the original sketch").
- **Watermark:** `watermark: true` adds an "AI-generated" mark in the lower right.

## What resellers add

Semi-official hosts wrap the same models. Where their advice differs from ByteDance's docs, the
docs win. Sources: [WaveSpeed text-to-image](https://wavespeed.ai/models/bytedance/seedream-v5.0-pro),
[WaveSpeed edit](https://wavespeed.ai/models/bytedance/seedream-v5.0-pro/edit),
[WaveSpeed layer decomposition](https://wavespeed.ai/models/bytedance/seedream-v5.0-pro/layer-decomposition),
[fal edit API](https://fal.ai/models/bytedance/seedream/v5/pro/edit/api),
[fal layerize API](https://fal.ai/models/bytedance/seedream/v5/pro/layerize/api),
[fal prompting guide](https://fal.ai/learn/tools/how-to-use-seedream-5-0-pro-v2),
[Runware model reference](https://runware.ai/docs/models/bytedance-seedream-5-0-pro),
[Runware prompting guide](https://runware.ai/docs/models/bytedance-seedream-5-0-pro/guides/prompting),
[Replicate blog](https://replicate.com/blog/how-to-prompt-seedream-5),
[Atlas Cloud guide](https://www.atlascloud.ai/blog/tips/seedream-5-pro-prompt-guide) (all retrieved
2026-11-08).

Parameter names by host:

| Host | Generation / edit | Layer decomposition | Prompt optimization |
|---|---|---|---|
| ByteDance (ModelArk, Ark) | `prompt`, `image` (array), `size`, `background` | `layer_decomposition: true` on the same endpoint | `optimize_prompt_options.mode` |
| WaveSpeed | `prompt`, `aspect_ratio`, `resolution` (`1k`/`1.5k`/`2k`); edits on `/edit` with `images` | separate `/layer-decomposition` endpoint (`image`, `prompt`, `resolution`) | `prompt_optimization_mode` |
| fal | `prompt`, `image_size` (`auto_1K`/`auto_1.5K`/`auto_2K` or presets), `num_images`, `background`; edits on `/edit` with `image_urls` (up to 10; extra ones drop the first) | separate `/layerize` endpoint (`image_url`, `prompt`, `image_size` incl. `auto`) | `enhance_prompt_mode` |
| Runware | `positivePrompt` (3,000 characters max), `width` / `height`, `inputs.referenceImages` | `settings.layerDecomposition: true` with exactly one reference image; `positivePrompt`, `width` / `height` and `settings.background` are not allowed with it | not documented |

When a host has an aspect-ratio control, keep the ratio written in the prompt consistent with it.
fal's edit example numbers inputs "Figure 1, Figure 2"; ByteDance uses "Image 1".

Advice that agrees with the official docs and adds practical detail:

- **No negative-prompt field** on WaveSpeed, fal or Atlas Cloud either; WaveSpeed labels `prompt`
  as the positive prompt.
- **Prompt optimization** (WaveSpeed): standard mode rewrites more fully; fast "follows long or
  intricate prompts less closely" (about 14 s vs 26 s).
- **Format first and pin clauses** (Runware): naming the format up front ("fashion editorial
  magazine cover") makes the model leave room for mastheads; edits should end by naming what stays
  fixed, or "unmentioned elements start moving".
- **Designed pieces as a layout handoff** (fal): name the grid, the regions and what fills each;
  give each quoted string a position.
- **Light and material over adjectives** (fal, Atlas Cloud): give light direction, hardness and
  colour; name materials ("matte ceramic") rather than "detailed" or "high quality".
- **Example-based edits** (Replicate, 5.0 lite): "Reference the change from Image 1 to Image 2,
  apply the same operation to Image 3."
