---
name: wan3-prompt-enhance
description: "Organize a Wan 3.0 (wan3.0, Alibaba Cloud Model Studio) video generation request - the user's text plus any Image N / Video N / Audio N references - into one clean, structured request with the five sections Core Task, Plot Outline, Audio Style, Camera and Core Constraints and Negative Prompt, faithful to the user's own story and never enriching it. Use whenever the user types /wan3-prompt-enhance or /wan3-pe (the upstream name), asks to refine, tidy, structure or optimize a Wan, Wanxiang or wan3.0 video prompt, or wants a text-to-video, image-to-video, first/last-frame, reference-to-video, multi-shot, storyboard, clay-render, audio-driven or video-extension request organized before generation, even if they don't name this skill. Not for remaking a source video's plot, direct edits to an existing video, or questions about API pricing, quotas or errors."
metadata:
  author: engels74
  version: "1.0.0"
  vendor: wan
  upstream: "Alibaba Cloud wan3-pe skill 0.2.0 (Mandarin), translated and merged with the Wan 3.0 Video Generation Prompt Guide"
---

# Wan 3.0 prompt enhance

An English translation of Alibaba Cloud's official `wan3-pe` skill (version 0.2.0), merged with the
[Wan 3.0 Video Generation Prompt Guide](https://help.aliyun.com/en/model-studio/wan3-video-generation-prompt-guide).
The guide's task types, prompt formula and scenario patterns are in
[references/prompt-guide.md](references/prompt-guide.md); read it when a request involves a scenario
named in "Scenario patterns" below or when you need the official wording for something.

## What this skill does

It turns the user's written request, together with references to image, video and audio materials,
into one clean, structured video generation request. The result always has the same five sections:
**[Core Task]**, **[Plot Outline]**, **[Audio Style]**, **[Camera and Core Constraints]** and
**[Negative Prompt]**. The user's core intent is carried over unchanged, every material reference
is gathered in [Core Task], and the subject mapping follows naturally from the plot beats.

This step formats and organizes. Its boundaries:

- Organize only the plot, subjects, dialogue and reference requests the user has written. Don't
  expand the story or add anything the user didn't mention.
- The request flows on to a downstream prompt-enhancement (PE) step. This step only makes the input
  clear; generation-specific phrasing is left to that later step. The official guide's advice to
  describe scenes richly applies to what the user writes and what PE adds, not to this step.
- Materials are read-only: never modify the source materials or produce helper materials.
- Never call a video generation API yourself. When the user asks for a video, deliver the organized
  request first and hand it on to the next step.

## When to use it

Decide by the target output alone. Use this skill when the materials are conditions for generating a
new video. Don't use it when the output must directly change the existing timeline of the input
video. When the input contains no video at all, always use it.

Use it when:

- The user gives image, video or audio references and wants them organized or normalized into a
  video generation request.
- The user wants a new video that borrows the people, objects, scenes, composition, lighting,
  style, motion, camera movement, editing, effects or sound from the materials.
- The user wants images as the opening, intermediate or closing frames, or wants a whole video or
  audio segment embedded in the result.
- The user wants new content generated and joined before, after or between reference videos
  (Wan calls this video extension).
- The user gives only a rough idea, a long description or a messy complex request that needs
  organizing into a structured request they can use directly.

Don't use it for:

- **Plot reshaping**: the user explicitly wants to reshape, subvert, adapt, remix, rework,
  reinterpret or remake the existing plot of the input video. That is a plot-reshape task; tell the
  user it needs the corresponding reshape flow. (Wan words these as "Reshape the plot of Video 1:
  ...".)
- **Direct edits to the input video file**: deleting, replacing or repairing picture, sound or
  timeline objects already in the source video. Pass the user's instruction downstream unchanged;
  it needs no organizing. Reply in one or two sentences that this is a direct edit for Wan's video
  editing, followed by the instruction exactly as written. If the user asks how Wan expects edit
  instructions to be worded, the official patterns are in
  [references/prompt-guide.md](references/prompt-guide.md).
- Questions only about API parameters, pricing, quotas, errors or model capabilities.

## Hard constraints

1. **Stay faithful to the original.** Character identities and numbers, key props, scenes, cause
   and effect, spatial relations and the story's ending follow the user's text exactly: nothing
   added, removed or altered.
2. **Keep facts apart from observations.** Identity, age, relationships, events and outcome come
   from the user's text. Materials only add attributes you can directly see or hear; an observed
   appearance never becomes a plot fact.
3. **Match subject counts.** A single-person character sheet maps to exactly one character. With
   several single-person candidates, assign one person per image first; with several group
   candidates, assign one group per image first. Merge references only for multiple views of the
   same subject, or when the material itself already shows the same group.
4. **The user's mapping wins.** Material roles, subject names and relationships the user assigned
   are carried over unchanged. Once the user's mapping covers a role, don't add unnamed materials
   for that same role.
5. **Account for each material.** For every material actually used, state what is taken from it and
   how far the reference reaches.
6. **Restructure.** Whether or not the original request is complete, reorganize it into the
   five-section template. Beyond synonymous rewording, the work is structural.
7. **Keep parameters out.** Aspect ratio, total duration, resolution and frame rate are set in the
   page or API. Use them only to plan how many events fit; don't write them into the request body.
   Event timings the user wrote are creative content and stay verbatim.
8. **Don't pile on constraints.** Organize only what the user asked for. Leave out quality
   boilerplate, watermark, logo or subtitle rules and other generic negatives the user didn't ask
   for.
9. **Deliver only the request body.** The whole reply is the request itself. Opening
   acknowledgements, closing summaries, analysis, organizing notes and reasons for changes stay
   internal. This applies to requests the skill organizes; for an out-of-scope request, reply
   briefly with the route instead (see "When to use it").
10. **One best version.** Give a single organized request by default; give several only when the
    user explicitly asks to compare versions.
11. **Ask as little as possible.** Finish everything you can reasonably decide from the text,
    materials and context. Ask only when a question would change the core result and has several
    equally valid answers, and then merge all doubts into one question.

## Material input cases

Work out which case the input falls into before organizing.

### Plain text, no materials

The user has no materials and the text shows no wish to reference any. Extract the subjects, events,
scene, shots and sound straight into the five-section template. Don't invent material numbers and
don't urge the user to add materials.

### Materials cited but not available

Keep every material reference already written in the request exactly as written: `Image N`,
`Video N`, `Audio N`, `图N`, `视频N`, `音频N` or the runtime's equivalent tags. A material missing from
the current message, or unreadable in this environment, is no reason to delete it, renumber it or
rewrite the request as reference-free.

Organize the request from the user's text as usual and keep each material's role and reference
relationship. Don't claim to have seen a material you couldn't read, and don't add details that
only viewing it could confirm. If the user wrote no material references, add none. An unreadable
material only limits which facts you can confirm; it doesn't block organizing.

### Materials readable

Actively read the images, video and audio the user provided. Skim all of them first, then build the
mapping together with the request. Never guess a material's content from its file name.

Documents (docx, pptx, xlsx, pdf) and webpage links are content sources: keep the citation as the
user wrote it and let the document or page supply the content. Wan can read only publicly
accessible files and links; if a link is clearly behind a login or on an intranet, say so in a
`Material note:` line.

### Count and limits

When there are many materials, remind the user to watch the submission limit. If the count is still
reasonable, keep organizing, and keep materials from interfering with each other by giving each
one a role and activating it only in its scene. If materials really must be cut, give the complete
request first, then append one `Material note:` line saying which materials to drop before
submitting.

### Numbering

Each modality is numbered separately in upload order: Image 1, Image 2, Video 1, Audio 1, so
Image 1 and Video 1 can coexist. The number identifies the material only and says nothing about
when it appears in the result. It must match the upload order, otherwise Wan cites the wrong
material. Keep the numbers and the reference forms of the user's original request throughout.

## Workflow

### Step 1: Lock the story contract

From the user's text, first set up a "story contract", then check the material references against
it. Extract and lock, item by item:

- The subjects that appear and how many there are.
- Actions, events, and their causes and order.
- Scene, time, weather and spatial orientation.
- Who owns each prop, how props change hands, and their final state.
- Requests for shots, sound, dialogue and subtitles.
- Shot timestamps: keep exactly as many as the user wrote.
- Anything the user named to keep or to exclude.

The story contract is the factual boundary for organizing. Every event, subject and line in the
result must trace back to the user's text; never swap or merge something in because a material
contains something more eye-catching.

Whenever the input involves speech, dialogue or narration, record for each line the speaker, the
verbatim text, the language, and whether it is on-screen or off-screen. Keep the user's lines word
for word. If the user only described what someone says without giving the words, keep that
description and don't write dialogue yourself.

Register every character, group, key prop and scene that clearly appears in an internal "required
entities list", and confirm one by one before finishing that each has made it into the request.

Words like "replace with" or "swap for" in the user's request describe a reference relationship (for
example, the person in Image 1 performs the motion of Video 1). Rewrite them as who does what, and
make the correspondence between people, actions, scenes and other references explicit.

### Step 2: Understand the materials

With many materials, look in two passes:

1. A light first pass over everything, marking candidates for people, products, props, scenes,
   actions, camera movement, sound and style.
2. A second, closer look only at materials that match the plot, conflict with each other, or will
   serve as key frames.

For a video, confirm at least the subjects, main action, shot changes and the opening and closing
states. For audio, confirm at least the sound type, timbre, language, spoken content or the purpose
of the ambient sound.

Treat information as one of two kinds:

- **Story assignment**: a person's name, age and relationships, which event they carry, who owns a
  prop, how things end. These always come from the user's text.
- **Observable traits**: facial features, hairstyle, clothing, colour, material, spatial layout,
  motion, camera movement, timbre, and other things you can directly see or hear.

Materials only add observable traits. Don't add brands, occupations, personalities or prop
functions you can't confirm. If the user just says "the person" or "the subject", keep that neutral
term; use a role name or identity only when the user gave one.

When mappings conflict, decide by this priority, highest first:

1. What the user explicitly specified.
2. The description in the request text.
3. The material's own content.
4. File names and metadata.
5. Upload order.

When the user's explicit mapping already covers every required entity, the remaining unnamed
materials stay out of this task by default.

### Step 3: Assign material roles

Each material used takes one clear role:

- Image: a person's appearance and clothing, a product's structure and material, a prop, a scene
  layout, lighting, or a frame in the timeline.
- Video: motion, camera movement, pacing, timeline, or a complete stretch of picture in the result.
- Audio: a speaker's timbre and lines, ambient sound, sound effects or music, or a complete stretch
  of sound in the result.

Build the mapping in this order:

1. Take each unassigned character, group, prop and scene from the required entities list in turn.
2. Survey all candidate materials, comparing headcount, clothing layers, silhouette, structure and
   fit for the role. Keep looking at the rest even after the first usable one.
3. Pick the best match for the current slot, then move to the next slot. Different named
   characters each get their own best candidate by default.
4. Finish with a gap audit: every required entity has exactly one clear role, and every material
   used carries only its declared role.

In the result, each reference binds exactly one subject, prop or scene to its material and the scope
taken from it. Multiple subjects are split into separate bindings:

```text
Person A references Image 1 for facial features, hairstyle and clothing.
Person B references Image 2 for facial features, hairstyle and clothing.
Prop A references Image 3 for structure, material and colour.
Scene A references Image 4 for spatial layout, architecture and lighting; ignore the people in the image.
```

When one subject has several references, say which view or attribute each one adds, and state that
together they define the same entity and only one instance is generated. When the user explicitly
draws several aspects from one material (Video 1 for both a character's look and the camera
movement, say), cite it separately for each aspect, still bound to that one subject.

When two references conflict, follow the user first; otherwise divide by clarity and fit with the
plot. Only when even the core identity can't be determined, merge it into one question.

### Step 4: Weigh mapping certainty

| Certainty | Response |
|---|---|
| Clear | Map directly and carry on. |
| Inferable | Use the most reasonable mapping and keep going; let the assumption show naturally in the matching text rather than declaring it. |
| Doubtful, no effect on the result | Leave the material unused and don't bother the user. |
| Doubtful, affects the core | When the ambiguity touches core identity, counts, prop ownership, spatial relations or a key-frame role, merge the doubts into one short question and wait for the answer before delivering. |

Style, lighting, ordinary camera movement, and other gaps that context can settle conservatively
never warrant interrupting the user.

### Step 5: Fill the template and clean up

Fill the five-section template below, applying any special-case guidance that fits, and keep only
the sections the task needs. Replace every placeholder with concrete content; the template's own
guidance text never appears in the result. Run the pre-delivery checks, then deliver per the
delivery conventions.

## Request template

### The five-section request

```text
[Core Task]
Generate a <genre or type> video of <content summary>, referencing the <appearance/motion/scene/timbre or other adopted content> of <subject or content> in <Video N/Image N/Audio N>. The whole video uses <global style tone>.
All material references are stated here; a timbre reference is written as "<character>'s voice timbre references Audio N".

[Plot Outline]
1. <Beat one: people, action, event; the user's lines kept verbatim and bound to the speaker>.
2. <Beat two...>; says in the voice of Audio N: "<verbatim line>".
<Timbre references are stated at the matching speaking beat.>
<When the user gave shot timestamps, start the beat with "Shot N xx-xx s", the timing kept exactly as the user wrote it; without user timestamps keep plain beat numbers.>

[Audio Style]
<Dialogue language and texture, live sound effects, the mood and arc of the score.>
<If the user didn't mention it, keep one short sentence or drop the section.>

[Camera and Core Constraints]
<Shot style, movement, editing pace, and any hard constraints the user gave.>
<If the user didn't mention it, keep one short sentence or drop the section.>

[Negative Prompt]
<Comma-separated items the user explicitly excluded. Output this section only when the user asked to exclude something.>
```

Section rules: [Core Task] and [Plot Outline] are always present. [Audio Style] and [Camera and Core
Constraints] scale with how much the user said: one short sentence, or nothing, when the user said
nothing. [Negative Prompt] appears only when the user asked to exclude something. A simple task may
keep just the first two sections.

For a request whose main instruction is in Chinese, use the original headings and reference forms:

| English | Chinese |
|---|---|
| `[Core Task]` | `【核心任务】` |
| `[Plot Outline]` | `【情节概要】` |
| `[Audio Style]` | `【音频风格】` |
| `[Camera and Core Constraints]` | `【运镜与核心约束】` |
| `[Negative Prompt]` | `【负面提示词】` |
| `Material note:` | `素材提示：` |
| `Additional note:` | `补充说明：` |
| `Image N` / `Video N` / `Audio N` | `图N` / `视频N` / `音频N` |

The five sections cover every part of the guide's full prompt formula: overall description and
material citations go in [Core Task]; shots, timestamps and dialogue in [Plot Outline]; sound
effects and BGM in [Audio Style]; style, mood, camera and hard rules in [Core Task] (global tone)
and [Camera and Core Constraints]; the negative list in [Negative Prompt].

Filled example (simple task; the user mentioned neither audio nor camera):

```text
[Core Task]
Generate a hands-on video documenting the repair of an old wooden chair, referencing the woodworker's appearance in Image 1 and the old chair's look in Image 2, and the glue-spreading and clamping hand motions in Video 1. The whole video uses a plain, natural slice-of-life documentary style.

[Plot Outline]
1. The woodworker checks the loose joint of the chair back.
2. Following the technique in Video 1, the woodworker spreads wood glue and presses the chair back into place to fix it.
3. The woodworker lets go; the chair back stays firm.

[Audio Style]
No dialogue; the woodworker's mouth stays naturally closed. Only live sounds such as wood rubbing and the light clink of tools.
```

### Writing conventions inside the sections

These follow the official guide and keep the request in the form Wan reads best:

- **Citations**: bind each subject to its material in plain words, as in "The general's appearance
  references Image 1" or "voice timbre references Audio 1". With a single material the user may
  have written "the reference image" or "the reference video"; keep their form.
- **Timestamps**: keep the user's own format (`Shot 1 [0-3s]`, `Shot 1 (00:00-00:03)`,
  `[00:00-00:03]`) exactly as written. Never add timestamps the user didn't write.
- **Dialogue**: `<speaker> says: "<verbatim>"`, one line per speaker for conversations. Off-screen
  speech is `Voiceover: "<verbatim>"`. A timbre reference applies to all of that character's lines,
  so state it once per character. Add `Lip sync` only when the user asks for it.
- **No dialogue**: when the task has no speech, say so explicitly ("No dialogue; the characters'
  mouths stay naturally closed") and name which sounds remain. Left unstated, Wan decides by
  itself whether people talk.
- **Music**: if the user said nothing about music, don't invent a score; a short sound sentence or
  nothing at all lets Wan choose. If the user wants none, write "No background music".
- **Shots and transitions**: when the user wants one take, write "One continuous shot" in
  [Camera and Core Constraints]. Write "hard cut" or "dissolve" only if the user named them.
- **Negative list**: comma-separated, only the user's exclusions, nothing that repeats the positive
  text, and no padding with stock negatives. Sound exclusions ("no dialogue", "no music") are
  already stated in [Audio Style], as the guide recommends, so they don't appear again here; if
  nothing else remains, leave [Negative Prompt] out.

### Whole image into the video

When the user wants a whole image to appear as a frame of the result:

- Put the image's position in [Core Task]: opening frame, key frame along the way, or closing frame.
  With several images, give their order.
- State at the matching [Plot Outline] beat how the image connects to its neighbours: as a continuous
  hand-off, or with new content generated before or after it.
- At the matching beat, state the subjects, states and spatial relations to keep from the image; the
  motion and environment around it change naturally and continuously.
- For a multi-grid image, describe each panel in reading order, always referring to subjects by the
  whole image's number.

When the platform's dedicated first-frame or first-and-last-frame mode is used, the images already
fix subject, scene and style, so the beats spend their words on motion, plot, dialogue and camera.
First-and-last-frame mode can't take other reference materials; if the user combined it with
references, keep the request and add a `Material note:` line saying so.

### Video segment into the video (including extension)

When the user wants a whole video, or a stretch of it, in the result:

- Put the segment's position in [Core Task]: the opening, a middle section, or the end. Use Wan's
  extension wording: "extend Video 1 backward" (continue after its last frame), "extend forward"
  (end at its first frame), or "use Video 1 as the middle segment".
- At the matching [Plot Outline] beats, state how an opening segment continues, how a closing
  segment is led into, or how a middle segment joins on both sides.
- Summarize what the segment actually shows (people, actions, events, sound) in [Plot Outline]; any
  speech in it is written with speaker, language and verbatim text.
- Keep subjects, space and sound continuous between the segment and the generated content. Restating
  the observable look of characters and scene from the source video helps the continuation stay
  consistent.

Wan caps input plus output duration at 30 seconds for extension. That is a parameter, not request
text; mention it in a `Material note:` only if the user's plan clearly exceeds it.

### Audio into the video

When the user wants an audio file used in full:

- Put its range in [Core Task]: throughout the video, or one continuous local stretch and where.
- Put the voices, music, ambience and effects it carries in [Audio Style]; any spoken content you can
  confirm goes verbatim, with its speaker, at the matching [Plot Outline] beat.
- State at the matching beats how the audio lines up with on-screen events. For audio that drives a
  dance, tie the movement to the audio's rhythm and swells.

### Dialogue and timbre

- Keep the user's lines, narration and lyrics verbatim at the matching [Plot Outline] beat, with
  speaker and language.
- Declare a timbre reference in [Core Task] as "<character>'s voice timbre references Audio N", and
  at the speaking beat write "says in the voice of Audio N: '<verbatim line>'".
- For tasks without dialogue, state that nobody speaks, where the sound comes from, and which ambient
  sounds remain.
- When the user explicitly wants on-screen subtitles, state their content and position; otherwise
  write nothing about subtitles.

### Scenario patterns

For these, read the matching section of [references/prompt-guide.md](references/prompt-guide.md) and
fold its pattern into the sections above. Each one only scopes the materials the user gave; none of
them adds story.

- **Multi-subject locking**: many people, props and scenes at once; one binding per subject so
  features don't bleed between them.
- **Storyboard or multi-grid**: say in [Core Task] that the storyboard only guides the shots and is
  not to be animated as a single image, then restate the panels in reading order.
- **Clay-render re-render**: Video 1 is the sole blueprint; only material, colour and texture change.
  List what the user locked (camera path, cut points, positions, actions) in [Camera and Core
  Constraints].
- **Line-guided camera path**: the image supplies a red-line path with numbered waypoints; restate
  the path waypoint by waypoint, and scope the image so its lines and markers are guidance, not
  picture content.
- **Motion, camera or effect transfer**: rewrite "replace X in Video 1 with Image 1" as "the person
  in Image 1 performs Video 1's action, trajectory and scene".
- **Document or webpage to video**: the document supplies content; the request states audience,
  style and format as the user gave them.

## Delivery conventions

- The output language follows the user's main instruction: Chinese in, Chinese out (with the
  Chinese headings); any other language in, that language out (with the English headings). Quoted
  dialogue, lyrics and on-screen text stay in their original language.
- The whole reply is the organized request, starting directly with the [Core Task] section. Only
  when a material limit or specific restriction must be flagged, append a `Material note:` or
  `Additional note:` line after the body.
- Material reference numbers match the user's original request and use one numbering system
  throughout.
- Aspect ratio and total duration are used only to plan event density; they stay page or API
  parameters and never enter the body.
- When materials exceed the submission limit, give the complete request first, then append a
  `Material note:` line. When some fact could only be copied from the user's text because a
  material was unreadable, append an `Additional note:` line. The body itself must be usable as is.

## Pre-delivery checks

Before delivering, check each item:

- Character identities and numbers, cause and effect, prop ownership, spatial relations and the
  ending all match the user's text.
- The result is organized in the template structure, and every event, subject and line traces back
  to the user's text.
- Every material actually used has one unique, clear role and scope.
- Material references are gathered in [Core Task]; timbre references appear at the matching speaking
  beats.
- People, props and scenes are bound one by one, one subject per binding.
- A single-person character sheet maps to one person; where several materials define one subject,
  that is stated explicitly.
- Material references from the original request are kept as written; for unreadable materials you
  didn't claim to have seen them or add unconfirmable details.
- Lines, narration, lyrics and other user-specified spoken content are kept verbatim, with the right
  speaker and language.
- Aspect ratio and total duration exist only as planning parameters; the body has no API parameters.
- Plot-reshape and direct-edit requests were recognized as out of scope and the right route was
  explained.
- The result starts with [Core Task]; [Core Task] and [Plot Outline] are present; [Audio Style] and
  [Camera and Core Constraints] match how much the user said.
- [Negative Prompt] appears only if the user explicitly asked to exclude things, and all of it comes
  from those exclusions.
- Shot timestamps are carried into [Plot Outline] exactly as the user wrote them; without user
  timestamps the beats keep plain numbers.
- The reply is only the request body: it starts with a request section and ends with one, or with
  an allowed `Material note:` / `Additional note:` line.

## End-to-end examples

[references/examples.md](references/examples.md) has two complete runs from the upstream skill: an
emergency-room clip with an appearance reference, a timbre reference, timestamped shots, verbatim
Korean lines and a negative list; and a whole video used as the opening and extended backward. Read
it before your first delivery to calibrate how much the request says.

## Runtime adaptation

- **Text only**: work from the user's text and the material reference tags they wrote; treat unread
  materials honestly and never pretend to have seen them.
- **Multimodal**: read images, video and audio as far as the runtime allows, use the two-pass review,
  and build the mapping automatically.
- **No file system**: keep the user's material numbers and reference forms; for materials you can't
  reach, follow "Materials cited but not available".
- **No network**: keep remote material URLs as references only; their content comes from the user's
  text.
- **Text output only**: this skill produces text. File writes, network, tool calls and binary output
  are all unnecessary.
