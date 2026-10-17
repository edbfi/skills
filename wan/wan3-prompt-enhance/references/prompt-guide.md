# Wan 3.0 prompt guide (condensed)

Condensed from Alibaba Cloud's
[Wan 3.0 Video Generation Prompt Guide](https://help.aliyun.com/en/model-studio/wan3-video-generation-prompt-guide)
(retrieved 2026-10-17). It describes how Wan 3.0 reads prompts. `SKILL.md` decides what this skill
writes: where the guide encourages adding detail, the skill still only organizes what the user
gave.

Contents:

1. [Task types](#task-types)
2. [The full prompt formula](#the-full-prompt-formula)
3. [Element writing](#element-writing)
4. [Scenario patterns](#scenario-patterns)
5. [Video editing wording (out of scope for the skill)](#video-editing-wording-out-of-scope-for-the-skill)
6. [Platform limits](#platform-limits)

## Task types

| Task type | Capability | Input | Output |
|---|---|---|---|
| Text-to-video | Text-to-video | Prompt | Single-shot or multi-shot narrative video |
| Image-to-video | First frame to video | Prompt + first-frame image | Video starting from the image |
| Image-to-video | First and last frame to video | Prompt + first and last frame images | Video moving from the first frame to the last |
| Reference-to-video | Subject reference | Prompt + image or video of a person, object, scene or virtual character | New video keeping the subject's appearance or voice |
| Reference-to-video | Motion reference | Prompt + video with action, expression, camera movement or VFX | New video replicating that motion |
| Reference-to-video | Style reference | Prompt + style image or video | Video following the style |
| Reference-to-video | Audio reference | Prompt + music, dialogue or timbre audio | Video whose audio track follows the reference |
| Reference-to-video | Clay render reference | Prompt + clay render video | Photorealistic re-render |
| Reference-to-video | Storyboard / multi-grid | Prompt + multi-grid shot image | Video following the storyboard |
| Reference-to-video | Keyframe reference | Prompt + several keyframe images | Video following the keyframe order |
| Reference-to-video | File / webpage reference | Prompt + document or webpage link | Video based on the content |
| Video editing | Instruction editing | Prompt + source video | Source video with elements added, removed or changed |
| Video editing | Reference-image editing | Prompt + source video + reference image | Source video changed with the image's content |
| Video editing | Audio editing | Prompt + source video | Source video with voice, music or effects adjusted |
| Video editing | Video extension | Prompt + source video | Source video continued before, after or both |

The skill organizes every row except instruction, reference-image and audio editing, which change
the source video's own timeline and are passed downstream unchanged. Video extension generates new
content around a source video and is in scope.

## The full prompt formula

One sentence is enough for Wan 3.0 to produce a video; the more complete and precise the
description, the closer the result. For full-modality work the guide recommends this formula. Write
whatever you want to control and skip any part you don't need:

```text
Prompt = [Overall description]
       + [Material citations: Image N / Video N / Audio N]
       + [Shot N (start-end seconds): subject + scene + motion + aesthetic control]
       + [Dialogue: xx says: "xxxx"]
       + [Sound effects / BGM]
       + [Style / mood]
       + [Negative list]
```

How the skill's sections cover it:

| Formula part | Skill section |
|---|---|
| Overall description | [Core Task] |
| Material citations | [Core Task] (timbre also at the speaking beat) |
| Shots and timestamps | [Plot Outline] |
| Dialogue | [Plot Outline] |
| Sound effects / BGM | [Audio Style] |
| Style / mood | [Core Task] global tone, [Camera and Core Constraints] |
| Negative list | [Negative Prompt] |

The guide's own example strings the formula together into flowing paragraphs: an overall line with
genre, duration and pacing arc; one citation sentence ("The general's appearance references Image 1,
facial expression references Image 2, mount references Image 3, voice timbre references Audio 1");
four timestamped shots; a "Style and mood:" line; a "Negative prompt list:" line.

## Element writing

### Material citations

- Materials are numbered by upload order, each modality separately: Image 1, Image 2, Video 1,
  Audio 1. Image 1 and Video 1 can coexist.
- Write `Image N`, `Video N` or `Audio N` directly. The number must match the upload order or the
  wrong material is cited.
- With a single material, "the reference image" or "the reference video" is enough; with two or
  more, numbers are required.
- One material can be cited in several places, once per use (appearance, motion, timbre, scene).

| Goal | Wording |
|---|---|
| Single material | "Reference image, generate a video of it running"; "Reference the camera movement of the video, reshoot a segment" |
| Lock appearance only | "The child in Image 1 stands in the entryway of the modern apartment in Image 2" |
| Mix materials | "The figure in Image 1 holds Image 2 in hand and walks into the scene of Video 1" |
| Voice cloning | "Voice timbre references Audio 1"; "Speak in the timbre of Audio 1: \"xxxx\"" |
| Camera movement only | "Reference the camera movement of the video, change the scene to a cup of coffee on a rooftop cafe table" |
| Action only | "Replace the skateboarding man in Video 1 with the woman in Image 1, keeping the skateboarding action, trajectory, and scene unchanged" (the skill rewrites "replace" as who does what) |
| VFX only | "The character in Image 1 follows the energy VFX of Video 1, generating the same flame-burning VFX and action" |
| Style only | "Style references Image 2"; "Only reference the color tone and lighting of Image 2, not the characters" |
| Document / webpage | "Based on my proposal document, generate an ad film for a brand" |

### Shots and timestamps

Multi-shot videos use number + timestamp + shot content, keeping subject, scene and atmosphere
consistent across shots:

- Overall description: one sentence on theme, perspective, narrative style and mood.
- Shot number: defines the order.
- Timestamp: start and end right after the number. Shots join end to end without gaps or overlaps,
  2 to 5 seconds each.
- Shot content: action, dialogue, expression and scene, as for a single shot. Avoid
  high-frequency actions the model can't control ("shakes head 3 times per second").

Formats are interchangeable but should be used consistently: `Shot 1 [0-3s] xxxx`,
`Segment 1 [0-5s]: xxxx`, `Shot 1 (00:00-00:03): xxxx`, number only (`Shot 1: wide shot xxxx`), or
timestamp only (`[00:00-00:03] xxxx`).

| Goal | Wording |
|---|---|
| Single shot, no split | "Generate single shot" or "One continuous shot" on the first line |
| Camera completely still | "Fixed shot, camera static, position unchanged" |
| Camera movement | Plain words: push in, pull out, orbit, handheld follow |
| Transition | "hard cut" or "dissolve" at the end of a segment, or "seamlessly continue from the last frame of the previous segment" |
| Pacing | "pacing shifts from steady restraint to explosive release" in the overall description |
| Focal length / depth of field | "85mm telephoto, shallow depth of field"; "24mm wide-angle, deep focus" |
| High-speed photography | "High-speed photography (1000fps slow motion)" |

### Dialogue

- Character + speaking verb + colon + quoted line: `xx says: "content"`, `she whispers: "content"`.
- Several speakers: one line each, speaker named (`Image 1 says: "xxxx"`; `Image 2 replies: "xxxx"`).
- Voice cloning: `Voice timbre reference Audio N`, written once; it applies to all of that
  character's lines.
- Lip sync: append `Lip sync`.
- Voiceover or monologue: `Voiceover: "xxxx"`; `Female voice chanting: "xxxx"`.
- No dialogue: write `No dialogue` explicitly, otherwise the model decides on its own.

### Sound effects and BGM

- Ambient sound is matched automatically when actions, materials and weather are described
  (war banners snapping, splashing through puddles).
- Specific effects go in their own sentences, optionally timed: "Whoosh on colour-block slide-in",
  "From the 8th second, female voice chanting: \"xxxx\"".
- BGM has three levels: write nothing and let the model choose; specify it ("BGM drops to the low
  register, cello enters very softly"); or exclude it ("No background music").

### Style and mood

Art style + colour tone + mood, at the start or end, as keywords or a fuller description:

| Part | Examples |
|---|---|
| Art style | 35mm cinematic film, Hong Kong realism, line illustration, wasteland style, Miyazaki animation, Chinese mineral-colour painting, clay animation, motion graphics, Apple Keynote minimalist business style |
| Colour tone | High-saturation warm yellow; cyan-blue × gilded gold contrast; low-key high-contrast lighting |
| Mood | Tragic and unyielding; light and healing; oppressive and tense; relaxed and confident; mysterious and magical |

### Negative list

Write only what must not appear; leave it out when there is nothing. Don't pad the list or repeat
what the positive prompt already says. Categories the guide lists, useful for recognizing and
phrasing a user's exclusions:

| Category | Examples |
|---|---|
| Characters / frame | No face distortion, no face swapping, no extra fingers, no twisted limbs, no clipping, no cutout traces |
| Text / watermark | No subtitles, no watermark, no complex text, no extra brand names |
| Style | No childish cartoon, no photorealistic live action, no game-CG look, no music-video showboating, no cheap cyberpunk |
| Sound | No background music, no voiceover, no dialogue, no BGM dominating the mix |
| Action | No characters running illogically, no exaggerated limb movements, no slow motion |
| Camera | No large camera movements, no sustained shake, no over-stabilization, no frequent cuts |
| Space | No spatial chaos, no vehicle clipping, no axis errors, no multiple people in frame |
| Consistency | No character position changes, no costume changes, no scale drift |

## Scenario patterns

### Multi-subject consistency

Pass many people, props and scenes at once and lock each with its own number. A compact form the
guide uses: "Subject locking: little girl Image 6, lollipop Image 7, punk Image 4, ... Chinatown
alley Image 1." Keep each material's purpose separate so features don't bleed between subjects.
Long multi-subject prompts often use labelled blocks (`[Video type]`, `[Reference material]`,
`[Shot structure]`, `[Expression and dialogue]`, `[Visual style]`).

### Storyboard / multi-grid

- Declare the usage first: "Use the storyboard only as shot guidance; do not generate video from the
  storyboard as a single image", so the grid isn't treated as one frame.
- Restate panel by panel, left to right and top to bottom: shot size, camera movement, subject
  position. Details the grid doesn't show come from the prompt.
- Segments needn't map one to one to panels; the storyboard is a plot outline.
- End with art style, render texture and the user's exclusions.

### Clay render reference

Use the pure-white clay render video as the sole blueprint and replace only material, colour and
texture:

- State the locked items explicitly ("change nothing except material and color") and list camera
  trajectory, cut points, object positions and character actions as unchanged: no additions,
  removals or moves, not one frame added or dropped.
- Optical details (glass refraction, leaf veins, skin subsurface scattering) make the re-render read
  as real; that detail is the user's or PE's to add.

### File / webpage to video

Upload docx, pptx, xlsx or pdf, or paste a link; the model reads the content. The prompt states who
it is for, what style and what format; for finer control, give the shot structure, voiceover pace
and number animations. Files and links must be publicly accessible; content behind a login or on
an intranet can't be read.

### Line-guided camera movement

Red lines on the reference image mark the camera path and waypoint order. The prompt restates the
route waypoint by waypoint (pass-throughs, speed changes) and the model flies one continuous take
along it. The guide's examples open with "[Hard requirements for the base image] The final footage
completely removes all red lines, numeric markers, arrows, and auxiliary marks", then
"[Core camera-movement rules]" (single take, follow 1→2→...→N, skip nothing), "[Segmented by
waypoint]", "[Final hold frame]" and "[Lighting and quality notes]".

### Temporal video transfer

A reference video's action, camera movement or effects act as a timing signal for a new subject or
scene:

- Action: "Reference video: replace the skateboarding man in Video 1 with the woman and outfit in
  Image 1. Note: replace only the character; keep the original skateboarding motion, trajectory,
  and skatepark background in the video completely unchanged."
- Camera movement: "Reference the camera-movement style of the reference video; change the scene to
  a cup of coffee on a rooftop café table."
- Effect: "Apply the energy effect from Video 1 to the character in Image 1; generate the same
  effect and action."

### Audio-driven

Audio can drive the beat (dance) or the timbre (dialogue transfer):

- Beat: "dances ... following the beat of the fixed audio"; map heavy downbeats to large moves and
  holds, gentle passages to soft waves, climaxes to denser, explosive moves.
- Timbre: "Extract the timbre features from Audio 1, and have the character speak the following
  dialogue: \"...\"", plus lip movements driven by the speech.

### Video extension

- Intent: use keywords such as extend, continue or continue writing.
- Direction: extend backward (from the last frame), extend forward (ending at the first frame), or
  both (the original as the middle segment).
- Content: the new actions, dialogue and picture changes, with the characters' look, clothing and
  scene restated to avoid continuity glitches; "timestamp + shot" can carry the original's mood
  and camera movement.

### First frame / first and last frame

The first (and last) frame locks the start (and end); the model fills the motion between. The
images already set subject, scene and style, so the prompt describes motion, plot, dialogue and
camera movement. The guide's first-frame example uses timed blocks such as
"(0:00-0:03) Camera movement: medium shot. Picture: ... Action: ... Mood: ...".

## Video editing wording (out of scope for the skill)

Editing requests pass downstream unchanged. If a user asks how Wan expects them worded:
"Edit the video: change xxx in Video 1 to yyy, keep the rest of the frame unchanged", using add,
delete, replace or modify.

- Element: "The man puts on a red hat"; "Replace the cat with a dog"; "Remove the cat on the grass";
  "Have the man in the video wear the top from Image 1 and the pants from Image 2".
- Global: weather, colour tone or style changes, with "keep everything else unchanged".
- Temporal: actions or lines over time, optionally with timestamps such as 4-6s; "Keep the
  character's voice timbre and tone; change the woman's spoken line to: 'Hello World'".
- Plot reshape: "Reshape the plot of Video 1: have the man pick up the guitar and play".

## Platform limits

- Extension: input duration + output duration ≤ 30 seconds. Set the duration parameter to -1 or to
  the input duration plus the wanted extension.
- First-and-last-frame mode and full reference mode are mutually exclusive; with the dedicated mode
  on, reference materials can't be added.
- Files and webpage links must be publicly reachable.
