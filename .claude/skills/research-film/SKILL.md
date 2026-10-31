---
name: research-film
description: Apply config/RESEARCH.md to a project - research the film on the web, locate every beat in the movie transcript, and write the cuts/<slug>.research.md beat sheet that select-cuts, review-cuts and select-shorts work from.
context: fork
---

Runs the research pass described in `config/RESEARCH.md`: learns the film
from the web, finds its beats in the word-level transcripts, and writes the
research sheet to `cuts/<slug>.research.md`. Stage 1 of 3 for the long cut
(`research-film` → `select-cuts` → `review-cuts`).

## 1. Find the project

`args` (if given) names the project - the movie title or its slug (e.g.
"Repo Man" or "repo-man"). Slugify the same way `src/new_project.py` does:
lowercase, non-alphanumerics collapsed to `-`.

- If `args` gives a slug, use `cuts/<slug>.media.json`.
- If no `args`: look for `*.media.json` in `cuts/`. Exactly one -> use it.
  None -> say to run `python src/new_project.py` first, then stop.
  More than one -> list the titles, say which one is needed, and stop.

Read that file for `title`, `reaction_media`, `movie_media`.

## 2. Load the transcripts and offset

Each clip's transcript is `<media path minus extension>.words.json` (the
default output path `src/transcribe.py` uses). A `.novad.words.json` beside it
is a second pass without the VAD filter; use it to fill gaps.

- If either `.words.json` doesn't exist, say to run
  `python src/transcribe.py --project cuts/<slug>.media.json` first, and stop.
- `movie_offset_seconds` comes from `cuts/<slug>.media.json`, or from an
  existing `cuts/<slug>.json`. If neither has it, stop and say it needs adding
  to `cuts/<slug>.media.json`; the sheet can't be written in recording time
  without it.

The movie transcript for a feature-length film is too long to read at once.
Read it in chunks and build a running map of scenes as you go.

## 3. Apply config/RESEARCH.md

Read `config/RESEARCH.md` in full and follow it. Load WebSearch / WebFetch via
ToolSearch if they aren't already loaded.

If `cuts/<slug>.research.md` already exists, read it and add to it only where
it's thin.

If `config/RESEARCH.md` and this file ever disagree, `config/RESEARCH.md`
wins.

## 4. Write the output

Save to `cuts/<slug>.research.md` in the OUTPUT shape from
`config/RESEARCH.md`. Then report what that file's chat summary asks for, and
the next step: the `select-cuts` skill.
