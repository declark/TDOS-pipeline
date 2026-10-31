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

If it doesn't exist, the film hasn't been researched yet. Run the
`research-film` skill first (it follows `config/RESEARCH.md` and saves the
sheet there, so the long cut can reuse it later), then carry on.

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

Write each segment's `captions` as SHORTS.md's CAPTIONS section describes:
who says each phrase, on that speaker's word boundaries, with the text
corrected where the transcript misheard it.

After writing the file (step 5), check it, not by eye:

`python src/check_cuts.py --cuts cuts/<slug>.shorts.json`

Every `FAIL` is a hard limit - film audio running past the 6s ceiling, a short
over 35s, a layout that isn't a shorts layout - and the renderer refuses a
short that has one. Fix it and re-run until there are none. Weigh each `WARN`
(a film-audio run past the 4s default needs its why in `reason`; runtime
outside 15–30s).

The checker can't judge these, so check them yourself for each short:

- the payoff lands within the first ~12s;
- the first segment is the hook: it's a reaction or striking frame, not setup;
- every caption's `start`/`end` sits inside its segment;
- no two shorts are built on the same moment.

Once there are no `FAIL`s, cut the dead air out mechanically:

`python src/tighten_cuts.py --cuts cuts/<slug>.shorts.json`

It trims silent, still lead-ins and tails to a 0.1s handle and cuts pauses
inside segments, from the waveforms (ours, and the film's in `panel`). Don't
try to do that by hand from the transcript. Then run `check_cuts.py` once
more: tightening only shortens, so it can't add a `FAIL`, but a short can
drop under the 15s target. If one does, it needs another beat, not padding.

**Revising one short.** When asked to revise a short in an existing file
(feedback from the desktop app), change only that short, leave the others and
their order exactly as they are, then run tighten and the checker again.
Segments carrying `trimmed_from` were already tightened; leave that field alone
on segments you don't change, and drop it from any segment you re-cut.

If `config/SHORTS.md` and this file ever disagree, `config/SHORTS.md` wins.

## 5. Write the output

Save to `cuts/<slug>.shorts.json` in the OUTPUT shape from
`config/SHORTS.md`, with `title` and `movie_offset_seconds` in the wrapper.

Then, in the chat response (not the file), give the **Ranking**, **Cut from
the list** and **Research gaps** from SHORTS.md, the checker's final FAIL /
WARN counts, and the next command:
`python src/render_shorts.py --cuts cuts/<slug>.shorts.json --preview`
(finished videos without Resolve), or
`python src/build_timeline.py --cuts cuts/<slug>.shorts.json --dry-run`
(timelines in Resolve).
