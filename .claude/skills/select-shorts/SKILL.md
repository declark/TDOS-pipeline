---
name: select-shorts
description: Apply config/SHORTS.md to a project's research sheet (cuts/<slug>.research.md) and word-level transcripts, and produce a ranked cuts/<slug>.shorts.json of YouTube Shorts ready for src/build_timeline.py.
---

Runs the shorts-selection pass described in `config/SHORTS.md`: mines the
film's research sheet for its most iconic moments, finds our best reactions to
them in the transcripts, and writes a ranked set of shorts to
`cuts/<slug>.shorts.json`, in the exact shape `src/build_timeline.py` expects.

## 1. Find the project

Same as the `select-cuts` skill: `args` names the project (title or slug);
with no `args`, use the only `cuts/*.media.json`, or ask if there are several.
Read `cuts/<slug>.media.json` for `title`, `reaction_media`, `movie_media`.

## 2. Load the research sheet

Read `cuts/<slug>.research.md` in full. It's the primary input.

If it doesn't exist, the film hasn't been researched yet. Do
`config/SKILL.md`'s STEP 1 (RESEARCH THE FILM) first and save the sheet
there, so the long cut can reuse it later. Load WebSearch / WebFetch via
ToolSearch if needed.

## 3. Load the transcripts and offset

Exactly as `select-cuts` steps 2 and 3: `<media path>.words.json` for both
clips (stop and tell the user to run `src/transcribe.py` if either is
missing), and `movie_offset_seconds` from the media config, the existing
`cuts/<slug>.json`, or the user.

You don't need to read the whole film transcript. The research sheet gives a
recording-time range for every beat. Read the film and reaction words only
around the candidates, with a margin of ~30s either side, converting film time
to recording time with `+ [OFFSET]`.

## 4. Apply config/SHORTS.md

Read `config/SHORTS.md` in full and follow it: mine the sheet, score and rank
the candidates, then cut the top ones. Every `start`/`end` must be a real word
boundary from one of the transcripts, per `config/SKILL.md`'s TIMESTAMPS rule.

Before writing the file, check the draft with a short script in the
scratchpad (not by eye). For each short, check:

- total runtime is ≤ 35s, and flag any outside 15–30s;
- every segment has `end > start` and a known layout;
- any single segment over ~5s has a stated reason;
- the payoff lands within the first ~12s;
- the first segment is the hook: it's a reaction or striking frame, not setup.

Also check that no two shorts are built on the same moment.
Fix anything that fails, then re-check.

If `config/SHORTS.md` and this file ever disagree, `config/SHORTS.md` wins.

## 5. Write the output

Save to `cuts/<slug>.shorts.json` in the OUTPUT shape from
`config/SHORTS.md`, with `title` and `movie_offset_seconds` in the wrapper.

Then, in the chat response (not the file), give the **Ranking**, **Cut from
the list** and **Research gaps** from SHORTS.md, and the next command:
`python src/build_timeline.py --cuts cuts/<slug>.shorts.json --dry-run`.
