---
name: review-cuts
description: Apply config/REVIEW.md to a project's cuts/<slug>.json - check it against the research sheet, the transcripts and config/SKILL.md, write cuts/<slug>.review.md, then fix the cut list.
context: fork
---

Runs the review pass described in `config/REVIEW.md`: reads a finished cut
list cold, reports what's weak in `cuts/<slug>.review.md`, then applies the
fixes to `cuts/<slug>.json`, keeping the original as `cuts/<slug>.draft.json`.
Stage 3 of 3 for the long cut (`research-film` → `select-cuts` →
`review-cuts`).

## 1. Find the project

Same as the `select-cuts` skill: `args` names the project (title or slug);
with no `args`, use the only `cuts/*.media.json`, or list the titles and stop
if there are several. Read `cuts/<slug>.media.json` for `title`,
`reaction_media`, `movie_media`.

Stop, and say which stage to run first, if either is missing:

- `cuts/<slug>.research.md` -> the `research-film` skill.
- `cuts/<slug>.json` -> the `select-cuts` skill.

## 2. Load the inputs

- `config/SKILL.md` and `config/REVIEW.md`, in full.
- `cuts/<slug>.research.md`, in full.
- `cuts/<slug>.json`. A full cut list is hundreds of segments; read it in
  chunks, and keep a compact per-segment table (number, start, end, layout,
  `film_beat`) to work from.
- The transcripts, `<media path minus extension>.words.json` for both clips
  (plus `.novad.words.json` if present), with `movie_offset_seconds` from the
  cut list's wrapper. The reaction transcript is the one to read end to end
  for the missed-peaks pass. Read the film transcript around the beats and
  segments you're checking, converting with `+ [OFFSET]`.
- `python src/check_cuts.py --cuts cuts/<slug>.json --verbose`

## 3. Apply config/REVIEW.md

Do THE PASSES in order and write THE REPORT to `cuts/<slug>.review.md`.

Then do THEN FIX IT: copy the original to `cuts/<slug>.draft.json`, apply the
fixes to `cuts/<slug>.json`, and re-run the checker until it reports no
`FAIL`. Make the edits with a short script in the scratchpad rather than by
hand-editing hundreds of lines, and keep the file's wrapper keys and segment
shape exactly as they are. Finish with

`python src/build_timeline.py --cuts cuts/<slug>.json --dry-run`

to confirm the build still accepts it.

If `config/REVIEW.md` and this file ever disagree, `config/REVIEW.md` wins;
on the selection rules themselves, `config/SKILL.md` wins over both.

## 4. Report

In the response, give what `config/REVIEW.md`'s chat summary asks for, where
the three files are (`.review.md`, `.json`, `.draft.json`), and the next
command: `python src/build_timeline.py --cuts cuts/<slug>.json --dry-run`.
