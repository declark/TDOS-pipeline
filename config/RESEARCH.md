---
name: tdoffscript film research
description: Research rules for a movie reaction episode - learn the film the way a fan searching for it does, and write the beat sheet the cut and the shorts are built from.
---

# TDOffScript film research

This is the first of three stages for the long-form cut:

1. **Research** (this file) → `cuts/<slug>.research.md`
2. **Cut** (`config/SKILL.md`) → `cuts/<slug>.json`
3. **Review** (`config/REVIEW.md`) → `cuts/<slug>.review.md`

The research sheet is the only thing the later stages know about the film, and
`config/SHORTS.md` mines it too. Nothing gets selected here. The job is to
know this movie the way a fan searching for it does, and to pin every moment
that matters to a place in the recording.

Viewers find us by searching the film, not by searching us. The transcript
alone won't tell you which moments people care about, so the research comes
from outside it.

## ATTACHED

Word-level JSON transcripts from `src/transcribe.py` (see
`segments[].words[]`, each with `start`/`end` in seconds):

1. The film's transcript. Timestamps are film time, starting at zero. The film
   begins at [OFFSET] seconds into our recording (`movie_offset_seconds`), so
   add [OFFSET] to every film timestamp to convert it to recording time.
2. Our commentary transcript, already in recording time. Here it's used only
   to anchor moments the film transcript can't, and for OUR RUNNING DYNAMIC.

## STEP 1 — RESEARCH THE FILM

Use web search (WebSearch / WebFetch) and cover at least:

- **Plot, act by act** — the Wikipedia plot summary (or equivalent), so you
  know the setups, turns, reveals, deaths and the ending, in order.
- **Iconic and most-discussed scenes** — "best scenes", "most iconic moments",
  "scenes everyone remembers" lists, fan discussion, retrospectives. Note which
  moments come up again and again across sources; those are the must-haves.
- **Famous lines** — the quotes the film is known for (IMDb quotes, AFI-style
  lists, memes). These are also your best tool for locating scenes in the film
  transcript.
- **Trivia and context** — twists viewers are primed to wait for, famous
  practical effects or stunts, well-known casting, anything the audience
  expects to see us discover.

Keep the sources. A moment only one page mentions is not iconic; a moment
every list mentions is.

## STEP 2 — BUILD THE BEAT SHEET

Every major beat and every iconic moment, in film order, each with:

- a one-line description,
- an importance rank: `must` = iconic or plot-critical, `strong`, `optional`,
- its range in **recording time** (film time + [OFFSET]),
- an anchor: the famous line or scene dialogue that locates it, with its time.

Find each beat by matching famous lines or scene dialogue in the film
transcript. For visual-only moments with no dialogue, anchor on the nearest
dialogue before and after and say the moment sits between them, or anchor on
one of our lines in the reaction transcript ("our '…' 1135").

Rank honestly. `must` is for what fans would be annoyed to find missing and
what the story can't be followed without. A sheet where everything is `must`
gives the cut nothing to trade against runtime.

The beat ranges should cover the film end to end with no large holes, so the
cut can follow the story from them alone.

## STEP 3 — CHECK THE TRANSCRIPT

The film transcript has gaps: the VAD filter drops dialogue under score or
effects, and famous lines get misheard. Before finishing:

- Look for long stretches of film with no words where the plot summary says
  there is dialogue. If a `--no-vad` pass exists
  (`<media>.novad.words.json`), use it to fill them; if not, say in the sheet
  that one would help.
- For each famous line, confirm it's in the transcript. If it was misheard or
  is missing, record what the transcript has instead, or anchor the moment on
  our line or the beat's edges.
- The reaction mic picks up the film's audio, so film lines can echo into our
  transcript a second or two late. Don't mistake an echo for our commentary.

## OUR RUNNING DYNAMIC

Skim our transcript for what runs through the whole watch: an argument that
keeps coming back, a prediction that pays off or blows up, a running joke.
Record each with its time range and the lines that mark it. Also record the
**biggest reaction peak** in the recording, with its time range and the words
around it.

This is a note for the later stages, not a selection. Keep it to a few lines.

## OUTPUT

Save to `cuts/<slug>.research.md` with these sections, in this order and with
these headings (the later stages look for them):

```markdown
# <Title> (<year>) — research & beat sheet

Offset: film starts at **<offset>s** in the reaction recording (`<reaction file>`).
Times below are **recording time** (film time + <offset>).

## Transcript notes

Gaps, misheard lines, which passes were used. Omit if there's nothing to say.

## Sources

- [Name](url): what it was used for

## What fans come for

- **The moment or line**: why it matters, in a sentence.

## Beat sheet (film order)

| rank | beat | recording time | anchor |
|---|---|---|---|
| **must** | One-line description | 905–990 | "the famous line" 921 |
| strong | ... | ... | ... |

## Our running dynamic

- **The bit**: where it runs and the lines that mark it.
- **Biggest reaction peak:** range and the words around it.
```

If the sheet already exists, read it and add to it only where it's thin.
Don't redo research that's there.

In the chat summary, report:

- how many beats at each rank,
- any `must` beat or famous line that couldn't be located in the transcript,
  and what it's anchored on instead,
- any transcript gap that a `--no-vad` pass would fix.
