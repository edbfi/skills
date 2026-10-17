# End-to-end examples

Two complete runs from the upstream skill, translated. Each shows the user request and the whole reply.

## Example A: emergency-room resuscitation (appearance reference and timbre reference)

User request: `Generate a medical-drama TV clip of a resuscitation scene in a modern emergency room; the doctor's look references Video 1, Shin Dong-wook's voice timbre references Audio 1. Handheld follow camera and fast cutting throughout, shots: Shot 1 0-3 s, Shot 2 3-6 s, Shot 3 6-8 s, Shot 4 8-10 s, Shot 5 10-12 s. Lines: Shin Dong-wook shouts "잠깐만요! 들어가요!", the attending physician says "하나, 둘, 셋.", "한 번 더.", "내 말 들려요?", "눈 떠봐요.", "인튜베이션.", the doctor in scrubs calls "사부님.". End on a freeze of Lee Sung-kyung's utterly shocked face as she puts on an isolation gown. Avoid slow pacing, a calm atmosphere, exaggerated acting, stiff movements, a clean and tidy set, a stable camera, tripods or cranes, slow motion, lyrical music, incorrect medical procedures, fake-looking props, identity drift, facial distortion, a CG look, plastic texture, blur, unrealistic lighting.`

Organized request:

```text
[Core Task]
Generate a medical-drama TV clip of a resuscitation scene in a modern emergency room, referencing the doctor's appearance in Video 1; Shin Dong-wook's voice timbre references Audio 1. The whole clip uses a strongly subjective handheld follow-camera style with fast cutting, building the tension of a race against death.

[Plot Outline]
1. Shot 1 0-3 s: A doctor (Shin Dong-wook) and colleagues rush a gurney carrying a young male patient with a cast on his leg into the resuscitation room; he shouts: "잠깐만요! 들어가요!"
2. Shot 2 3-6 s: Everyone surrounds the bed; the attending physician directs: "하나, 둘, 셋.", starts chest compressions on the patient and orders: "한 번 더." A woman (Lee Sung-kyung) rushes in and pulls off her coat, ready to help.
3. Shot 3 6-8 s: The attending physician tries to rouse the patient: "내 말 들려요?", then instructs: "눈 떠봐요.", "인튜베이션."
4. Shot 4 8-10 s: The doctor with Video 1's appearance (navy scrubs and a sky-blue isolation gown) calls out nervously while working with surgical instruments: "사부님."
5. Shot 5 10-12 s: The final shot freezes on Lee Sung-kyung's face as she puts on the isolation gown, an expression of utter shock, as the ending.

[Audio Style]
Urgent Korean dialogue, live sound such as gurney wheels rolling and monitor beeps, and a score that keeps pushing the tension higher.

[Camera and Core Constraints]
Strongly subjective handheld follow camera that stays close to the characters with natural shake. Fast action cutting between characters and actions to stress chaos and urgency. No slow motion and no unnecessary transition effects.

[Negative Prompt]
slow pacing, calm atmosphere, exaggerated acting, stiff movements, clean and tidy set, stable camera, tripods or cranes, slow motion, lyrical music, incorrect medical procedures, fake-looking props, identity drift, facial distortion, CG look, plastic texture, blur, unrealistic lighting
```

## Example B: whole video as the opening, extended backward

User request: `Continue on from Video 1 as the opening: the character from Image 1 takes the bouquet and smiles in thanks; Audio 1 is his voice, saying "Thank you so much."`

Organized request:

```text
[Core Task]
Use Video 1 as the opening segment and extend it backward into a video in which a character accepts a bouquet and gives thanks; in the continuation the character's appearance references Image 1, and his voice timbre references Audio 1. The whole video keeps the visual tone established by Video 1.

[Plot Outline]
1. Video 1 plays in full as the opening segment; its picture, sound and order of events stay as they are.
2. The character from Image 1 takes the offered bouquet with both hands, draws it to his chest and nods to the other person with a smile, saying in the voice of Audio 1: "Thank you so much."
3. After the handover, the bouquet is only in his hands.

[Audio Style]
The Video 1 opening keeps its original sound; the continuation keeps live ambience and voices, and the music settles naturally with the thanks.

[Camera and Core Constraints]
The camera style stays continuous from Video 1 into the continuation; subjects, scene direction and sound stay coherent, and the character's appearance and clothing stay stable.
```
