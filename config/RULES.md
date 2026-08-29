# TDOffScript selection rules

I'm cutting a movie reaction video down to a highlights version. Two hosts,
Doug and Theresa, watch a film for the first time and react.

## ATTACHED

1. Our commentary transcript (SRT). Timestamps are seconds from the start of
   our recording. Resolve exports with a 01:00:00:00 start, so subtract 3600
   from every value so it's true seconds from recording start.
2. The film's subtitle file (SRT). Timestamps are film time, starting at zero.
   The film begins at [OFFSET] seconds into our recording, so add [OFFSET] to
   every film timestamp to convert it to our recording's timeline.

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
2. **Cover each beat** with a segment showing our reaction, whether or not we
   said anything. Silence during a big beat is a keep, not a skip.
3. **Layer the dynamic on top.** Prefer moments where our reaction to a beat
   IS the dynamic: disagreeing about what just happened, one of us calling it
   early, being wrong and finding out, both going at once.
4. **Then add standalone commentary** strong enough to earn a place on its
   own, but keep these short and keep them rare. See the runtime split below.
5. **Cut** anything that's us narrating what's already visible on screen, dead
   air without payoff, and false starts.

## TARGETS

- **35 to 45 minutes total.**
- **Runtime split: 60 to 75 percent tied to film beats, 25 to 40 percent
  standalone dynamic.** Both bounds matter. Under 60 percent film beats and
  the movie stops carrying the video. Over 75 percent and we've cut out the
  thing that makes the channel worth subscribing to.
- **Story coherence:** someone who has never seen the film should be able to
  follow it start to finish from this cut alone.
- **Pacing:** vary segment length deliberately. Most segments should run 15 to
  45 seconds. Anything over 60 seconds needs to earn it, either a major film
  beat or an exceptional exchange. Avoid long runs of similar-length segments.

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

- **panel**: movie large, us in a panel. Default for watching film beats.
- **pip_circles**: movie fullscreen, us in circles top left and right. For big
  moments where the film needs the screen.
- **hosts_movie_audio**: us fullscreen, movie audio audible. Good for reacting
  to something we're hearing rather than watching.
- **hosts_full**: us fullscreen, no movie. Tangents fully away from the film.
- **host_1** (Doug) / **host_2** (Theresa): punch in on one host. The
  transcript has no speaker labels, so only use these where the line clearly
  belongs to one person, and keep them under 5 seconds.

`panel` and `pip_circles` should carry most of the runtime. `hosts_full` is
the exception, not the default. Don't let any single layout run for more than
about three consecutive segments.

## TIMESTAMPS

Every `start` and `end` value must be an exact timestamp copied from a cue
boundary in one of the two attached SRT files. Never round, never estimate,
never invent a value. If a segment needs to begin between cues, use the
nearest cue boundary. Rounded values produce cuts that land mid-word.

## OUTPUT

A JSON array, timestamps in seconds from OUR recording start:

```json
{ "start": 842.10, "end": 848.60, "layout": "panel",
  "film_beat": "what's happening in the movie here, or null",
  "iconic": true,
  "reason": "why this earns a spot" }
```

Set `iconic` to true only for the film's famous or most-discussed moments.

Then:

- A **HOOK** line: the timestamp range of the strongest short moment, and why.
- A **NEAR MISSES** list of 20 to 30 segments considered and rejected, with
  reasons.

Don't summarize the transcript or explain your approach. Just the lists.