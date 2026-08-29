# TDOS pipeline - FCPXML/EDL round-trip test

This is a throwaway spike, not the pipeline itself. Before building anything
that turns a JSON edit list into a real DaVinci Resolve timeline, it needs
to be proven that the intended mechanism actually works end to end:

**OpenTimelineIO can build a timeline in Python and export FCPXML or EDL
that Resolve imports with the right clip count, the right in/out points
down to the frame, and layout visible on each clip via its name** (via a
marker too, for FCPXML - but confirmed by hand that Resolve's FCPXML
importer doesn't bring clip markers in at all; see "Known simplifications").

If that doesn't hold up, the rest of the pipeline (transcription, segment
selection, layout decisions) has nowhere to land. This test isolates just
the OTIO -> FCPXML/EDL -> Resolve link so that failure is easy to diagnose.
EDL is the leaner path (pure cuts on one video track, no PIP compositing),
and may end up replacing FCPXML entirely - see `--format` below.

## What's here

- `src/build.py` - reads `sources.json` + `edit.json`, builds an OTIO
  timeline, writes `test/cut.fcpxml` or `test/cut.edl` depending on
  `--format`.
- `test/edit.json` - 15 hand-written segments (placeholder timestamps) that
  exercise both adjacent cuts and gaps on a single video track.
- `test/sources.json` - template for the two source media paths, fps, and
  target resolution.
- `test/VERIFY.md` - what to check by hand after importing `cut.fcpxml`
  into Resolve.

## Setup

```
pip install -r requirements.txt
```

`requirements.txt` pins `opentimelineio==0.16.0` specifically because that's
the last release whose wheel still bundles the `fcpx_xml` adapter in
`opentimelineio_contrib`. Newer releases split FCPXML support into a
separate package, which this test avoids depending on. This same pinned
install also has everything needed for `--format edl` (see below) - no
extra package required for that format today.

## Run it

```
python src/build.py
```

That writes **both** `test/cut.fcpxml` and `test/cut.edl` from one build,
which is the default. Spelled out in full, the defaults are:

```
python src/build.py --sources test/sources.json --edit test/edit.json \
    --format both --mode compact
```

### `--format`: both | fcpxml | edl

`both` (the default) writes each format in turn from a single
`build_timeline()` result - neither writer mutates the timeline (the EDL
path deepcopies the tracks it keeps), so the two files can't drift out of
sync with each other. Pass `fcpxml` or `edl` to write just one.

- **fcpxml** (default) - via the pinned 0.16.0 `fcpx_xml` contrib adapter,
  same as before. Writes `test/cut.fcpxml`.
- **edl** - via OTIO's `cmx_3600` adapter, which is core OTIO code (it has
  never lived in `opentimelineio_contrib`), so the EDL path doesn't touch
  any of the `fcpx_xml`-specific, 0.16.0-pinned machinery in `build.py`
  (`patch_frame_duration_table()` etc.). Writes `test/cut.edl`. Each
  event's reel name comes from `REEL_NAMES` in `build.py`
  (`HOST`/`MOVIE`, <=8 chars, matching `cmx_3600`'s default reel-name
  limit) rather than the source file's basename, so Resolve's relink list
  reads cleanly. The layout marker also survives into the EDL as a
  `* LOC:` comment per event (OTIO translates clip markers to CMX
  locators) - worth checking in `test/VERIFY.md` whether Resolve's EDL
  importer surfaces that as an actual marker or just leaves it as an inert
  comment.

  **EDL only ever represents V1 - V2 (see "Video and audio layering"
  below) never makes it in.** Two separate reasons, confirmed by reading the
  pinned adapter's source (`opentimelineio/adapters/cmx_3600.py`,
  `write_to_string()`):
  - It hard-requires exactly one video track
    (`if len(video_tracks) != 1: raise ...`), so `write_timeline()` builds
    a throwaway copy of the timeline with V2 dropped (`track.deepcopy()`
    of V1 into a fresh `Timeline`) before handing it to the writer -
    otherwise every `--format edl` run would raise `NotSupportedError`.
  - Audio tracks are accepted - up to 2, validated - and then silently
    discarded anyway: the actual EDL content only ever comes from
    `get_content_for_track_at_index(0, ...)`. Moot here, since the
    timeline has no audio tracks (audio rides with each `<asset-clip>`),
    but it means EDL could not carry audio even if it did.

  Net effect: `test/cut.edl` reflects only `video_source_for_layout()`'s
  pick per segment - no movie overlay, no audio.
  This is a limitation of this OTIO version's writer, not a bug in
  `build.py` - there's no fix available on the writer side without
  monkeypatching the installed package or moving to a different EDL
  adapter. Use FCPXML when V2 needs to be visible in the export.

  **Careful with the version pin**: `cmx_3600` being core in 0.16.0 does
  *not* mean it's core in current OTIO. As of 0.17, OTIO split *every*
  built-in adapter (not just `fcpx_xml`) out of the main wheel, `cmx_3600`
  included - confirmed by installing plain `opentimelineio` (latest, 0.18.1)
  and finding only `otio_json`/`otioz`/`otiod` registered. `cmx_3600` comes
  back via the separate, OTIO-project-maintained `otio-cmx3600-adapter`
  package. So "drop the version pin and the contrib adapter entirely" (once
  EDL is confirmed working in Resolve) means: unpin to current
  `opentimelineio`, drop `fcpx_xml`/FCPXML support, add
  `otio-cmx3600-adapter` as a normal dependency, and delete
  `patch_frame_duration_table()` and `_fcpx_xml_adapter_module()` along with
  the fcpxml code path in `build.py`. It's still a real simplification
  (one small, actively-maintained package instead of a pinned old release),
  just not literally "zero extra dependencies" the way the phrase "core
  adapter" might suggest.

### `--mode`: compact | inplace

Controls where segments land on the output timeline. Either way, each
clip's in/out point *into the source media* is unchanged - this only
affects whether gaps get inserted between clips on the output track.

- **compact** (default) - segments are appended back-to-back with no gaps.
  This is the real use case: a 2-hour source with 40 minutes of selected
  segments becomes a 40-minute cut.
- **inplace** - segments stay at their source positions, with `Gap`s
  filling the space between them. Useful for reviewing selections against
  the original, since the output timeline's shape still matches the
  source's.

`test/VERIFY.md`'s reference table was built against `--mode inplace`
(the only mode that existed when it was written) - pass `--mode inplace`
if you're following that checklist verbatim; the frame numbers won't match
under `--mode compact`.

## Video and audio layering

`build_timeline()` builds two tracks, V1 and V2. **There are no separate
audio tracks, deliberately** - each clip becomes an FCPXML `<asset-clip>`,
which references an asset and carries that asset's video *and* audio
together. Modelling audio as its own OTIO track is what produced the
gap-wrapped `<audio>` junk described in fix 6 below, so the audio rides
with its picture instead. That only works because fix 7 flags each asset
`hasAudio="1"` - without it the adapter marks every asset silent and the
export imports as picture only.

- **V1 - the hosts, always.** Carries `video_source_for_layout()`'s pick
  (host, for every layout in this dataset), with the host's own sound.
- **V2 - the movie, on every segment.**
  `secondary_source_for_layout()` in `src/build.py` returns the other
  source unconditionally, so V2 gets a movie clip at the same output
  position, in sync with V1, for every layout - `panel` and `hosts_full`
  included, not just `pip_circles`/`hosts_movie_audio`. Layout tags
  describe how a segment should eventually be *composited*, not whether
  the footage is on hand to composite with, so the movie is laid in
  everywhere and the arranging happens in Resolve. In the FCPXML this
  becomes an `<asset-clip lane="1">` nested inside V1's, carrying the
  movie's own audio with it.

  The only thing that leaves V2 empty is physical: a segment playing
  before the movie started rolling has no movie frames to point at. With
  the current data that's exactly one segment - `01_hosts_full`, starting
  at 2.566s, before `movie_offset_seconds` (70) - which gets a
  same-duration `Gap` so later V2 clips stay correctly positioned.

Since a segment's `start`/`end` in `edit.json` are expressed in its
*primary* source's timeline (see "fps handling" below), placing a V2
clip from the *other* source at the same moment needs those seconds
converted into that source's own timeline first. That's what
`sources.json`'s `movie_offset_seconds` is for:
`seconds_in_other_source()` applies
`movie_time = host_time - movie_offset_seconds` (and the reverse for a
movie-primary segment's V2). Get the sign of that offset wrong and
whatever lands on V2 will be in sync with nothing.

**The offset has no size limit and may be negative.** A long lead-in
before you hit play (538s, 20 minutes, whatever) is fine - segments that
land before the movie started simply get a `Gap` on V2 instead of an
error. A *negative* offset means the movie started BEFORE the host
recording did. Since large offsets silently strip the movie off the front
of the cut, every run reports coverage so a mistyped value is obvious:

```
Movie on 88/95 segments (movie_offset_seconds=538)
  7 segment(s) start before the movie did, so they have hosts only.
```

with an extra warning if nothing at all gets the movie. Past the point
where no segment references it, the movie is dropped from `<resources>`
entirely, so Resolve never asks you to relink a file the cut doesn't use. A segment that
would need movie time before the movie file even starts (e.g. host
banter before hitting play) gets a `Gap` there, rather than a
fabricated negative timecode - `seconds_in_other_source()` returns `None`
for that case instead of raising, since it's expected data, not a
misconfiguration. Any source pairing other than host<->movie has no
defined mapping and fails loudly (`SystemExit`) rather than guessing.

**This only builds track structure and timing, not a visual composite** -
see "Known simplifications" below for what's still manual in Resolve.

V2 only affects `--format fcpxml` - see the EDL section above for why
EDL only ever represents V1.

## Media paths across platforms (generate on macOS, import on Windows)

The spec calls for media paths to be written in a form Windows Resolve can
resolve, since generation may happen on macOS while import happens on
Windows. What's actually implemented, per format:

- **fcpxml**: `to_media_target_url()` in `src/build.py` converts whatever
  path is in `sources.json` into a syntactically-valid `file://` URL,
  normalizing to forward slashes either way (`C:/foo/bar.mov` ->
  `file:///C:/foo/bar.mov`, `/foo/bar.mov` -> `file:///foo/bar.mov`). This
  makes the URL well-formed for Resolve to parse on either OS - it does
  **not** make the media auto-relink across machines. A macOS-absolute path
  baked into the FCPXML will not exist on the Windows box, so those clips
  come in offline and still need a manual "Relink Selected Clips" pointing
  at the real files (`test/VERIFY.md` covers this). What this buys you is
  that the path Resolve *shows* while offline is one it can parse without
  choking on backslashes, not that it finds the file.
- **edl**: standard EDL has no field for a full path at all - only an
  8-character reel name per event (`REEL_NAMES` = `HOST`/`MOVIE`). The
  source path only appears in a `* FROM CLIP:` comment, which Resolve's EDL
  importer isn't expected to use for relinking. So EDL relinking is manual
  by reel name on every platform, macOS or Windows, generation machine or
  not - there's no cross-platform-specific behavior to get right here
  because there's no path-based relink path to begin with.

If a fully automatic cross-machine relink ever becomes a real requirement
(not just "the path doesn't crash the importer"), that needs Resolve's
Media Management / a relative-path or media-pool-relink workflow layered on
top - out of scope for this spike either way.

### Path capitalisation matters, even on macOS

macOS filesystems are case-*insensitive*, but the `file://` URL in the
FCPXML is read case-*sensitively* by Resolve's importer. So a
`sources.json` path of `/Users/you/movies/...` when the folder is really
`/Users/you/Movies/...` opens fine from Python, passes `os.path.exists()`,
and then imports into Resolve with the media reported **missing** - the
one failure mode where everything looks correct locally.

`resolve_true_case()` in `src/build.py` guards against this: before any
path is turned into a URL, each component is resolved against its real
on-disk capitalisation, and a correction is printed so you can fix
`sources.json` at the source:

```
Note: corrected host_clip case to match disk:
  /Users/doug/movies/Repo Man/repo man shortened.mp4
  -> /Users/doug/Movies/Repo Man/repo man shortened.mp4
```

It only applies to files present on the machine running `build.py` - a
path pointing at another machine's disk can't be checked and is passed
through untouched.

## ffmpeg/ffprobe

The `fcpx_xml` adapter shells out to `ffprobe` (part of the ffmpeg suite,
not a separate install) to embed the source media's real frame size into
the FCPXML `<format>` element - see `format_name()` in
`opentimelineio_contrib/adapters/fcpx_xml.py`. It's opportunistic, not
required:

- It only runs at all if the path in `sources.json` already exists on the
  machine running `build.py` (`os.path.exists(path)`) - with the shipped
  placeholder paths, or with real paths that only exist on a *different*
  machine, it's skipped entirely and `build.py` needs nothing on PATH.
- Even when it does run, a missing `ffprobe` binary is caught
  (`except (subprocess.CalledProcessError, OSError)`) and treated as
  "couldn't get the frame size" rather than a crash - the export still
  succeeds.
- The `edl`/`cmx_3600` path never touches this - it's fcpxml-only.

**ffmpeg isn't needed either way.** `fix_up_fcpxml()` writes the
`<format>` element's `width`/`height`/`name` from `sources.json`'s
`resolution` after the fact (fix 5 under "Known simplifications"), so the
frame size is embedded whether or not ffprobe ever ran. Installing ffmpeg
just means the adapter *also* reads it off the real file first; the
post-processing then overwrites it with the declared value regardless. If
`resolution` in `sources.json` disagrees with the actual media, the
declared value is what Resolve sees - so keep it accurate.

## Known simplifications (deliberate, for this test only)

- **Resolve doesn't import FCPXML clip markers - confirmed by hand, not a
  bug in this repo.** `build.py` writes a layout marker onto every clip
  (`clip.markers.append(...)` in `build_timeline()`), and it's genuinely
  present in `test/cut.fcpxml` (`grep marker test/cut.fcpxml` shows all 15).
  But after importing into Resolve, Index > Markers is empty - Resolve has
  never supported importing clip-level markers via FCPXML, from any tool,
  not just OTIO's. There's no fix on the writer side for this; it's a
  Resolve importer limitation. Layout visibility on the timeline comes
  entirely from the clip **name** (`01_hosts_full`, etc.), which does
  survive import - that's why the spec asked for both channels. The
  EDL path's equivalent (`* LOC:` comment, from the same OTIO marker -
  see `--format edl` above) has not been separately confirmed either way.
- **V2 is track presence, not visual compositing.** Every segment gets a
  second, correctly time-aligned movie clip on V2 (see "Video and audio
  layering" above), but
  `build.py` writes no transform/position/scale/blend elements - Resolve
  will stack both sources full-frame on top of each other on import. The
  actual picture-in-picture arrangement (host in a corner over the movie,
  or whatever the real composite should look like) still has to be built
  by hand in Resolve; this only guarantees both sources are present, in
  sync, ready to arrange.
- **Timeline seconds == source seconds, except for output position under
  `--mode compact`.** A segment's `start`/`end` are always its in/out point
  in the source media - there's no independent sync offset. Under
  `--mode inplace` they're also its position on the output timeline;
  under `--mode compact` (the default) the output position is instead
  wherever the previous segment left off, per the spec's real use case of
  collapsing a long source down to just its selected segments.
- **The adapter's raw output needs seven fixes before Resolve takes it;
  `fix_up_fcpxml()` in `src/build.py` applies them all** after
  `write_to_file()` returns:
  1. **`<project>` comes out unwrapped.** The adapter puts it as a direct
     child of `<fcpxml>`, sibling to `<resources>`. Final Cut Pro
     tolerates that, Resolve doesn't - it fails on import with `Unable to
     find inherited value for key "library". Line 4.`, because it expects
     to inherit format/library context down through
     `<library>`/`<event>`/`<project>`. Fixed by nesting it in a
     synthesized `<library><event>`.
  2. **~200 junk `<asset-clip>` bin items.** The adapter emits one per
     distinct clip *name*, each just re-pointing at one of the two real
     `<asset>` resources, all loose at the document root (not valid there
     either). Resolve turns each into its own Media Pool item, so the pool
     fills with entries named after segments (`03_panel`, `05_pip_circles_
     movie_audio`) that look like clips from files you never selected -
     they're all just the same two sources. The spine references the
     assets directly, so these are pure decoration; `fix_up_fcpxml()`
     drops them, leaving exactly one Media Pool item per real file.
  3. **Assets named after the wrong thing.** The adapter names an
     `<asset>` after whichever clip referenced it first, so the host
     source imported as `01_hosts_full`. Reset to the media file's own
     basename (`repo man shortened.mp4`), which is what you're actually
     relinking against.
  4. **No start timecode.** The adapter never writes `tcStart`/`tcFormat`
     on `<sequence>` (it doesn't read `Timeline.global_start_time` at all,
     so setting that in OTIO is a no-op). Set to `tcStart="3600s"` -
     01:00:00:00, the Resolve/broadcast convention - with `tcFormat`
     `DF` at 29.97fps and `NDF` otherwise. **Every top-level `<spine>`
     item's `offset` is shifted by the same hour to match**: a spine
     child's offset is its absolute position on the sequence's timeline,
     so leaving them at `0s` under a `3600s` tcStart puts the whole cut an
     hour before its own start and Resolve won't place the clips. Nested
     clips (the V2 lane) are deliberately *not* shifted - their offset
     is anchored to the parent clip's `start`, so shifting them too would
     desync every secondary clip from the V1 clip it hangs off.
  5. **A `<format>` with no frame size and an empty name.** The adapter
     only fills width/height in when it can `ffprobe` the media, and
     ffprobe isn't a dependency here - so the single `<format>` both
     assets inherit came out as
     `<format id="r1" frameDuration="1/30s" name=""/>`. Resolve needs the
     frame size to conform a clip, and an empty `name` is worse than an
     absent one. Both are now filled from `sources.json`'s `resolution`,
     with a Final Cut-style name (`FFVideoFormat1080p30`).
  6. **Audio wrapped in phantom `<gap>` elements.** The adapter models a
     clip as `<clip><video ref=.../></clip>` and has no way to say "this
     clip's audio comes too" - so getting sound required a separate OTIO
     audio track, which the adapter emitted as a `<gap name="Gap">`
     spanning the *entire* asset, nested inside the clip, with the
     `<audio>` hidden inside the gap. Resolve read those ~190 `name="Gap"`
     elements as a third piece of media to link and reported **"1 of 3
     clips were not yet found"** - there is no file called `Gap`.
     `rewrite_spine_as_asset_clips()` replaces the whole structure with
     `<asset-clip>`, which references an asset and brings its video *and*
     audio along - what Resolve itself exports. Connected clips (the movie
     on lane 1) become nested `<asset-clip>`s; the gap-wrapped audio is
     dropped entirely. This is also why `build_timeline()` builds no audio
     tracks at all.
  7. **`hasAudio="0"` on every asset.** Direct fallout of fix 6: the
     adapter decides `hasAudio` purely from whether a clip sits on an OTIO
     *audio* track (`_add_asset()`), and this timeline deliberately has
     none - so every asset came out flagged silent regardless of what the
     media actually contains, and an `<asset-clip>` only carries sound
     when its asset declares sound. `fix_up_fcpxml()` sets
     `hasAudio="1"` plus the descriptors FCPXML expects beside it
     (`audioSources`/`audioChannels`/`audioRate`, from the constants at
     the top of `build.py`). Those are declarations - Resolve reads the
     real channel count and rate off the media when it links - so they
     don't convert anything; they just have to be present.

  A connected clip's `offset` is also pinned to its parent's `start`
  rather than trusting the adapter's independently-derived value. The two
  are the same by construction (a V2 clip sits exactly on top of its V1
  clip for that clip's whole length), but the adapter lands a frame early
  on the occasional segment - 2 of 89 in the current data - and Resolve
  reads a connected clip that isn't frame-exact as not properly aligned,
  dropping its audio onto an extra track.

  If a future OTIO/adapter version starts emitting any of this correctly,
  the corresponding step becomes redundant and will fail loudly (e.g. "no
  `<project>` found") rather than silently double-applying.
- **Don't trust OTIO's own FCPXML *read* path for round-tripping.** This
  same bundled adapter's `read_from_file()` has its own, unrelated rate
  bug that reintroduces spurious gaps when reading `cut.fcpxml` back into
  OTIO. That's a flaw in this old contrib adapter's read half, not in the
  file `build.py` writes - the file's raw rational timecodes are internally
  consistent (verified directly against `edit.json` during development).
  The only read path that matters for this test is Resolve's own importer,
  which is exactly what `test/VERIFY.md` checks.

## fps handling

Only `23.976`, `29.97`, and `30` are accepted. `23.976`/`29.97` are
converted to their exact NTSC rational rate (`24000/1001` / `30000/1001`)
for all frame math, never rounded to a flat `24`/`30`; `30` is its own
distinct exact whole-number rate (`Fraction(30, 1)`), not a stand-in for
`29.97` - e.g. a screen recording that's genuinely 30.00fps, as opposed to
NTSC 29.97. Any other value in `sources.json` fails immediately with an
error rather than silently producing off-by-a-hair timing.

`sources.json`'s `fps` is the *project/timeline* rate, applied uniformly to
every segment's `start`/`end` regardless of which source it cuts from -
it's not required to match each source file's native rate. Mixing a
30.00fps host recording with 23.976 movie footage in one cut (this repo's
actual test case) is a normal editorial scenario; Resolve conforms the
off-rate source during playback the same way it would for any 23.976
footage cut into a 29.97/30 timeline. Pick whichever rate matches your
intended *delivery* timeline - usually whichever source makes up most of
the runtime.
