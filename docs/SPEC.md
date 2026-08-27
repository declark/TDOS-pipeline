Working in the existing empty repo at ./tdos-pipeline.

I'm building a pipeline that generates a DaVinci Resolve timeline from a JSON
edit list. Before building the rest, I need to verify that OpenTimelineIO can
produce FCPXML that Resolve imports correctly.

1. Add to the repo (it's initialized but empty, don't run git init):
   - .gitignore covering .env, *.mp4, *.mkv, *.mov, *.wav, __pycache__
   - requirements.txt with opentimelineio
   - README.md explaining what this test proves

2. Create test/edit.json with 15 hand-written segments. Schema per row:
   { "start": 842.10, "end": 848.60, "layout": "hosts_full", "note": "..." }
   Times are seconds from timeline zero. Vary durations between 2 and 12
   seconds. Include a few adjacent segments and a few with gaps between them.
   Leave the times as placeholders I'll replace with real ones.

3. Create test/sources.json as a template with: host_clip path, movie_clip
   path, fps, and timeline resolution. I'll fill in real values.

4. Write src/build.py that:
   - Reads sources.json and edit.json
   - Builds an OTIO timeline: one video track, one clip per segment,
     source_range set from the start/end times converted to frames at fps
   - Writes the layout value into each clip's name AND as an OTIO marker
     on the clip, so I can see it in Resolve after import
   - Exports FCPXML to test/cut.fcpxml
   - Takes --sources and --edit as CLI args, defaulting to the test files

5. Write test/VERIFY.md: a checklist of exactly what to confirm in Resolve
   after import. Clip count, in/out points frame-accurate against the JSON,
   media relinks, layout names visible.

Constraints:
- Python 3, standard library plus opentimelineio only
- No Resolve API, no environment variables, nothing requiring Resolve to run
- Frame conversion explicit and correct for both 23.976 and 29.97; fail
  loudly on an unhandled fps rather than rounding
- No media paths in edit.json, only in sources.json
- Media paths must be written into the FCPXML in a form Windows Resolve can
  resolve, since I may generate on macOS and import on Windows

Don't build transcription, selection, or validation yet. Just this.