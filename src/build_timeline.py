#!/usr/bin/env python3
"""Build a DaVinci Resolve timeline from a cut list, using a predefined multicam clip.

Every segment in the cut list becomes one instance of the SAME multicam Media Pool
item, cut to the segment's in/out. The layout each segment is *meant* to use is
carried as the timeline clip's colour - the angle itself is switched by hand in
Resolve during review.

This talks to Resolve directly through its scripting API (Resolve Studio), so
there is no FCPXML/EDL intermediate and none of that format's limitations:
no file:// path escaping, no <library> wrapping, and no silently-dropped markers.

Nothing here is per-episode. The multicam clip is found by scanning the project,
the timeline is named after the cut list, and the config holds only things that
stay the same from one episode to the next.

Usage:
    python3 src/build_timeline.py --cuts cuts/<episode>.json --dry-run
    python3 src/build_timeline.py --cuts cuts/<episode>.json
"""

import argparse
import csv
import json
import os
import re
import sys
from fractions import Fraction

# --- Resolve scripting bootstrap -------------------------------------------
# Set before importing DaVinciResolveScript. Environment wins, so a non-default
# Resolve install or a Windows/Linux box can override without editing this file.

_DEFAULT_ENV = {
    "darwin": {
        "RESOLVE_SCRIPT_API": "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting",
        "RESOLVE_SCRIPT_LIB": "/Applications/DaVinci Resolve/DaVinci Resolve.app/Contents/Libraries/Fusion/fusionscript.so",
    },
    "win32": {
        "RESOLVE_SCRIPT_API": r"C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting",
        "RESOLVE_SCRIPT_LIB": r"C:\Program Files\Blackmagic Design\DaVinci Resolve\fusionscript.dll",
    },
    "linux": {
        "RESOLVE_SCRIPT_API": "/opt/resolve/Developer/Scripting",
        "RESOLVE_SCRIPT_LIB": "/opt/resolve/libs/Fusion/fusionscript.so",
    },
}


def _bootstrap_resolve_env():
    platform = "linux" if sys.platform.startswith("linux") else sys.platform
    defaults = _DEFAULT_ENV.get(platform, {})
    for key, value in defaults.items():
        os.environ.setdefault(key, value)
    api = os.environ.get("RESOLVE_SCRIPT_API")
    if api:
        modules = os.path.join(api, "Modules")
        if modules not in sys.path:
            sys.path.append(modules)


# --- fps --------------------------------------------------------------------
# Exact playback rates only. Anything else fails loudly rather than being
# rounded: 23.976 must never become a flat 24, 29.97 must never become a flat
# 30, and a genuine flat 30 (a screen recording, say) must never become 29.97.

SUPPORTED_FPS = {
    23.976: Fraction(24000, 1001),
    24: Fraction(24, 1),
    25: Fraction(25, 1),
    29.97: Fraction(30000, 1001),
    30: Fraction(30, 1),
    50: Fraction(50, 1),
    59.94: Fraction(60000, 1001),
    60: Fraction(60, 1),
}
FPS_TOLERANCE = 0.001

# Resolve's 16 clip colours. A colour outside this set is silently ignored by
# SetClipColor, which would leave segments unlabelled, so validate up front.
RESOLVE_CLIP_COLORS = {
    "Orange", "Apricot", "Yellow", "Lime", "Olive", "Green", "Teal", "Navy",
    "Blue", "Purple", "Violet", "Pink", "Tan", "Beige", "Brown", "Chocolate",
}

REQUIRED_CUT_FIELDS = ("start", "end", "layout")

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_CONFIG = os.path.join(REPO_ROOT, "config", "timeline.json")
CUTS_DIR = os.path.join(REPO_ROOT, "cuts")


class BuildError(Exception):
    """A problem the user needs to fix - reported without a traceback."""


def resolve_fps(value):
    """Map a config fps value to its exact Fraction, or fail loudly."""
    for known, rate in SUPPORTED_FPS.items():
        if abs(float(value) - float(known)) < FPS_TOLERANCE:
            return rate
    raise BuildError(
        "Unsupported fps {!r}. Supported: {}. Add it to SUPPORTED_FPS with its "
        "exact rate rather than letting it round to a neighbour.".format(
            value, ", ".join(str(f) for f in sorted(SUPPORTED_FPS))
        )
    )


def seconds_to_frames(seconds, rate):
    """Convert seconds to a frame index at an exact rate.

    Fraction keeps 29.97 and 23.976 exact all the way to the final rounding,
    so a 40-minute timeline doesn't accumulate drift the way repeated float
    multiplication does.
    """
    return int(round(Fraction(str(seconds)) * rate))


def frames_to_timecode(frames, rate):
    """Non-drop-frame timecode, for human-readable preflight output only."""
    fps_int = int(round(float(rate)))
    frames = int(frames)
    f = frames % fps_int
    total_seconds = frames // fps_int
    s = total_seconds % 60
    m = (total_seconds // 60) % 60
    h = total_seconds // 3600
    return "{:02d}:{:02d}:{:02d}:{:02d}".format(h, m, s, f)


def timecode_to_frames(timecode, rate):
    parts = timecode.split(":")
    if len(parts) != 4:
        raise BuildError(
            "timeline_start_timecode must be HH:MM:SS:FF, got {!r}".format(timecode)
        )
    try:
        h, m, s, f = (int(p) for p in parts)
    except ValueError:
        raise BuildError(
            "timeline_start_timecode must be HH:MM:SS:FF, got {!r}".format(timecode)
        )
    fps_int = int(round(float(rate)))
    return ((h * 3600 + m * 60 + s) * fps_int) + f


# --- input ------------------------------------------------------------------


def load_config(path):
    if not os.path.exists(path):
        raise BuildError("Config not found: {}".format(path))
    with open(path, "r", encoding="utf-8") as handle:
        config = json.load(handle)

    # multicam_clip_name and timeline_name are deliberately NOT required: both
    # are per-episode, and the point is that a new episode needs no config edit.
    missing = [k for k in ("fps", "layout_colors") if k not in config]
    if missing:
        raise BuildError(
            "Config {} is missing required key(s): {}".format(path, ", ".join(missing))
        )

    bad_colors = {
        layout: color
        for layout, color in config["layout_colors"].items()
        if color not in RESOLVE_CLIP_COLORS
    }
    if bad_colors:
        raise BuildError(
            "layout_colors has colours Resolve doesn't accept: {}.\nValid colours: {}".format(
                ", ".join("{}={}".format(k, v) for k, v in sorted(bad_colors.items())),
                ", ".join(sorted(RESOLVE_CLIP_COLORS)),
            )
        )

    config.setdefault("sync_offset_seconds", 0)
    config.setdefault("timeline_start_timecode", "01:00:00:00")
    config.setdefault("multicam_clip_name", None)  # None -> find it in the project
    config.setdefault("timeline_name", None)       # None -> name it after the cut list
    return config


def _coerce_cut_row(row, index, source):
    """Normalise one row from JSON or CSV into the internal cut shape."""
    missing = [f for f in REQUIRED_CUT_FIELDS if row.get(f) in (None, "")]
    if missing:
        raise BuildError(
            "{}: row {} is missing required field(s): {}".format(
                source, index + 1, ", ".join(missing)
            )
        )
    try:
        start = float(row["start"])
        end = float(row["end"])
    except (TypeError, ValueError):
        raise BuildError(
            "{}: row {} has non-numeric start/end ({!r}, {!r})".format(
                source, index + 1, row.get("start"), row.get("end")
            )
        )

    iconic = row.get("iconic", False)
    if isinstance(iconic, str):
        iconic = iconic.strip().lower() in ("true", "yes", "1", "y")

    return {
        "index": index,
        "start": start,
        "end": end,
        "layout": str(row["layout"]).strip(),
        "film_beat": row.get("film_beat") or None,
        "iconic": bool(iconic),
        "reason": row.get("reason") or "",
    }


def load_cuts(path):
    """Read a cut list from .json or .csv. Format is chosen by extension.

    Returns (cuts, meta). Per-episode facts belong in the cut list, not the
    config, so a wrapper object may carry them alongside the segments:

        { "title": "Repo Man", "movie_offset_seconds": 458,
          "segments": [ ... ] }

    That keeps config/timeline.json free of anything episode-specific.
    """
    if not os.path.exists(path):
        raise BuildError("Cut list not found: {}".format(path))

    ext = os.path.splitext(path)[1].lower()
    if ext == ".json":
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        meta = {}
        if isinstance(data, dict):
            # Tolerate a wrapper object, e.g. {"segments": [...]}
            for key in ("segments", "cuts", "edit"):
                if isinstance(data.get(key), list):
                    meta = {k: v for k, v in data.items() if k != key}
                    data = data[key]
                    break
        if not isinstance(data, list):
            raise BuildError(
                "{}: expected a JSON array of segments (or an object with a "
                "'segments'/'cuts'/'edit' array).".format(path)
            )
        rows = data
    elif ext == ".csv":
        meta = {}
        with open(path, "r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames:
                raise BuildError("{}: CSV has no header row.".format(path))
            header = [h.strip() for h in reader.fieldnames]
            missing = [f for f in REQUIRED_CUT_FIELDS if f not in header]
            if missing:
                raise BuildError(
                    "{}: CSV header is missing column(s): {}. Found: {}".format(
                        path, ", ".join(missing), ", ".join(header)
                    )
                )
            rows = [{(k.strip() if k else k): v for k, v in row.items()} for row in reader]
    else:
        raise BuildError(
            "Unsupported cut list format {!r}. Use .json or .csv.".format(ext)
        )

    if not rows:
        raise BuildError("{}: cut list is empty.".format(path))

    return [_coerce_cut_row(row, i, path) for i, row in enumerate(rows)], meta


def validate_cuts(cuts, config, rate):
    """Reject a cut list that would produce a wrong or confusing timeline."""
    errors = []
    known_layouts = set(config["layout_colors"])

    for cut in cuts:
        label = "segment {}".format(cut["index"] + 1)
        if cut["end"] <= cut["start"]:
            errors.append(
                "{}: end ({}) is not after start ({}).".format(
                    label, cut["end"], cut["start"]
                )
            )
        if cut["start"] < 0:
            errors.append("{}: start ({}) is negative.".format(label, cut["start"]))
        if cut["layout"] not in known_layouts:
            errors.append(
                "{}: unknown layout {!r}. Known layouts: {}.".format(
                    label, cut["layout"], ", ".join(sorted(known_layouts))
                )
            )
        if seconds_to_frames(cut["end"], rate) - seconds_to_frames(cut["start"], rate) < 1:
            errors.append(
                "{}: {}s-{}s is shorter than one frame at {} fps.".format(
                    label, cut["start"], cut["end"], float(rate)
                )
            )

    # The edit stays chronological (RULES.md), so out-of-order or overlapping
    # segments are a mistake in the cut list, not something to silently accept.
    for prev, cur in zip(cuts, cuts[1:]):
        if cur["start"] < prev["end"]:
            errors.append(
                "segments {} and {} overlap: {} ends at {}s, {} starts at {}s.".format(
                    prev["index"] + 1, cur["index"] + 1,
                    prev["index"] + 1, prev["end"],
                    cur["index"] + 1, cur["start"],
                )
            )

    if errors:
        raise BuildError(
            "Cut list has {} problem(s):\n  - {}".format(
                len(errors), "\n  - ".join(errors)
            )
        )


def plan_segments(cuts, config, rate):
    """Turn cuts into the frame ranges Resolve's AppendToTimeline wants.

    IMPORTANT: Resolve's clipInfo endFrame is EXCLUSIVE - verified empirically
    against Resolve Studio 20, where duration came back as endFrame - startFrame.
    (Much of the community documentation claims it is inclusive; it is not here.)
    So a segment covering the half-open range [start, end) in seconds - the same
    convention the FCPXML build used - passes endFrame = round(end*fps)
    unmodified. Subtracting one "for inclusivity" silently shortens every single
    segment by a frame, which is exactly the kind of error that survives a spot
    check - it is only visible by reading durations back out of the timeline.
    """
    offset = config["sync_offset_seconds"]
    plan = []
    for cut in cuts:
        start_frame = seconds_to_frames(cut["start"] + offset, rate)
        end_frame_exclusive = seconds_to_frames(cut["end"] + offset, rate)
        if start_frame < 0:
            raise BuildError(
                "segment {} starts at frame {} after applying sync_offset_seconds "
                "({}); it falls before the start of the multicam clip.".format(
                    cut["index"] + 1, start_frame, offset
                )
            )
        entry = dict(cut)
        entry["start_frame"] = start_frame
        entry["end_frame"] = end_frame_exclusive  # exclusive, per Resolve
        entry["duration_frames"] = end_frame_exclusive - start_frame
        entry["color"] = config["layout_colors"][cut["layout"]]
        plan.append(entry)
    return plan


def print_plan(plan, config, rate):
    """Preflight table - what will be laid down, before touching Resolve."""
    start_tc_frames = timecode_to_frames(config["timeline_start_timecode"], rate)
    fps_label = float(rate)

    print("")
    print("Multicam clip : {}".format(
        config.get("multicam_clip_name") or "auto (the project's only multicam)"))
    print("Timeline      : {}".format(
        config["timeline_name"]
        or "auto (Resolve project name, else {!r})".format(
            name_from_filename(config["cuts_path"]))))
    print("fps           : {} (exact {}/{})".format(
        fps_label, rate.numerator, rate.denominator))
    print("Start TC      : {}".format(config["timeline_start_timecode"]))
    print("Sync offset   : {}s".format(config["sync_offset_seconds"]))
    print("Segments      : {}".format(len(plan)))
    print("")
    print("  #  source in    source out   dur      timeline in   layout              colour")
    print("  -- ------------ ------------ -------- ------------- ------------------- ----------")

    record_frames = 0
    for entry in plan:
        print("  {:>2} {:<12} {:<12} {:>5}f {:<13} {:<19} {}".format(
            entry["index"] + 1,
            frames_to_timecode(entry["start_frame"], rate),
            frames_to_timecode(entry["end_frame"] - 1, rate),  # last frame shown
            entry["duration_frames"],
            frames_to_timecode(start_tc_frames + record_frames, rate),
            entry["layout"],
            entry["color"],
        ))
        record_frames += entry["duration_frames"]

    total_seconds = float(Fraction(record_frames) / rate)
    print("")
    print("Total runtime : {} frames = {:02d}:{:02d}:{:05.2f} ({:.1f} min)".format(
        record_frames,
        int(total_seconds // 3600),
        int((total_seconds % 3600) // 60),
        total_seconds % 60,
        total_seconds / 60.0,
    ))

    counts = {}
    for entry in plan:
        counts[entry["layout"]] = counts.get(entry["layout"], 0) + entry["duration_frames"]
    print("")
    print("Layout split by runtime:")
    for layout, frames in sorted(counts.items(), key=lambda kv: -kv[1]):
        share = 100.0 * frames / record_frames if record_frames else 0.0
        print("  {:<19} {:>6.1f}%  ({:.1f} min, {})".format(
            layout, share, float(Fraction(frames) / rate) / 60.0,
            config["layout_colors"][layout],
        ))
    print("")


# --- Resolve ----------------------------------------------------------------


def connect_resolve():
    _bootstrap_resolve_env()
    try:
        import DaVinciResolveScript as dvr
    except ImportError as exc:
        raise BuildError(
            "Couldn't import DaVinciResolveScript ({}).\n"
            "Checked RESOLVE_SCRIPT_API={!r}.\n"
            "Set RESOLVE_SCRIPT_API / RESOLVE_SCRIPT_LIB if Resolve is installed "
            "somewhere non-default.".format(exc, os.environ.get("RESOLVE_SCRIPT_API"))
        )

    resolve = dvr.scriptapp("Resolve")
    if resolve is None:
        raise BuildError(
            "Resolve isn't reachable. Open DaVinci Resolve Studio with your project, "
            "and make sure Preferences > System > General > 'External scripting using' "
            "is set to Local (or Network)."
        )
    return resolve


def get_project(resolve):
    project = resolve.GetProjectManager().GetCurrentProject()
    if project is None:
        raise BuildError("No project is open in Resolve.")
    return project


def iter_media_pool_items(folder):
    """Depth-first walk of the whole Media Pool, so bin nesting doesn't matter."""
    for item in folder.GetClipList() or []:
        yield item
    for sub in folder.GetSubFolderList() or []:
        for item in iter_media_pool_items(sub):
            yield item


def is_multicam(item):
    return (item.GetClipProperty("Type") or "").lower().startswith("multicam")


def find_multicam_item(media_pool, name=None):
    """Find the multicam clip to cut from.

    With no name, scan the project: if it holds exactly one multicam clip, that
    is unambiguously the one to use. This is what keeps the tool generic - a new
    episode means a new project with its own multicam, and no config to edit.
    Only a genuinely ambiguous project (two or more multicams) needs a name.
    """
    items = list(iter_media_pool_items(media_pool.GetRootFolder()))

    if name is None:
        multicams = [i for i in items if is_multicam(i)]
        if len(multicams) == 1:
            return multicams[0]
        if not multicams:
            raise BuildError(
                "No multicam clip in this project's Media Pool. Create one, or "
                "open the project that has it."
            )
        raise BuildError(
            "This project has {} multicam clips, so the target is ambiguous: {}.\n"
            "Pick one with --multicam \"<name>\".".format(
                len(multicams), ", ".join(sorted(i.GetName() for i in multicams))
            )
        )

    matches = [i for i in items if i.GetName() == name]
    if not matches:
        multicams = sorted(i.GetName() for i in items if is_multicam(i))
        hint = (
            "\nMulticam clips in this project: {}".format(", ".join(multicams))
            if multicams
            else "\nThis project has no multicam clips at all."
        )
        raise BuildError("No Media Pool item named {!r}.{}".format(name, hint))
    if len(matches) > 1:
        raise BuildError(
            "{} Media Pool items are named {!r}. Rename so the target is "
            "unambiguous.".format(len(matches), name)
        )

    item = matches[0]
    if not is_multicam(item):
        raise BuildError(
            "Media Pool item {!r} is of type {!r}, not a multicam clip.".format(
                name, item.GetClipProperty("Type") or "unknown"
            )
        )
    return item


def name_from_filename(cuts_path):
    """Prettify a cut list filename: "the-thing-1982.json" -> "The Thing 1982"."""
    stem = os.path.splitext(os.path.basename(cuts_path))[0]
    return " ".join(w.capitalize() for w in re.split(r"[-_\s]+", stem) if w) or "Cut"


def explicit_timeline_name(args_name, config_name, meta):
    """The name if one was actually stated, else None.

    Deliberately excludes the derived fallbacks: those need the open Resolve
    project, which isn't available during a dry run.
    """
    return args_name or config_name or (meta or {}).get("title") or None


def resolve_timeline_name(explicit, cuts_path, project):
    """Final name, in precedence order.

    --timeline-name > config > cut list "title" > Resolve project name > filename.

    The project name sits above the filename because the project is already
    named per episode, so a fixed cut list filename (cuts/current.json) needs no
    upkeep at all - no renaming, no title field. The filename only matters when
    the project name is somehow unusable.
    """
    if explicit:
        return str(explicit).strip()
    project_name = (project.GetName() or "").strip() if project else ""
    return project_name or name_from_filename(cuts_path)


def unique_timeline_name(project, base):
    """Never overwrite or duplicate-name an existing timeline."""
    existing = {
        project.GetTimelineByIndex(i).GetName()
        for i in range(1, project.GetTimelineCount() + 1)
    }
    if base not in existing:
        return base
    n = 2
    while "{} {}".format(base, n) in existing:
        n += 1
    return "{} {}".format(base, n)


def build_timeline(plan, config, rate):
    resolve = connect_resolve()
    project = get_project(resolve)
    media_pool = project.GetMediaPool()

    multicam = find_multicam_item(media_pool, config.get("multicam_clip_name"))
    print("Using multicam: {!r}".format(multicam.GetName()))

    clip_fps = multicam.GetClipProperty("FPS")
    if clip_fps:
        try:
            if abs(float(clip_fps) - float(rate)) > FPS_TOLERANCE:
                print(
                    "WARNING: multicam clip is {} fps but config says {}. Frame "
                    "conversion uses the config value, so every cut will drift. "
                    "Fix fps in the config before trusting this timeline.".format(
                        clip_fps, float(rate)
                    ),
                    file=sys.stderr,
                )
        except ValueError:
            pass

    name = unique_timeline_name(
        project,
        resolve_timeline_name(config["timeline_name"], config["cuts_path"], project),
    )
    timeline = media_pool.CreateEmptyTimeline(name)
    if timeline is None:
        raise BuildError("Resolve refused to create a timeline named {!r}.".format(name))
    if not project.SetCurrentTimeline(timeline):
        raise BuildError("Couldn't make {!r} the current timeline.".format(name))

    if not timeline.SetStartTimecode(config["timeline_start_timecode"]):
        print(
            "WARNING: couldn't set start timecode to {}; timeline keeps Resolve's "
            "default.".format(config["timeline_start_timecode"]),
            file=sys.stderr,
        )

    clip_infos = [
        {
            "mediaPoolItem": multicam,
            "startFrame": entry["start_frame"],
            "endFrame": entry["end_frame"],
            # mediaType is deliberately omitted. It is NOT a video+audio flag:
            # 1 means video only and 2 means audio only, so passing 1 lays down
            # a silent timeline. Omitting it brings both, which is what a
            # reaction cut needs.
        }
        for entry in plan
    ]
    # One AppendToTimeline call for the whole list: Resolve batches it as a
    # single undo step, and it's an order of magnitude faster than appending
    # segment by segment.
    appended = media_pool.AppendToTimeline(clip_infos)
    if not appended:
        raise BuildError(
            "AppendToTimeline returned nothing. The multicam clip may not cover "
            "the requested frame range - the last cut ends at frame {}.".format(
                plan[-1]["end_frame"]
            )
        )
    if len(appended) != len(plan):
        print(
            "WARNING: asked for {} segments, Resolve created {}. Colours are "
            "applied positionally, so verify the tail of the timeline by hand.".format(
                len(plan), len(appended)
            ),
            file=sys.stderr,
        )

    colored = 0
    for entry, item in zip(plan, appended):
        if item.SetClipColor(entry["color"]):
            colored += 1

    print("Created timeline {!r}: {} segments, {} coloured.".format(
        name, len(appended), colored))
    if colored != len(appended):
        print(
            "WARNING: {} segment(s) didn't take a colour.".format(len(appended) - colored),
            file=sys.stderr,
        )
    return name


# --- entry point ------------------------------------------------------------


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Build a Resolve timeline from a cut list using a predefined multicam clip."
    )
    parser.add_argument("--cuts", required=True,
                        help="Cut list (.json or .csv).")
    parser.add_argument("--config", default=DEFAULT_CONFIG,
                        help="Timeline config JSON. Default: %(default)s")
    parser.add_argument("--multicam", default=None,
                        help="Multicam clip name. Default: the project's only multicam.")
    parser.add_argument("--timeline-name", default=None,
                        help="Timeline name. Default: taken from the cut list.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print the plan and exit without touching Resolve.")
    args = parser.parse_args(argv)

    try:
        config = load_config(args.config)
        rate = resolve_fps(config["fps"])
        cuts, meta = load_cuts(args.cuts)

        # Precedence, most explicit first. Both fall back to something derived,
        # so neither ever needs to be set for a routine episode.
        if args.multicam:
            config["multicam_clip_name"] = args.multicam
        config["cuts_path"] = args.cuts
        config["timeline_name"] = explicit_timeline_name(
            args.timeline_name, config.get("timeline_name"), meta
        )
        validate_cuts(cuts, config, rate)
        plan = plan_segments(cuts, config, rate)
        print_plan(plan, config, rate)
        if args.dry_run:
            print("Dry run - Resolve was not touched.")
            return 0
        build_timeline(plan, config, rate)
    except BuildError as exc:
        print("ERROR: {}".format(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
