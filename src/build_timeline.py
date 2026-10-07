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

A shorts file (cuts/<episode>.shorts.json, from config/SHORTS.md) builds one
vertical timeline per short instead, cut from the project's portrait multicam.

Usage:
    python src/build_timeline.py --cuts cuts/<episode>.json --dry-run
    python src/build_timeline.py --cuts cuts/<episode>.json
    python src/build_timeline.py --cuts cuts/<episode>.shorts.json --short 2
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
    config.setdefault("shorts_resolution", [1080, 1920])
    # Resolve has no red clip colour, so flagged segments take Orange (unused by
    # any layout) and also get a red timeline marker - see lay_down.
    config.setdefault("fix_color", "Orange")
    if config["fix_color"] not in RESOLVE_CLIP_COLORS:
        raise BuildError("fix_color {!r} isn't a Resolve clip colour. Valid colours: {}".format(
            config["fix_color"], ", ".join(sorted(RESOLVE_CLIP_COLORS))))
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
        # Optional review note: the segment needs reworking by hand. It gets
        # fix_color instead of its layout colour and a red marker carrying the note.
        "fix": str(row.get("fix") or "").strip(),
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


def is_shorts_file(path):
    """A shorts file is a JSON object with a "shorts" array (config/SHORTS.md)."""
    if os.path.splitext(path)[1].lower() != ".json" or not os.path.exists(path):
        return False
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    return isinstance(data, dict) and isinstance(data.get("shorts"), list)


def load_shorts(path):
    """Read a shorts file. Returns (shorts, meta).

    Each short is a dict with "name", the short's own metadata, and "cuts" in
    the same internal shape load_cuts produces.
    """
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    meta = {k: v for k, v in data.items() if k != "shorts"}
    if not data["shorts"]:
        raise BuildError("{}: shorts list is empty.".format(path))

    shorts = []
    for number, short in enumerate(data["shorts"], start=1):
        label = "{} short {}".format(path, number)
        if not isinstance(short, dict) or not isinstance(short.get("segments"), list) \
                or not short["segments"]:
            raise BuildError("{}: needs a non-empty 'segments' array.".format(label))
        entry = {k: v for k, v in short.items() if k != "segments"}
        entry["number"] = number
        entry["name"] = str(short.get("name") or "Short {}".format(number)).strip()
        entry["cuts"] = [
            _coerce_cut_row(row, i, label) for i, row in enumerate(short["segments"])
        ]
        shorts.append(entry)
    return shorts, meta


def validate_cuts(cuts, config, rate, chronological=True):
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

    # The long edit stays chronological (config/SKILL.md), so out-of-order or
    # overlapping segments are a mistake in the cut list, not something to
    # silently accept. Shorts are exempt: a flash-forward hook plays a reaction
    # first and may repeat it later (config/SHORTS.md).
    for prev, cur in zip(cuts, cuts[1:]) if chronological else ():
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
        entry["color"] = (config["fix_color"] if cut["fix"]
                          else config["layout_colors"][cut["layout"]])
        plan.append(entry)
    return plan


def print_plan_header(config, rate, timeline_label, multicam_label):
    print("")
    print("Multicam clip : {}".format(config.get("multicam_clip_name") or multicam_label))
    print("Timeline      : {}".format(timeline_label))
    print("fps           : {} (exact {}/{})".format(
        float(rate), rate.numerator, rate.denominator))
    print("Start TC      : {}".format(config["timeline_start_timecode"]))
    print("Sync offset   : {}s".format(config["sync_offset_seconds"]))


def print_plan(plan, config, rate):
    """Preflight table - what will be laid down, before touching Resolve."""
    print_plan_header(
        config, rate,
        config["timeline_name"]
        or "auto (Resolve project name, else {!r})".format(
            name_from_filename(config["cuts_path"])),
        "auto (the project's landscape multicam)",
    )
    print("Segments      : {}".format(len(plan)))
    print_plan_table(plan, config, rate)


def print_shorts_plan(shorts, config, rate, base_label):
    width, height = config["shorts_resolution"]
    print_plan_header(
        config, rate,
        "one per short, {}x{}, named \"{} Short <n> - <name>\"".format(
            width, height, base_label),
        "auto (the project's portrait multicam)",
    )
    print("Shorts        : {}".format(len(shorts)))
    for short in shorts:
        print("")
        print("=== Short {}: {} ===".format(short["number"], short["name"]))
        for key in ("yt_title", "hook_text"):
            if short.get(key):
                print("{:<13} : {}".format(key, short[key]))
        print_plan_table(short["plan"], config, rate)


def print_plan_table(plan, config, rate):
    start_tc_frames = timecode_to_frames(config["timeline_start_timecode"], rate)
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
            entry["color"] + ("  FIX: " + entry["fix"] if entry["fix"] else ""),
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
    flagged = [e for e in plan if e["fix"]]
    if flagged:
        print("")
        print("Flagged for fixing: {} segment(s), {:.1f}s (clip colour {}, red marker).".format(
            len(flagged), float(Fraction(sum(e["duration_frames"] for e in flagged)) / rate),
            config["fix_color"]))
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


def orientation(item):
    """"portrait" or "landscape" from a clip's Resolution ("1080x1920"), else None."""
    match = re.match(r"\s*(\d+)\s*x\s*(\d+)", item.GetClipProperty("Resolution") or "")
    if not match:
        return None
    width, height = int(match.group(1)), int(match.group(2))
    return "portrait" if height > width else "landscape"


def find_multicam_item(media_pool, name=None, want="landscape"):
    """Find the multicam clip to cut from.

    With no name, scan the project: if it holds exactly one multicam clip, that
    is unambiguously the one to use. This is what keeps the tool generic - a new
    episode means a new project with its own multicam, and no config to edit.

    A project with both the 16:9 multicam and a vertical one for shorts is
    still unambiguous: the long cut wants the landscape one, shorts the portrait
    one. Only two or more of the same orientation need a name.
    """
    items = list(iter_media_pool_items(media_pool.GetRootFolder()))

    if name is None:
        multicams = [i for i in items if is_multicam(i)]
        if not multicams:
            raise BuildError(
                "No multicam clip in this project's Media Pool. Create one, or "
                "open the project that has it."
            )
        matching = [i for i in multicams if orientation(i) == want]
        if len(matching) == 1:
            return matching[0]
        if len(multicams) == 1:
            # The only multicam is the wrong shape - e.g. shorts cut from the
            # 16:9 multicam into a vertical timeline, to be reframed by hand.
            print(
                "NOTE: no {} multicam in this project; using {!r} ({}).".format(
                    want, multicams[0].GetName(), orientation(multicams[0]) or "unknown shape"
                ),
                file=sys.stderr,
            )
            return multicams[0]
        raise BuildError(
            "This project has {} multicam clips and {} of them are {}, so the "
            "target is ambiguous: {}.\nPick one with --multicam \"<name>\".".format(
                len(multicams), len(matching), want,
                ", ".join(sorted(i.GetName() for i in multicams))
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


def open_multicam(config, rate, want):
    """Connect to Resolve and find the multicam to cut from, checking its fps."""
    resolve = connect_resolve()
    project = get_project(resolve)
    media_pool = project.GetMediaPool()

    multicam = find_multicam_item(media_pool, config.get("multicam_clip_name"), want)
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
    return project, media_pool, multicam


def extent_errors(plan, multicam):
    """Segments that run past the end of the multicam clip.

    AppendToTimeline doesn't say which segment it couldn't place - it just
    returns nothing - so catch this before Resolve is asked, per segment.
    Returns [] when the clip's length isn't readable.
    """
    try:
        total = int(multicam.GetClipProperty("Frames"))
    except (TypeError, ValueError):
        return []
    return [
        "segment {} ends at frame {} but multicam {!r} is only {} frames long.".format(
            entry["index"] + 1, entry["end_frame"], multicam.GetName(), total)
        for entry in plan
        if entry["end_frame"] > total
    ]


def build_timeline(plan, config, rate):
    project, media_pool, multicam = open_multicam(config, rate, "landscape")
    errors = extent_errors(plan, multicam)
    if errors:
        raise BuildError("\n  - ".join(["Cut list doesn't fit the multicam:"] + errors))
    name = unique_timeline_name(
        project,
        resolve_timeline_name(config["timeline_name"], config["cuts_path"], project),
    )
    return lay_down(project, media_pool, multicam, name, plan, config)


def build_shorts(shorts, config, rate, explicit_title):
    """Build every short it can. One bad short never stops the rest.

    Returns (built_names, failures), failures being "short N (name): why".
    """
    project, media_pool, multicam = open_multicam(config, rate, "portrait")
    base = resolve_timeline_name(explicit_title, config["cuts_path"], project)
    built, failures = [], []
    for short in shorts:
        label = "short {} ({})".format(short["number"], short["name"])
        errors = extent_errors(short["plan"], multicam)
        if errors:
            failures.append("{}: {}".format(label, " ".join(errors)))
            continue
        name = unique_timeline_name(
            project, "{} Short {} - {}".format(base, short["number"], short["name"])
        )
        try:
            built.append(lay_down(project, media_pool, multicam, name, short["plan"],
                                  config, resolution=config["shorts_resolution"]))
        except BuildError as exc:
            failures.append("{}: {}".format(label, exc))

    print("")
    print("Built {} of {} short(s).".format(len(built), len(shorts)))
    for failure in failures:
        print("  FAILED {}".format(failure), file=sys.stderr)
    return built, failures


def discard_timeline(media_pool, timeline):
    """Delete a timeline this run just created and couldn't fill."""
    if not media_pool.DeleteTimelines([timeline]):
        print("WARNING: couldn't remove empty timeline {!r}; delete it by hand.".format(
            timeline.GetName()), file=sys.stderr)


def lay_down(project, media_pool, multicam, name, plan, config, resolution=None):
    """Create timeline `name` and append the plan's segments to it."""
    timeline = media_pool.CreateEmptyTimeline(name)
    if timeline is None:
        raise BuildError("Resolve refused to create a timeline named {!r}.".format(name))
    if not project.SetCurrentTimeline(timeline):
        discard_timeline(media_pool, timeline)
        raise BuildError("Couldn't make {!r} the current timeline.".format(name))

    # Set before anything is appended, so clips are sized for the frame they
    # land in rather than rescaled after the fact.
    if resolution:
        width, height = resolution
        if not timeline.SetSettings({
            "useCustomSettings": "1",
            "timelineResolutionWidth": str(width),
            "timelineResolutionHeight": str(height),
        }):
            print(
                "WARNING: couldn't set {!r} to {}x{}; set it in the timeline's "
                "settings by hand.".format(name, width, height),
                file=sys.stderr,
            )

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
        # Don't leave an empty timeline behind: it would just push the next
        # attempt's name to "... 2".
        discard_timeline(media_pool, timeline)
        raise BuildError(
            "AppendToTimeline returned nothing. The multicam clip may not cover "
            "the requested frame range - the latest cut ends at frame {}.".format(
                max(entry["end_frame"] for entry in plan)
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

    # AppendToTimeline returns only the video timeline items, so the linked
    # audio clips keep Resolve's default colour and can't be selected by
    # colour. Colour them too, matching the plan positionally within each audio
    # track. Every segment came from the same multicam appended in order into a
    # fresh timeline, so the Nth clip on any audio track is the Nth segment.
    audio_colored = 0
    audio_total = 0
    for track in range(1, timeline.GetTrackCount("audio") + 1):
        items = timeline.GetItemListInTrack("audio", track) or []
        if len(items) != len(plan):
            print(
                "WARNING: audio track {} has {} clip(s) but the plan has {}; "
                "colouring by position may be misaligned, so verify by hand.".format(
                    track, len(items), len(plan)
                ),
                file=sys.stderr,
            )
        for entry, item in zip(plan, items):
            audio_total += 1
            if item.SetClipColor(entry["color"]):
                audio_colored += 1

    # Segments flagged with "fix" get a red marker spanning the segment, with the
    # note in it, so they're easy to find on the timeline and in the Edit Index.
    # AddMarker's frameId is an offset from the timeline start, not a timecode.
    flagged = [e for e in plan if e["fix"]]
    marked = 0
    record = 0
    for entry in plan:
        if entry["fix"] and timeline.AddMarker(
                record, "Red", "Fix: {}".format(entry.get("film_beat") or "host footage")[:60],
                entry["fix"], entry["duration_frames"]):
            marked += 1
        record += entry["duration_frames"]

    print("Created timeline {!r}: {} segments, {} video / {} audio clip(s) coloured.".format(
        name, len(appended), colored, audio_colored))
    if flagged:
        print("{} segment(s) flagged for fixing: {} red marker(s) added, clips coloured {}.".format(
            len(flagged), marked, config["fix_color"]))
        if marked != len(flagged):
            print("WARNING: {} fix marker(s) didn't take.".format(len(flagged) - marked),
                  file=sys.stderr)
    if colored != len(appended):
        print(
            "WARNING: {} video segment(s) didn't take a colour.".format(len(appended) - colored),
            file=sys.stderr,
        )
    if audio_total and audio_colored != audio_total:
        print(
            "WARNING: {} audio clip(s) didn't take a colour.".format(audio_total - audio_colored),
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
    parser.add_argument("--short", type=int, action="append", metavar="N",
                        help="Shorts file only: build just short N (1-based). Repeatable.")
    args = parser.parse_args(argv)

    try:
        config = load_config(args.config)
        rate = resolve_fps(config["fps"])
        if args.multicam:
            config["multicam_clip_name"] = args.multicam
        config["cuts_path"] = args.cuts

        if is_shorts_file(args.cuts):
            return run_shorts(args, config, rate)
        if args.short:
            raise BuildError("--short only applies to a shorts file (one with a "
                             "\"shorts\" array).")

        cuts, meta = load_cuts(args.cuts)

        # Precedence, most explicit first. Both fall back to something derived,
        # so neither ever needs to be set for a routine episode.
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


def run_shorts(args, config, rate):
    """Plan, and unless --dry-run build, one vertical timeline per short."""
    shorts, meta = load_shorts(args.cuts)
    if args.short:
        bad = [n for n in args.short if not 1 <= n <= len(shorts)]
        if bad:
            raise BuildError("--short {}: the file has shorts 1-{}.".format(
                ", ".join(str(n) for n in bad), len(shorts)))
        shorts = [s for s in shorts if s["number"] in set(args.short)]

    errors = []
    for short in shorts:
        try:
            validate_cuts(short["cuts"], config, rate, chronological=False)
            short["plan"] = plan_segments(short["cuts"], config, rate)
        except BuildError as exc:
            errors.append("short {} ({}): {}".format(short["number"], short["name"], exc))
    if errors:
        raise BuildError("\n".join(errors))

    title = explicit_timeline_name(args.timeline_name, config.get("timeline_name"), meta)
    print_shorts_plan(shorts, config, rate,
                      title or "<Resolve project name>")
    if args.dry_run:
        print("Dry run - Resolve was not touched.")
        return 0
    _, failures = build_shorts(shorts, config, rate, title)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
