# TDOS pipeline

Builds a DaVinci Resolve timeline from a list of cuts, using a predefined
multicam clip.

Give it a JSON or CSV list of segments and it lays each one down on a new
timeline as an instance of the same multicam clip, trimmed to that segment's
in/out. It drives Resolve Studio directly through its scripting API - there is
no FCPXML or EDL in the middle.

## How it works

The multicam clip's **angles are the layouts** (`panel`, `pip_circles`,
`hosts_full`, ...), each one pre-composed in Resolve.

The script does **not** set angles. It sets a **clip colour** per segment
according to the layout the cut list asked for, and you switch the angle by
hand during review. The colour is the suggestion; the angle is your call.

Cut selection itself is a separate, human/LLM step - the rules live in
[`config/RULES.md`](config/RULES.md) and produce the cut list this consumes.

## Setup

Resolve Studio must be **open with your project loaded**, and
Preferences > System > General > "External scripting using" set to **Local**.

No dependencies and no virtualenv - it uses Resolve's own bundled module and
the standard library, and runs on stock system Python 3. The API location is
auto-detected on macOS, Windows and Linux; override `RESOLVE_SCRIPT_API` /
`RESOLVE_SCRIPT_LIB` for a non-default install.

## Run it

Per episode, the only thing you supply is the cut list. Nothing in
`config/timeline.json` is episode-specific, so a new film needs no config edit.

```
# See the plan without touching Resolve - always do this first
python3 src/build_timeline.py --cuts cuts/<episode>.json --dry-run

# Build it
python3 src/build_timeline.py --cuts cuts/<episode>.json

# CSV works identically
python3 src/build_timeline.py --cuts cuts/<episode>.csv
```

**The multicam clip is found automatically.** A project normally holds exactly
one, and that is unambiguously the one to cut from. Only a project with two or
more needs `--multicam "<name>"`, and the error lists the candidates.

**The timeline names itself.** In precedence order:

```
--timeline-name  >  config timeline_name  >  cut list "title"
                 >  Resolve project name  >  cut list filename
```

The project name sits above the filename because the project is already named
per episode. **You never have to rename the cut list** - keep a fixed
`cuts/current.json` with no `title` and each episode's timeline takes its
project's name. Set `title` only when you want a name that differs from the
project's.

The dry run prints every segment's source in/out, duration, timeline position,
layout and colour, plus total runtime and the layout split by runtime - enough
to check a cut against `RULES.md`'s 35-45 minute and 60-75% targets before
building anything.

Each run creates a **new** timeline. Nothing is ever overwritten - a name
collision gets a numeric suffix ("Repo Man 2"), so you can iterate on a cut
list and compare versions side by side.

## Cut list format

JSON array, or CSV with the same column names. `start`, `end` and `layout` are
required; `film_beat`, `iconic` and `reason` are carried for your reference and
don't affect the build.

```json
{ "start": 842.10, "end": 848.60, "layout": "panel",
  "film_beat": "...", "iconic": true, "reason": "..." }
```

Times are seconds from the start of the recording, per `config/RULES.md`
(Resolve exports SRT with a 01:00:00:00 start, so subtract 3600).

A JSON object wrapping the array under `segments`, `cuts` or `edit` is also
accepted, so an LLM's output doesn't need reshaping by hand. **Per-episode
facts belong in that wrapper**, which is what keeps the config generic:

```json
{ "title": "Repo Man",
  "movie_offset_seconds": 458,
  "segments": [ ... ] }
```

`title` overrides the timeline name (optional - the project name covers it).
`movie_offset_seconds` is the offset that converts
film-subtitle times to recording time - `RULES.md` needs it as `[OFFSET]` when
selecting cuts; the builder just carries it. See `cuts/repo-man.json`.

## Config

[`config/timeline.json`](config/timeline.json):

Everything here is a standing preference, set once and left alone:

| key | meaning |
| --- | --- |
| `fps` | must match the multicam clip; a mismatch warns loudly |
| `sync_offset_seconds` | added to every timestamp. `0` while multicam frame 0 == recording time 0 |
| `timeline_start_timecode` | `01:00:00:00` |
| `layout_colors` | layout -> one of Resolve's 16 clip colours |

`multicam_clip_name` and `timeline_name` are accepted but deliberately absent:
both are per-episode, and both are derived automatically. Set them only to pin
an unusual project, or pass `--multicam` / `--timeline-name` for a one-off.

## Frame accuracy

Both endpoints are converted from absolute seconds with `Fraction`, so 29.97
and 23.976 stay exact and **error never accumulates** over a 40-minute
timeline. Every cut lands within half a frame of its true time, which is the
property that matters: `RULES.md` requires each timestamp to be an SRT cue
boundary, and cuts that drift land mid-word. A segment's duration is a derived
consequence and may differ from nominal by at most one frame.

Unsupported frame rates fail loudly rather than rounding to a neighbour - a
genuine flat 30 is never treated as 29.97, and vice versa.

## Validation

The cut list is fully validated before Resolve is touched. The build refuses to
run on: `end` <= `start`, negative starts, segments shorter than one frame,
unknown layout names, overlapping or out-of-order segments (the edit is
chronological), colours outside Resolve's 16, or an fps with no exact rate. All
problems are reported at once, not one per run.

## Two Resolve API traps, both verified the hard way

Both were caught only by reading the built timeline back out of Resolve. Both
produced a build that **reported success** and looked right at a glance.
Verify by read-back, not by return value.

**`endFrame` is exclusive.** Much of the community documentation says it is
inclusive. On Resolve Studio 20 it is not: `GetDuration()` comes back as
`endFrame - startFrame`. Passing `round(end*fps) - 1` "for inclusivity"
shortened all 95 segments by exactly one frame - a 95-frame total error that no
spot check would surface. A segment covering `[start, end)` passes
`endFrame = round(end*fps)` unmodified.

**`mediaType` is not a video+audio flag.** `1` means video *only*, `2` means
audio *only*. Passing `1` built a completely silent 38-minute timeline - 95
video clips, 0 audio clips. Omit the key entirely to get both.

See `plan_segments()` and `build_timeline()` in `src/build_timeline.py`.

## Verifying a build

1. Clip count on V1 matches the dry run's segment count.
2. The audio track has the same clip count as V1 - see the `mediaType` trap.
3. Spot-check a cut: park on a clip boundary and compare its source timecode
   against the dry-run table's "source in" column.
4. Clip colours match the "layout" column - scan for them at a glance.
5. Total runtime matches the dry run.
6. Open the multicam in the viewer, confirm angle switching works, then set
   angles per the colour coding.

A read-back check asserting all of this against the cut list is worth running
after any change to the build path.

## Why not FCPXML or EDL

An earlier version of this repo generated FCPXML/EDL via OpenTimelineIO and
imported it. That approach is gone: **neither format can express a Resolve
multicam clip**, so it could not do this job at all.

Driving Resolve directly also retired three problems that route had to work
around - `file://` percent-encoding for paths with spaces and parens,
`<library><event>` wrapping to satisfy Resolve's FCPXML importer, and clip
markers that Resolve's FCPXML importer silently drops. Media relinking stops
mattering too, since the multicam clip is already in the project.
