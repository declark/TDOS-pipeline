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
python src/build.py --sources test/sources.json --edit test/edit.json \
    --format fcpxml --mode compact
```

All four flags default to the values shown above, so `python src/build.py`
alone is equivalent.

### `--format`: fcpxml | edl

- **fcpxml** (default) - via the pinned 0.16.0 `fcpx_xml` contrib adapter,
  same as before. Writes `test/cut.fcpxml`.
- **edl** - via OTIO's `cmx_3600` adapter, which is core OTIO code (it has
  never lived in `opentimelineio_contrib`), so the EDL path doesn't touch
  any of the `fcpx_xml`-specific, 0.16.0-pinned machinery in `build.py`
  (`patch_frame_duration_table()` etc.). Writes `test/cut.edl`. Since this
  edit is pure cuts on one video track, EDL (CMX 3600) is a much simpler
  format for the same result - `cmx_3600` only supports a single video
  track anyway, so it's a natural fit, not a limitation here. Each event's
  reel name comes from `REEL_NAMES` in `build.py` (`HOST`/`MOVIE`,
  <=8 chars, matching `cmx_3600`'s default reel-name limit) rather than the
  source file's basename, so Resolve's relink list reads cleanly. The
  layout marker also survives into the EDL as a `* LOC:` comment per event
  (OTIO translates clip markers to CMX locators) - worth checking in
  `test/VERIFY.md` whether Resolve's EDL importer surfaces that as an
  actual marker or just leaves it as an inert comment.

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
  succeeds, just without an embedded resolution (same fallback as the
  "Resolution isn't embedded yet" simplification below).
- The `edl`/`cmx_3600` path never touches this - it's fcpxml-only.

So: install ffmpeg if you want `sources.json`'s real media probed for
resolution on a machine that already has the actual files locally
(matters for `--format fcpxml`; EDL has no equivalent format-resolution
concept). Not installing it doesn't break anything.

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
- **One source per clip.** Each segment's `layout` value picks either
  `host_clip` or `movie_clip` as its single media reference (anything
  tagged `movie` uses `movie_clip`, everything else uses `host_clip`).
  Real picture-in-picture compositing isn't built yet - see
  `source_for_layout()` in `src/build.py`.
- **Timeline seconds == source seconds, except for output position under
  `--mode compact`.** A segment's `start`/`end` are always its in/out point
  in the source media - there's no independent sync offset. Under
  `--mode inplace` they're also its position on the output timeline;
  under `--mode compact` (the default) the output position is instead
  wherever the previous segment left off, per the spec's real use case of
  collapsing a long source down to just its selected segments.
- **Resolution isn't embedded yet.** The `fcpx_xml` adapter only writes a
  format's width/height when it can `ffprobe` the actual media file, which
  doesn't exist yet with placeholder paths. `resolution` in `sources.json`
  is documentation for now; Resolve will fall back to its project default
  until real media is relinked.
- **The `fcpx_xml` adapter writes `<project>` unwrapped; `build.py` patches
  it back in.** The adapter puts `<project>` as a direct child of
  `<fcpxml>`, sibling to `<resources>`. Final Cut Pro tolerates that, but
  Resolve's importer doesn't - it fails on import with `Unable to find
  inherited value for key "library". Line 4.`, because it expects to
  inherit format/library context down through `<library>`/`<event>`/
  `<project>` and there's no `<library>` ancestor to inherit from.
  `wrap_fcpxml_project_in_library()` in `src/build.py` rewrites the file
  after the adapter writes it, nesting `<project>` inside a synthesized
  `<library><event>`. If a future OTIO/adapter version starts writing this
  wrapper itself, this function becomes redundant (it'll just re-wrap
  something already correctly wrapped and fail with "no `<project>` found"
  as a loud signal to remove it, not a silent double-wrap - it only ever
  looks for a bare top-level `<project>`).
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
