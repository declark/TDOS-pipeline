# Verifying test/cut.fcpxml in Resolve

This checks one thing only: does the FCPXML that `src/build.py` writes
import into Resolve with the right structure? It does not test
transcription, segment selection, or layout compositing - none of that
exists yet.

Before importing, fill in real, absolute paths for `host_clip` and
`movie_clip` in `test/sources.json`, matching your actual fps (`23.976`,
`29.97`, or `30`), then regenerate. This checklist and its reference table assume
`--mode inplace` (segments kept at their source positions with gaps, so the
frame numbers below line up) - the default is now `--mode compact`
(segments appended back-to-back, no gaps), so pass `--mode inplace`
explicitly:

```
python src/build.py --mode inplace
```

For `--format edl` instead of the default `fcpxml`, see the EDL section at
the end of this file - most of the checklist below is fcpxml-specific.

## Import

1. In Resolve: File > Import > Timeline, choose `test/cut.fcpxml`.
2. If prompted about frame rate/format mismatch against the project, note
   what Resolve says (this is useful signal even if you proceed anyway).

## Checklist

- [ ] **Clip count.** The timeline has exactly **15 clips** on one video
      track (V1), separated by empty gaps where `edit.json` has time gaps.
      Count them in the timeline, not just the media pool.
- [ ] **Clip order.** Clip names read `01_hosts_full` through
      `15_hosts_full` in order, matching the reference table below.
- [ ] **In/out points frame-accurate.** For each clip, right-click >
      "Timeline Info" (or check the clip's position/duration in the
      timeline toolbar) and compare the clip's start frame and duration
      against the table below. These are timeline frame numbers at your
      source fps, computed as `round(seconds * fps)` - they will not be
      exact multiples of the JSON's decimal seconds, that's expected
      (29.97/23.976 aren't whole numbers of frames per second).
  - [ ] Frame 0 is the very start of the timeline (no leading gap, since
        segment 1 starts at `0.00`).
  - [ ] Gaps land where the table shows a jump between one clip's end
        frame and the next clip's start frame (segments 3->4, 5->6, 7->8,
        9->10, 11->12, 13->14).
- [ ] **Media relinks.** Resolve will likely show clips as offline/red
      (the FCPXML references whatever path you put in `sources.json`,
      which won't match Resolve's file system unless you generated and
      imported on the same machine). Use Media Pool > right-click >
      "Relink Selected Clips" and point both `host_clip` and `movie_clip`
      at your real files. Confirm:
  - [ ] Only **two** items need relinking in the Media Pool (not 15) -
        clips sharing a source should share one Media Pool item.
  - [ ] After relinking, clips play back at the correct in/out points
        (spot-check a couple against the table).
- [ ] **Layout names visible.** For each clip, confirm the layout value
      shows up in the clip's **name** on the timeline (e.g. `01_hosts_full`).
      `build.py` also writes the layout as an OTIO marker on each clip, and
      that marker *is* present in `test/cut.fcpxml` (`grep marker
      test/cut.fcpxml`) - but confirmed by hand: DaVinci Resolve's FCPXML
      importer does not bring clip-level markers in at all (check Index >
      Markers - it's empty even though the file has 15). This is a
      longstanding Resolve limitation, not a bug in what `build.py` writes
      or in `wrap_fcpxml_project_in_library()` - Resolve has never accepted
      markers via FCPXML from any source, confirmed independently of this
      project. The clip name is the channel that actually carries layout
      visibility into Resolve; the marker is inert data for any tooling
      that reads the FCPXML file directly (or re-imports it into OTIO),
      just not for Resolve's UI.

## Reference table (fps = 30, from the shipped `test/edit.json`)

If you changed `fps` or `edit.json`, regenerate this by hand - it's just
`round(seconds * fps)`. (This table was originally computed at 29.97, the
placeholder default; `test/sources.json` is currently set to `fps: 30` to
match the real host recording, so the table below is at 30 - a plain
`round(seconds * 30)`, no NTSC rational rounding involved.)

| clip name       | start frame | end frame | duration (frames) |
|-----------------|------------:|----------:|-------------------:|
| 01_hosts_full   |           0 |       240 |                 240 |
| 02_movie_full   |         240 |       375 |                 135 |
| 03_hosts_full   |         375 |       435 |                  60 |
| 04_pip_host     |         600 |       780 |                 180 |
| 05_pip_movie    |         780 |       900 |                 120 |
| 06_movie_full   |        1200 |      1560 |                 360 |
| 07_hosts_full   |        1560 |      1650 |                  90 |
| 08_pip_host     |        1800 |      1965 |                 165 |
| 09_pip_movie    |        1965 |      2100 |                 135 |
| 10_hosts_full   |        2400 |      2475 |                  75 |
| 11_movie_full   |        2475 |      2700 |                 225 |
| 12_hosts_full   |        3000 |      3180 |                 180 |
| 13_pip_host     |        3180 |      3240 |                  60 |
| 14_movie_full   |        3450 |      3810 |                 360 |
| 15_hosts_full   |        3810 |      3900 |                  90 |

## If it fails

- **Wrong clip count / merged clips**: check for duplicate clip names in
  `test/cut.fcpxml` (`grep 'asset-clip name'`) - the adapter silently skips
  creating a second `<asset-clip>` for a name it's already seen.
- **Frame numbers off by more than 1**: check `frameDuration` on the
  `<format>` element in `test/cut.fcpxml` isn't empty - see the
  `patch_frame_duration_table()` note in `src/build.py`.
- **Both sources show as one relink item**: means `host_clip` and
  `movie_clip` resolved to the same path in `sources.json` - fix the
  template.

## EDL (`--format edl`)

```
python src/build.py --mode inplace --format edl
```

Writes `test/cut.edl` instead of `test/cut.fcpxml`. Import via File >
Import > Timeline as usual. The clip-count/order/in-out-point checks above
still apply conceptually, but check them differently since EDL has no XML
to inspect casually:

- [ ] **Clip count / order** - same as above: 15 clips on V1, in order.
- [ ] **In/out points** - same reference table below applies (EDL events
      use the same frame numbers as the fcpxml `offset`/`start` values).
- [ ] **Relink** - only **two** reel names appear (`HOST`, `MOVIE` -
      `REEL_NAMES` in `src/build.py`), not 15 and not the source
      filenames. Unlike fcpxml, EDL never carries a full file path Resolve
      can use for relinking (see the README's "Media paths across
      platforms" section) - relink is always manual by reel name here.
- [ ] **Layout visibility** - EDL has no clip-name or marker field the way
      FCPXML does. Open `test/cut.edl` in a text editor and confirm each
      event has a `* FROM CLIP NAME:` comment with the layout
      (`01_hosts_full`, etc.) and a `* LOC:` comment with the layout name
      uppercased (e.g. `HOSTS_FULL`) - OTIO writes the clip's marker out as
      a CMX locator. Check in Resolve whether the `* LOC:` line actually
      becomes a visible marker on import, or stays inert - that's the one
      genuinely open question for this format, since Resolve's own EDL
      locator support is what's actually being tested here, not OTIO's
      writer.
