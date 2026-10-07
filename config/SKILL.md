---
name: tdoffscript edit pipeline
description: this will create a json file that will be used to produce a davinci resolve project cut list. 

---

# TDOffScript selection rules

I'm cutting a movie reaction video down to a highlights version. Two hosts,
Doug and Theresa, watch a film for the first time and react.

## ATTACHED

Both are word-level JSON transcripts from `src/transcribe.py` (see
`segments[].words[]`, each with `start`/`end` in seconds), not SRT files.

1. Our commentary transcript, from the reaction recording directly.
   Timestamps are already true seconds from the start of our recording - no
   offset needed.
2. The film's transcript, from the movie file directly. Timestamps are film
   time, starting at zero. The film begins at [OFFSET] seconds into our
   recording (`movie_offset_seconds`), so add [OFFSET] to every film
   timestamp to convert it to our recording's timeline.

## THE CHANNEL

Viewers find us by searching the film, not by searching us. They arrive for
the movie. What makes them stay and subscribe is the couple dynamic: two
people who've never seen this reacting to it together, disagreeing, being
wrong, calling things early.

Both halves matter. The film is the draw, the dynamic is the reason to come
back. The cut has to serve both, and the way it does that is by putting the
dynamic on top of film beats rather than in place of them. A disagreement
that happens during a scene is worth more than the same disagreement floating
free of the movie.

## WHAT THE AUDIENCE WANTS

Viewers have told us directly: they want to watch us react, not listen to us
talk through the movie. Silent reaction beats commentary. Our faces during a
reveal are worth more than a clever line about it.

This means the commentary transcript is a weak signal for the moments that
matter most, because our best reactions produce no words at all. Never treat
"there's a good line here" as sufficient reason to keep something.

## STEP 1 — RESEARCH THE FILM (before touching the transcripts)

Do not start selecting until you know this movie the way a fan searching for
it does. The transcript alone won't tell you which moments people care about.
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
  practical effects or stunts, anything the audience expects to see us
  discover.

Then build a **beat sheet**: every major beat and every iconic moment, in film
order, each with:

- a one-line description,
- an importance rank (`must` = iconic / plot-critical, `strong`, `optional`),
- its location in the film transcript (film-time `start`/`end`), found by
  matching famous lines or scene dialogue. For visual-only moments with no
  dialogue, anchor on the nearest dialogue before and after and note that the
  moment sits between them.

Save it to `cuts/<slug>.research.md` (with the sources you used) so it can be
reviewed and reused. Every `must` beat has to be in the final cut, even if our
reaction to it is mild — the film moment itself is the payload. If a `must`
beat can't be located in the transcript, say so in the chat summary rather than
silently dropping it.

## STEP 2 — FIND OUR REACTION PEAKS

For every beat on the sheet, find how we reacted in the recording (film time
+ [OFFSET] = recording time). Signals of a big reaction in our transcript:

- exclamations and shouts: "oh my god", "no no no", "what?!", "wait", "are
  you kidding", swearing, a name yelled at the screen;
- both of us talking at once, or rapid short back-and-forth;
- a burst of words right after a stretch of silence during a big beat
  (silence while the event plays, then the explosion);
- laughter, gasps, or transcribed noises;
- one of us calling something early, then the film proving them right or
  wrong.

A long silence from us during a `must` beat is not a miss — it's usually us
glued to the screen, and that's a keep.

## STEP 3 — HOW TO SELECT

Work from the beat sheet, not our transcript.

1. **Cover every `must` beat**, then `strong` beats as runtime allows, with the
   peak of our reaction — trim to the beat's best stretch rather than carrying
   the whole scene.
2. **See the event, then see us.** When we yell, gasp, or are shocked, the
   viewer must first see WHAT shocked us, then the cut shifts focus to our
   faces. Pattern: the event plays (`pip_circles` if it's a big visual, `panel`
   otherwise) up to or just into the moment it lands → cut to a layout that
   centres us (`panel`, `panel_hosts_only`, or a short `hosts_full`) for the
   reaction. Never show our reaction before the thing we're reacting to, and
   never cut away from the event so early that the viewer misses it.
3. **Layer the dynamic on top.** Prefer moments where our reaction to a beat
   IS the dynamic: disagreeing about what just happened, one of us calling it
   early, being wrong and finding out, both going at once.
4. **Then add standalone commentary** strong enough to earn a place on its
   own, but keep these short and rare.
5. **Cut** anything that's us narrating what's already visible on screen, dead
   air without payoff, and false starts.

## TARGETS

- **35 to 50 minutes total.**
- **Story coherence:** someone who has never seen the film should be able to
  follow it start to finish from this cut alone. The beat sheet is the
  checklist.
- **The movie is on screen almost the whole time.** Us-only footage
  (`hosts_full`, `hosts_movie_audio`) never runs longer than 6 seconds except
  the intro and outro (see CONTINUOUS HOSTS-ONLY).
- **Layout mix** — see LAYOUT MIX below. Check it before writing the file.

## INTRO

The first segment is the intro and it must be short and clear. Under 20
seconds. It needs to establish only: the film, that we've never seen it, and
that we're going in cold. No preamble, no housekeeping, no throat-clearing.

Separately, identify the strongest 5 to 15 second moment in the whole
recording as a hook candidate. Don't move it in the cut; the edit stays
chronological. Just tell me where it is so I can decide whether to open with
it.

## LAYOUTS

Assign one per segment. We are ALWAYS on screen; there is never movie-only
footage.

| layout | picture | audio |
|---|---|---|
| `panel` | hosts large, movie in a panel | film + us |
| `panel_hosts_only` | hosts large, movie in a panel | us only (film muted) |
| `pip_circles` | movie fullscreen, us in circles | film + us |
| `pip_circles_hosts_only` | movie fullscreen, us in circles | us only (film muted) |
| `hosts_movie_audio` | us fullscreen | film + us |
| `hosts_full` | us fullscreen | us only |

### When to use which

- **`panel` — the workhorse.** Most reaction footage lives here. It keeps us
  big and the film small, which is what viewers want (our faces) and limits
  how much of the film's picture ends up in the video. Default to `panel`
  unless one of the rules below clearly calls for something else. Hard cuts
  from one `panel` segment to another `panel` segment at a later point in the
  film are fine and expected (see BREAKS).
- **`pip_circles` — selective, for major on-screen moments.** Reserve it for
  the film's big visual beats — the reveal, the monster, the stunt, the
  iconic shot — where the viewer needs to actually see the picture to get it.
  Lead `must` beats with it when the moment is visual. Also use it
  occasionally to break up a long stretch of `panel` so the video doesn't
  look the same for minutes at a time. It is a spice, not the base.
- **`panel_hosts_only` / `pip_circles_hosts_only` — when we're talking about
  the film.** Use these when our conversation is the content: discussing what
  just happened, theorising, disagreeing, calling it early. Choose them when
  what's on screen is either relevant background to what we're saying or
  unimportant — either way the film's audio isn't needed, so mute it and let
  us be heard clean. `panel_hosts_only` is the usual choice;
  `pip_circles_hosts_only` when the image on screen is what we're talking
  about and deserves to be big.
- **`hosts_full` — short reaction cutaways.** The "focus on us" shot after a
  shock, a laugh, a big look between us. Also the intro and outro. Short.
- **`hosts_movie_audio` — rare.** Reacting to something we're hearing rather
  than seeing. It still exposes the film's audio, so use sparingly.

### LAYOUT MIX

Share of total runtime (intro and outro included):

| layout | target |
|---|---|
| `panel` | **60–70%** |
| `panel_hosts_only` + `pip_circles_hosts_only` | ~15–25% |
| `pip_circles` | ~10–15% |
| `hosts_full` + `hosts_movie_audio` | ≤ ~8% |

These are targets for the whole cut, not per scene — a big `must` beat can
lean on `pip_circles`, a talky stretch can lean on `_hosts_only`. Compute the
actual shares before writing the file; if `panel` is outside 60–70% or
`pip_circles` is over ~15%, rebalance.

## BREAKS — NO CONTINUOUS FILM FOOTAGE

The film must never play continuously for long in our video. Content-ID-style
systems match on continuous stretches of the film's audio and picture, so
between film chunks there must be a real break.

**A break is any of:**

1. **A source skip (the main one).** The next segment starts at a later point
   in the recording, dropping at least **2 seconds** of film between the end of
   one segment and the start of the next. The result is a hard cut to a
   different moment in the movie — `panel` → `panel` is perfectly fine here.
   Vary the size of the skips: sometimes a couple of seconds, sometimes a
   whole scene.
2. **A film-audio-muted segment** (`panel_hosts_only`,
   `pip_circles_hosts_only`, `hosts_full`) — used when we have something to
   say or a reaction to show.

**Never butt two film-audio segments together on contiguous source time.**
Two segments where the second picks up within 2 seconds of where the first
ended are one continuous run, whatever their layouts, and must be treated as
one for the cap below.

### CONTINUOUS FILM EXPOSURE — HARD LIMIT

A **continuous run** is consecutive segments that expose the film's audio
(`panel`, `pip_circles`, `hosts_movie_audio`) with no break (as defined above)
between them.

**The rule:** a continuous run defaults to a maximum of **4 seconds.** It may
stretch to an absolute ceiling of **6 seconds** only when cutting at 4 would
break something that matters — a line of dialogue that would be chopped
mid-sentence, the payoff of a `must` beat landing just after 4s, or no usable
word boundary near the 4s mark. When a run goes past 4s, say why in that
segment's `reason`. Nothing goes past 6s — no moment, however iconic, earns an
exception. Most runs should land around 2–4 seconds and vary in length;
over-4s runs should be the exception, not a habit.

A beat whose best stretch runs longer than 4 seconds is split: a chunk of
exposure, a break (a source skip that trims the least important few seconds,
or a `_hosts_only` / `hosts_full` reaction), another chunk, and so on. All the
pieces carry the same `film_beat` value.

Picture-only layouts (`_hosts_only`) are exempt from the audio cap, but the
picture can still be matched, so keep each one to the length of the commentary
it carries, not longer.

Illustration of one 25-second iconic scene (not a template — don't reuse
these lengths or this order):

| # | layout | length | break before next |
|---|---|---|---|
| 1 | pip_circles | 3.5s | cut to reaction |
| 2 | hosts_full | 1.5s | source skip 3s |
| 3 | panel | 2.5s | source skip 6s |
| 4 | panel | 5s (line runs past 4s) | cut to our talk |
| 5 | panel_hosts_only | 4s | — |

### CONTINUOUS HOSTS-ONLY — HARD LIMIT

Viewers came for the movie. Consecutive us-only segments (`hosts_full`,
`hosts_movie_audio`, any order) must not add up to more than **6 seconds**
before a movie-on-screen layout appears. Only the intro and outro are exempt.
A reaction or exchange that needs longer plays over the movie
(`panel` / `panel_hosts_only`).

## MAKE IT FEEL EDITED BY A PERSON

Cuts should feel organic, not robotic. A human editor cuts on meaning — a
line landing, a look, a laugh, the moment a shock hits — not on a timer.

- **Cut on motivation.** Every cut should have a reason: the event landed, one
  of us reacted, the conversation turned, the scene changed. If you can't name
  the reason, move the cut.
- **Vary everything.** Segment lengths (quick 1–2s beats, lots in the middle,
  only a few stretching past the 4s default), break types (source skip vs. `_hosts_only` vs.
  `hosts_full`), skip sizes, and how many chunks go by between breaks.
- **No repeating patterns.** Don't let the same sequence of layouts repeat
  (e.g. `panel` → `hosts_full` → `panel` → `hosts_full` …), and don't let three
  or more segments in a row share nearly the same length. After drafting,
  scan the list: if a stretch reads like a metronome, rework it.
- **Let moments breathe when they earn it.** A big reaction can hold a beat
  longer on us; a quick gag can be a snap cut. Not every beat gets the same
  treatment.

## TIMESTAMPS

Anchor every segment on real word boundaries from the transcripts (a word's
`start` or `end` time), converted to recording time per ATTACHED above. Never
invent a value out of thin air, and never place a boundary in the middle of a
word. Find the first and last word the segment should contain from one of the
two transcripts.

Then give the segment a little air so words don't sound clipped:

- `start` = the first word's `start` **minus about 0.25s**
- `end` = the last word's `end` **plus about 0.25s**

Clamp the handle so it never reaches into a neighbouring word we are NOT
keeping: if there's less than ~0.25s of gap, take only the gap that's there,
down to zero. Segments must never overlap (the build rejects that).

For a silent-reaction segment with no spoken words in it, anchor it on the
film's word boundaries or the beat's edges — the handle protects speech, it
doesn't pad silence. The ≥2s source-skip rule is measured after padding.

## OUTPUT

A JSON array, timestamps in seconds from OUR recording start:

```json
{ "start": 842.10, "end": 848.60, "layout": "panel",
  "film_beat": "what's happening in the movie here, or null",
  "iconic": true,
  "reason": "why this earns a spot" }
```

Set `iconic` to true only for beats ranked `must` on the beat sheet because
they're famous or most-discussed.

In the chat summary, also report:

- **Layout mix** — actual % of runtime per layout vs. the LAYOUT MIX targets.
- **HOOK** — the hook candidate (see INTRO).
- **Beat coverage** — any `must` beat not in the cut, and why.
- **NEAR MISSES** — strong moments left out for runtime, with timestamps, so
  they can be swapped in.
