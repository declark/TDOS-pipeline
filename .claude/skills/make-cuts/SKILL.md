---
name: make-cuts
description: Run the whole long-cut pipeline for a project in order - research-film, then select-cuts, then review-cuts, then src/tighten_cuts.py - ending with a reviewed, tightened cuts/<slug>.json ready for src/build_timeline.py.
---

Chains the three long-cut stages for one film. Each stage is its own skill
and can still be run alone; this just runs them in order and stops if one
can't finish.

## 1. Find the project

`args` names the project (title or slug). With no `args`, use the only
`cuts/*.media.json`, or ask which one if there are several. Work out the slug
once and pass it to every stage.

Before starting, check the things every stage needs, so the chain doesn't
fail halfway:

- `cuts/<slug>.media.json` exists (else: `python src/new_project.py`).
- Both `.words.json` transcripts exist (else:
  `python src/transcribe.py --project cuts/<slug>.media.json`).
- `movie_offset_seconds` is in `cuts/<slug>.media.json`. If it isn't, ask the
  user for it and save it there.

## 2. Run the stages

Invoke each with the Skill tool, passing the slug as `args`, and wait for it
to finish before starting the next.

1. **`research-film`** -> `cuts/<slug>.research.md`. Skip it if the sheet
   already exists and the user didn't ask for it to be redone. If it reports a
   `must` beat it couldn't locate, tell the user and carry on; the cut stage
   anchors those on our lines or the beat's edges.
2. **`select-cuts`** -> `cuts/<slug>.json`. If a cut list already exists, ask
   before replacing it.
3. **`review-cuts`** -> `cuts/<slug>.review.md`, a revised `cuts/<slug>.json`,
   and the cutter's original as `cuts/<slug>.draft.json`.
4. **Tighten** (a script, not a skill): `python src/tighten_cuts.py --cuts
   cuts/<slug>.json`. It cuts dead air out of the hosts-only-audio segments
   from the waveform and keeps the version before as
   `cuts/<slug>.pretighten.json`. If it fails (missing media, or PyAV not
   installed), report that and carry on: the reviewed list is still buildable.

Stop the chain if a stage ends without writing its file, and say which stage
and why. If the review's verdict is that the cut should go back through the
cut stage, run `select-cuts` and `review-cuts` once more with the review's
findings as guidance; don't loop more than that once.

## 3. Report

- The review's verdict, findings by severity, and what it changed.
- What tightening removed (segments tightened, pauses cut, seconds saved),
  and any segments it listed as having no sound at all.
- Final runtime and layout mix (from `python src/check_cuts.py --cuts
  cuts/<slug>.json`).
- The HOOK, and any `must` beat not in the cut.
- The files written, and the next command:
  `python src/build_timeline.py --cuts cuts/<slug>.json --dry-run`.
