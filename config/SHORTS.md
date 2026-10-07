---
name: tdoffscript shorts
description: Selection rules for YouTube Shorts - turns a film's research sheet and our reaction transcript into a ranked set of self-contained vertical clips.
---

# TDOffScript Shorts selection rules

The long-form cut (`config/SKILL.md`) tells the film's story. **Shorts don't.**
Each short is one moment: the most iconic scenes in the film with our
reaction to them, cut to stop the scroll and get watched twice.

Shorts are built from the same inputs as the long cut, and the research is
already done: **`cuts/<slug>.research.md` is the primary input.** Don't
re-research the film. Read the sheet and mine it.

Anything this file doesn't cover (the TIMESTAMPS rule, the transcript
format, `[OFFSET]`) works exactly as in `config/SKILL.md`.

## WHAT MAKES ONE OF OURS GO VIRAL

Viewers find shorts by what's in them, not by who we are. A short works when a
stranger scrolling past sees these three things in the first seconds:

1. **A moment they recognise or instantly want**: the famous line, the
   monster, the kill, the twist. Recognition stops the thumb.
2. **A real reaction on our faces**: a gasp, a shout, a laugh, one of us
   being dead wrong. That's what they can't get from the film itself.
3. **Payoff fast.** There's no time to set anything up. Whatever needs
   explaining should be explained by the film's own line or picture in a
   couple of seconds, or the moment isn't a short.

## STEP 1 — MINE THE RESEARCH SHEET

Build a candidate list from `cuts/<slug>.research.md`, in this priority:

1. **"What fans come for"**: every item is a candidate. These are the
   moments people search for and quote, and they're the reason the short
   gets found.
2. **`must` beats on the beat sheet**: iconic or plot-critical moments with a
   recording-time range and anchor already located.
3. **"Our running dynamic"**: the biggest reaction peak is an automatic
   candidate. A running bit, like an argument that runs the whole film and
   pays off at the end, is a candidate for a **compilation short** (see
   SHORT TYPES).
4. **`strong` beats** only when our reaction to them is exceptional.

The sheet's recording times and anchors are where to look, not the final
cut points. Always set boundaries from the word-level transcripts.
Where the sheet says the film transcript is empty or missing a line, anchor
on our words as the sheet does.

## STEP 2 — SCORE AND RANK

Score every candidate 1–5 on each axis, then rank by the total:

| axis | 5 means |
|---|---|
| **Iconic** | the film is known for this moment; it's quoted, memed, or in every "best scenes" list |
| **Reaction** | loud, visible, unscripted: shouting, both of us at once, a gasp then silence, a laugh we can't stop |
| **Instant read** | a stranger with no context gets it in under 3 seconds, and it reads on a phone screen |
| **Dynamic** | one of us called it early, got it wrong, or we disagree, and the moment settles it |
| **Loop** | the last beat flows back into the first, or the ending makes you want to see the opening again |

A candidate with **Reaction ≤ 2 is out**, however iconic. A clip of the
film with us sitting quietly is not a short. It's just the film.

Cut the top **5–10** candidates, depending on how many clear the bar. Better
six great shorts than ten where the bottom four are filler. Never make two
shorts from the same moment.

## SHORT TYPES

- **Moment** (the default): one scene. The event, then our reaction to it.
- **Quote**: a famous line lands and we react. Use the line in the title,
  because people search it word for word.
- **Called it / Wrong**: one of us predicts something, then the film
  settles it. The prediction and the payoff can be minutes apart in the
  recording; cut straight from one to the other.
- **Compilation**: a running bit across the whole film, stitched together.
  Only when the bit has a clear payoff at the end. Up to ~4 pieces, each a
  single line, so it still fits in 30 seconds.

## STRUCTURE

A short is **not chronological**. Order segments for impact:

1. **HOOK (first 1–2 seconds).** Open on the single strongest frame: our peak
   reaction (a shout, a gasp, a face), or the most arresting frame of the
   film. No intro, no "okay so", no setup line. It's fine to show the
   reaction first and then rewind to what caused it. That flash-forward is
   the standard short opener.
2. **SETUP (only if needed, ≤ 3 seconds).** The minimum context: usually one
   film line or one of our lines ("wait, is that a tongue?"). Skip it if the
   moment reads without it.
3. **PAYOFF.** The event itself, then us reacting. See the event, then see
   us: the same rule as the long cut. Keep the peak of the reaction, usually
   2–5 seconds, not the whole wind-down.
4. **BUTTON / LOOP.** End on a line, laugh, or look that closes it, ideally
   one that plays naturally into the hook when YouTube loops it. End on the
   last word, not after it. A short that trails off doesn't loop.

A hook that flash-forwards may reuse footage that plays again later in the
short. Segments may overlap in source time and run in any order.

## TIMING

- **Target 15–30 seconds.** Our shorts that have performed are all in this
  range. Never over 35. A moment that needs more is carrying too much setup,
  or is really two shorts.
- **Tight, tighter than the long cut.** Remove every pause longer than ~0.4s
  between spoken lines unless the silence *is* the reaction (a stare, a
  held breath before the explosion).
- **Something changes every 2–4 seconds**: a cut or a new line.
  A single segment over ~5 seconds needs a reason in `reason`.
- The payoff should land **by ~8 seconds** in, 12 at the latest.

## LAYOUTS

Shorts have **two layouts**. Both use the same picture, the vertical stack:

- **Top**: the movie clip, full width, at 16:9.
- **Seam**: captions sit on the line where the movie meets the hosts.
- **Bottom**: Doug and Theresa, filling the rest of the frame.

They differ only in audio. The names are the long cut's, so the cut list
format and clip colours stay the same:

| layout | audio | use it for |
|---|---|---|
| `panel` | movie audio + us | the default: the film's line or sound is part of the moment |
| `panel_hosts_only` | us only, movie muted | we're talking over the film and its audio would muddy our line |

- The picture never changes, so pace comes from cuts and lines (see TIMING).
- Don't use any other layout name in a short.
- The seam caption covers the bottom edge of the movie and the top of our
  frame, so don't pick a moment whose key detail sits at the very bottom of
  the film frame.

## TITLES AND TEXT

For each short, write:

- **`yt_title`**: ≤ 60 characters. Lead with the hook, and name the film:
  viewers search the film. Quote the famous line when there is one.
  E.g. `"Broke into the wrong rec room" 😳 Tremors reaction`.
- **`hook_text`**: 3–7 words of on-screen text for the first 2 seconds,
  shown in the seam caption, stating the tension, not the answer
  (`She did NOT see this coming`).
- **`description`**: one line, then hashtags: `#<Film> #movie reaction
  #firsttimewatching` plus 1–2 specific to the moment.

## OUTPUT

Write `cuts/<slug>.shorts.json`. Shorts go in rank order, best first:

```json
{
  "title": "Tremors",
  "movie_offset_seconds": 242.5,
  "shorts": [
    {
      "name": "Rec room",
      "type": "moment",
      "film_beat": "Basement rec room firefight",
      "score": { "iconic": 5, "reaction": 5, "instant_read": 4, "dynamic": 3, "loop": 3 },
      "yt_title": "...",
      "hook_text": "...",
      "description": "...",
      "segments": [
        { "start": 3821.0, "end": 3823.4, "layout": "panel_hosts_only",
          "reason": "HOOK - flash-forward: our 'oh no no no'" }
      ]
    }
  ]
}
```

Segment fields are the same as the long cut's (`start`, `end`, `layout`,
optional `film_beat` / `iconic` / `reason`). Segments play in the order
listed. `name` becomes the timeline name, so keep it short.

In the chat summary, also report:

- **Ranking**: each short's name, total score, runtime, and one line on why.
- **Cut from the list**: candidates you scored and dropped, with why
  (usually low Reaction), so they can be swapped in.
- **Research gaps**: any iconic moment from the sheet you couldn't find
  in the transcripts.
