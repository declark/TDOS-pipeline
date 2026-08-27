# Next steps (paused mid-verification)

Where this spike stands as of the last session, and what to pick up.

## Status: core mechanism is basically proven

Verified by hand in Resolve, against the real files in
`~/movies/Repo Man/`:

- [x] FCPXML imports without error (see "Fixed" below - needed a code fix
      first)
- [x] 15 clips on one video track
- [x] Gaps land at the right spots (jumps between clips 3-4, 5-6, 7-8,
      9-10, 11-12, 13-14)
- [x] Frame-accurate in/out points (spot-checked `04_pip_host` at frame
      600 / 20s, matches `test/VERIFY.md`'s table)
- [x] Only two Media Pool items (not 15) - one per source, confirms
      clips sharing a source share one Media Pool entry
- [ ] **Not yet confirmed**: do the clip *names* on the timeline actually
      read `01_hosts_full`, `02_movie_full`, etc.? This is the last open
      checklist item - was asked, session paused before getting an answer.
      If yes, the spike's core goal is fully validated.

## Found and fixed this session

Two real bugs surfaced by testing against actual media (not the
placeholder paths) - both already fixed in `src/build.py`, already
verified against the real files:

1. **Unescaped spaces/parens in file paths broke the URL.**
   `to_media_target_url()` wasn't percent-encoding paths.
   `Repo Man (1984).mkv` has both a space and parens, which produced an
   invalid `file://` URL. Fixed with `urllib.parse.quote()`.
2. **Resolve rejected the FCPXML entirely on import**: `Unable to find
   inherited value for key "library". Line 4.` The pinned `fcpx_xml`
   adapter writes `<project>` as a bare sibling of `<resources>`, but
   Resolve requires it nested in `<library><event>`. Fixed with a new
   `wrap_fcpxml_project_in_library()` post-processing step in
   `write_timeline()`.

Also added mid-session, not a bug fix but new capability needed to use
the real files:
- **Exact `30fps` support.** The host recording is genuinely 30.00fps
  (not 29.97) - added as its own entry in `SUPPORTED_FPS`, not conflated
  with 29.97. `test/sources.json` is currently set to `fps: 30`.

## Confirmed limitation (not fixable, not a bug)

**DaVinci Resolve does not import FCPXML clip-level markers, from any
tool, ever** - confirmed via web search, it's a longstanding Resolve
limitation, not specific to OTIO or this repo. `build.py` writes a
marker on every clip and it IS present in `test/cut.fcpxml` (`grep marker
test/cut.fcpxml` shows all 15), but Resolve's Index > Markers panel comes
up empty after import regardless. Layout visibility on the timeline
comes entirely from the clip **name** channel instead - this is already
documented in the README and `test/VERIFY.md`.

Open question, not yet checked either way: does the EDL path's equivalent
(a `* LOC:` comment translated from the same OTIO marker) fare any
better on Resolve's *EDL* importer specifically? Different import
code path, so the FCPXML finding above doesn't necessarily predict it.

## Current `test/sources.json` (real values, not placeholders)

```json
{
  "host_clip": "/Users/doug/movies/Repo Man/Watch Repo Man.mov",
  "movie_clip": "/Users/doug/movies/Repo Man/Repo Man (1984).mkv",
  "fps": 30,
  "resolution": { "width": 1920, "height": 1080 }
}
```

Resolution is confirmed for the host clip (via `mdls`) but **not**
confirmed for the movie file (no ffprobe/mediainfo/exiftool available on
this Mac, and Spotlight had no video metadata for the `.mkv`). Doesn't
block anything - `resolution` is documentation-only per the existing
"Known simplifications" note (Resolve falls back to project default
either way).

`test/edit.json` still has its original 15 placeholder timestamps
(0-130s) - fine for this structural test since both source files run
much longer than that, but they're not meaningful content selections.

## To resume

`opentimelineio` isn't installed in this environment (system Python has
no venv with it set up persistently) - recreate one:

```
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python src/build.py --mode inplace              # regenerates test/cut.fcpxml
python src/build.py --mode inplace --format edl # regenerates test/cut.edl
```

Both are currently already regenerated and sitting in `test/` with all
the fixes above applied, so re-running isn't strictly necessary unless
you've changed `sources.json`/`edit.json` since.

1. Re-open the Resolve project, confirm the clip-name checklist item
   above (last thing asked before pausing).
2. Decide whether to also test `test/cut.edl` in Resolve - untested so
   far, and it's the format the original ask singled out as the likely
   long-term winner (see README's `--format` section: "If EDL works in
   Resolve, I want to drop the version pin and the contrib adapter
   entirely").
3. If EDL checks out: the README already documents exactly what dropping
   the pin requires (unpin `opentimelineio`, add `otio-cmx3600-adapter`,
   delete `patch_frame_duration_table()` / `_fcpx_xml_adapter_module()` /
   the fcpxml code path) - that's a deliberate follow-up, not done yet.

## Housekeeping (not urgent, just noted)

- **Nothing in this repo has been committed to git yet** - `git status`
  still shows every file as untracked, including the fixes above. Worth
  making an initial commit before this drifts further.
- `test/cut.fcpxml` and `test/cut.edl` are generated output, currently
  *not* covered by `.gitignore` (which only covers `.env`, media
  extensions, `__pycache__`) - decide if they should be ignored or
  checked in before committing.
- A stray `.DS_Store` is untracked at the repo root - not covered by
  `.gitignore` either.
