---
name: select-cuts
description: Apply config/SKILL.md to a project's reaction + movie word-level transcripts (from src/transcribe.py) and produce a cuts/<slug>.json cut list ready for src/build_timeline.py.
---

Runs the cut-selection pass described in `config/SKILL.md`: reads the two
word-level transcripts for an episode and writes the resulting cut list to
`cuts/<slug>.json`, in the exact shape `src/build_timeline.py` expects.

## 1. Find the project

`args` (if given) names the project - the movie title or its slug (e.g.
"Repo Man" or "repo-man"). Slugify the same way `src/new_project.py` does:
lowercase, non-alphanumerics collapsed to `-`.

- If `args` gives a slug, use `cuts/<slug>.media.json`.
- If no `args`: look for `*.media.json` in `cuts/`. Exactly one -> use it.
  None -> tell the user to run `python src/new_project.py` first, then stop.
  More than one -> list the titles and ask which one.

Read that file for `title`, `reaction_media`, `movie_media`.

## 2. Load the transcripts

Each clip's transcript is `<media path>.words.json` (the default output path
`src/transcribe.py` uses - e.g. `...\repo man shortened.words.json`).

For each of `reaction_media` and `movie_media`:

- If its `.words.json` doesn't exist, tell the user to run
  `python src/transcribe.py --project cuts/<slug>.media.json` first, and stop.
- Otherwise read it. Structure: `{ segments: [ { start, end, text, words: [
  { start, end, word, prob } ] } ] }`, seconds relative to that media file.

The reaction transcript is usually short enough to read in full. The movie
transcript for a feature-length film is not - read it in chunks (e.g. by
byte offset or a handful of `segments` at a time) and build a running map of
candidate film beats as you go, rather than trying to hold the whole thing in
context at once.

## 3. Get movie_offset_seconds

config/SKILL.md needs `[OFFSET]` = how many seconds into the reaction recording the
movie starts playing. Look for `movie_offset_seconds`, in order:

1. `cuts/<slug>.media.json` (if already saved there).
2. `cuts/<slug>.json`, if a previous cut list already exists for this project
   (its wrapper carries this field - see `cuts/repo-man.json` for the shape).
3. Otherwise ask the user for it, then save it into `cuts/<slug>.media.json`
   under the key `movie_offset_seconds` so this step is skipped next time.

## 4. Research the film

Before selecting anything, do config/SKILL.md's STEP 1 (RESEARCH THE FILM):
load WebSearch / WebFetch via ToolSearch if they aren't already loaded, research
the film, and write the beat sheet to `cuts/<slug>.research.md`. If that file
already exists from an earlier run, read it and reuse it, adding to it only
where it's thin.

## 5. Apply config/SKILL.md

Read `config/SKILL.md` in full and follow it exactly - it is the single
source of truth for selection criteria, layouts, the LAYOUT MIX targets, the
BREAKS / source-skip rule, the film-exposure cap (4s default, 6s hard
ceiling), the 6-second hosts-only cap, and the TIMESTAMPS rule
(every `start`/`end` must be a real word boundary from one of the two
transcripts, converted to recording time: reaction words are used as-is, film
words get `+ [OFFSET]`).

Before writing the file, check the draft with a short script in the
scratchpad (not by eye): no overlaps; every film-audio run ≤ 6s, and any run over 4s has
a stated reason and is rare, where a
run only breaks on a ≥ 2s source skip or a `_hosts_only` / `hosts_full`
segment; every us-only run ≤ 6s outside intro/outro; layout shares vs. the
LAYOUT MIX targets; and no repeating layout pattern or run of near-equal
lengths. Fix anything that fails, then re-check.

Do not re-derive or second-guess config/SKILL.md's targets from this file - if the
two ever disagree, config/SKILL.md wins; this file only wires it up to the actual
transcript data.

## 6. Write the output

Save to `cuts/<slug>.json`:

```json
{
  "title": "<title from the media config>",
  "movie_offset_seconds": <offset>,
  "segments": [ /* config/SKILL.md OUTPUT array */ ]
}
```

Then, in the chat response (not the file), give:

- A short summary: total runtime, film-beat vs. standalone split, segment
  count - the same shape `build_timeline.py --dry-run` will print.
- The **layout mix** (actual % per layout vs. target).
- The **HOOK** line.
- **Beat coverage** - any `must` beat from the research sheet not in the cut.
- The **NEAR MISSES** list.
- The next command to run: `python src/build_timeline.py --cuts cuts/<slug>.json --dry-run`.
