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

## HOW TO SELECT

Work from the film's beats first, not our transcript.

1. **Map the film.** From its subtitles, identify the major moments: reveals,
   twists, deaths, shocks, big turns, the ending. Also identify the film's
   iconic or most-discussed moments, the ones someone searching this title
   arrives hoping to watch us see. These must be in the cut even if our
   reaction to them is mild. The film moment itself is the payload.
2. **Cover each beat** with the peak of our reaction, whether or not we said
   anything — this is a highlights cut, so trim to the beat's best stretch
   rather than carrying the whole scene. If that stretch runs longer than the
   6-second film-exposure cap (see CONTINUOUS FILM EXPOSURE below), split it
   into multiple segments across layouts with a real break between them,
   rather than holding one layout past the cap. Segments produced this way
   all carry the same `film_beat` value. Silence during a big beat is a keep,
   not a skip.
3. **Layer the dynamic on top.** Prefer moments where our reaction to a beat
   IS the dynamic: disagreeing about what just happened, one of us calling it
   early, being wrong and finding out, both going at once.
4. **Then add standalone commentary** strong enough to earn a place on its
   own, but keep these short and keep them rare. See the runtime split below.
5. **Cut** anything that's us narrating what's already visible on screen, dead
   air without payoff, and false starts.

## TARGETS

- **35 to 50 minutes total.**
- **The movie is on screen almost the whole time.** Us-only footage — where the
  movie picture is off screen (`hosts_full`, and `hosts_movie_audio`) — must
  never run longer than **6 seconds** except the intro and outro (see
  CONTINUOUS HOSTS-ONLY below). Across the whole cut, us-only footage should be
  a clear minority: aim for the movie visible (`panel` / `pip_circles`) in at
  least **65 percent** of the runtime.
- **The dynamic plays over the movie, not instead of it.** The couple dynamic
  still carries the video, but it now happens OUT LOUD OVER the film —
  disagreeing, calling things early, being wrong — with the movie on screen
  behind us (`panel` / `pip_circles`), rather than on a full-screen us-only
  tangent. There is no long-tangent layout in the body any more.
- **Story coherence:** someone who has never seen the film should be able to
  follow it start to finish from this cut alone.
- **Pacing:** vary segment length within the caps. Because BOTH film exposure
  and us-only footage are capped at 6 seconds, the body of the cut is a fast
  alternation — at most ~6 seconds of movie, a short us-only cutaway, movie
  again — so expect a lot of cuts. Let the film chunks breathe up toward the
  6-second cap and keep the us-only cutaways short. Avoid long runs of
  identical-length segments.

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

- **panel**: hosts large, movie in a panel. Best when our reaction or talk is
  the focus, and the default for standalone riffs where the movie only needs to
  be present, not centred.
- **pip_circles**: movie fullscreen, us in circles top left and right. The film
  gets the screen. Use it heavily through film beats, alternating with `panel`
  from one movie chunk to the next so a beat isn't all one look, and always lead
  the iconic moments with it. Across the cut, `pip_circles` should carry a large
  share of the on-screen-movie time, not just the occasional big moment.
- **hosts_movie_audio**: us fullscreen, movie audio audible. Good for reacting
  to something we're hearing rather than watching.
- **hosts_full**: us fullscreen, no movie. Short cutaways to us between film
  chunks, plus the intro and outro. Never a long tangent.

`panel` and `pip_circles` carry the large majority of the runtime — the movie
should be on screen by default. `hosts_full` is the exception: short cutaways
only, never the default. See CONTINUOUS FILM EXPOSURE and CONTINUOUS HOSTS-ONLY
below for the hard limits that bound how long either side may run.

## CONTINUOUS FILM EXPOSURE — HARD LIMIT

Content-ID-style systems match on the film's own audio/video, not on our
layout choice. So exposure is tracked per FILM content, across layout
changes, not per segment:

- **Full exposure** (film picture AND audio): `panel`, `pip_circles`.
- **Audio exposure** (film audio only): `hosts_movie_audio`.
- **No exposure** (neither): `hosts_full`.

**The rule:** any run of consecutive segments that are Full or Audio exposure
— any order, any mix of `panel` / `pip_circles` / `hosts_movie_audio` — must
not add up to more than **6 seconds** before a `hosts_full` segment appears.
This is a hard ceiling, not a target — no moment, however iconic, earns an
exception.

What this means in practice:

1. `panel` and `pip_circles` must never sit directly next to each other.
   Switching between them changes the layout but not the exposure - the film
   is rolling the whole time either way, so back-to-back they share one
   6-second budget, not two.
2. `hosts_movie_audio` may sit between two exposure segments for visual
   variety, but it does NOT reset the clock - the film's audio is still
   playing. Only `hosts_full` (true silence from the film) resets it.
3. A beat whose peak runs longer than 6 seconds of film exposure is cut into
   pieces: a few seconds of exposure, a real break, a few more seconds of
   exposure, another break, and so on for as long as the beat earns it. Every
   piece keeps the same `film_beat` value - this is the one case where
   adjacent same-`film_beat` segments are correct, not duplication.
4. Every boundary this creates still needs a real SRT cue boundary (ours or
   the film's) per TIMESTAMPS below. If neither transcript has one near the
   6-second mark, cut at the nearest boundary BEFORE 6 seconds - never after.
   A segment that runs a little short to respect the cap is correct; one that
   runs over is not.

Example - an iconic 20-second reveal, previously one long `panel` segment:

| # | layout      | length | running exposure |
|---|-------------|--------|-------------------|
| 1 | panel       | 5s     | 5s                |
| 2 | hosts_full  | 2s     | reset (break)     |
| 3 | pip_circles | 5s     | 5s                |
| 4 | hosts_full  | 2s     | reset (break)     |
| 5 | panel       | 6s     | 6s                |

Five segments, all sharing `film_beat`, instead of one - this is what "cover
the beat" means once it runs longer than 6 seconds of film exposure.

## CONTINUOUS HOSTS-ONLY — HARD LIMIT

The mirror of the film-exposure cap, for the opposite reason: viewers came for
the movie, so we must not sit on us-only footage. "Us-only" means the movie
picture is off screen:

- **Us-only** (no movie picture): `hosts_full` (no movie at all) and
  `hosts_movie_audio` (movie audio only, us full-screen).
- **Movie on screen**: `panel`, `pip_circles`.

**The rule:** any run of consecutive us-only segments — `hosts_full` and/or
`hosts_movie_audio`, in any order — must not add up to more than **6 seconds**
before a `panel` or `pip_circles` segment (movie back on screen) appears. The
ONLY exceptions are the intro and the outro, which may run longer.

Together with the film-exposure cap, this makes the body of the cut a strict
alternation: at most ~6 seconds of movie, then a short us-only cutaway, then
movie again, and so on. A reaction or exchange that needs more than 6 seconds
plays OVER the movie (`panel`) rather than on us alone. The two caps between
them mean neither side — movie nor hosts — is ever held for longer than 6
seconds anywhere except the intro and outro.

## TIMESTAMPS

Every `start` and `end` value must be an exact word boundary (a word's
`start` or `end` time) copied from one of the two attached transcripts -
converted to recording time per ATTACHED above. Never round, never estimate,
never invent a value. If a segment needs to begin between words, use the
nearest word boundary. Rounded values produce cuts that land mid-word.

## OUTPUT

A JSON array, timestamps in seconds from OUR recording start:

```json
{ "start": 842.10, "end": 848.60, "layout": "panel",
  "film_beat": "what's happening in the movie here, or null",
  "iconic": true,
  "reason": "why this earns a spot" }
```

Set `iconic` to true only for the film's famous or most-discussed moments.