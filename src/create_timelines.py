#!/usr/bin/env python3
"""Create empty timelines in the currently open DaVinci Resolve project.

Names come from config/timelines.json - edit that file's "names" list rather
than passing names on the command line.

Two sets are made by default: the names as-is at the project's resolution
(the angles of the 16:9 multicam), and the same names plus the "vertical"
suffix at the vertical resolution (the angles of the portrait multicam that
shorts are cut from - see config/SHORTS.md). The vertical set goes in its own
top-level bin ("vertical" > "bin"); the 16:9 set goes in the current bin.

Usage:
    python src/create_timelines.py                  # both sets
    python src/create_timelines.py --set vertical   # just the vertical set
    python src/create_timelines.py --config config/timelines.json
"""

import argparse
import json
import os
import sys

# --- Resolve scripting bootstrap -------------------------------------------
# Same defaults as build_timeline.py. Environment wins, so a non-default
# Resolve install or a different OS can override without editing this file.

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


REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_CONFIG = os.path.join(REPO_ROOT, "config", "timelines.json")


class BuildError(Exception):
    """A problem the user needs to fix - reported without a traceback."""


def load_names(path):
    if not os.path.exists(path):
        raise BuildError("Config not found: {}".format(path))
    with open(path, "r", encoding="utf-8") as handle:
        config = json.load(handle)

    names = config.get("names")
    if not isinstance(names, list) or not names:
        raise BuildError("{}: \"names\" must be a non-empty JSON array.".format(path))

    empty = [i + 1 for i, n in enumerate(names) if not str(n).strip()]
    if empty:
        raise BuildError("{}: name(s) at position(s) {} are empty.".format(
            path, ", ".join(str(i) for i in empty)))

    vertical = config.get("vertical") or {}
    resolution = vertical.get("resolution", [1080, 1920])
    if not (isinstance(resolution, list) and len(resolution) == 2
            and all(isinstance(v, int) and v > 0 for v in resolution)):
        raise BuildError("{}: vertical \"resolution\" must be [width, height], got {!r}.".format(
            path, resolution))
    suffix = vertical.get("suffix", " Vertical")
    if not str(suffix).strip():
        raise BuildError("{}: vertical \"suffix\" can't be empty - the two sets would "
                         "share names.".format(path))

    bin_name = str(vertical.get("bin") or "").strip() or None
    return [str(n).strip() for n in names], {
        "suffix": suffix, "resolution": resolution, "bin": bin_name}


def plan_sets(names, vertical, which):
    """[(name, resolution or None, bin or None)] for the requested set(s), landscape first.

    A bin of None means the Media Pool's current bin.
    """
    plan = []
    if which in ("both", "landscape"):
        plan += [(name, None, None) for name in names]
    if which in ("both", "vertical"):
        plan += [(name + vertical["suffix"], vertical["resolution"], vertical["bin"])
                 for name in names]
    return plan


def get_or_create_bin(media_pool, name):
    """The top-level bin called `name`, created if it isn't there yet."""
    root = media_pool.GetRootFolder()
    for folder in root.GetSubFolderList() or []:
        if folder.GetName() == name:
            return folder
    folder = media_pool.AddSubFolder(root, name)
    if folder is None:
        raise BuildError("Resolve refused to create a bin named {!r}.".format(name))
    print("Created bin: {}".format(name))
    return folder


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


def existing_timeline_names(project):
    return {
        project.GetTimelineByIndex(i).GetName()
        for i in range(1, project.GetTimelineCount() + 1)
    }


def unique_name(base, taken):
    """Never collide with an existing timeline name."""
    if base not in taken:
        return base
    n = 2
    while "{} {}".format(base, n) in taken:
        n += 1
    return "{} {}".format(base, n)


def create_timelines(project, plan):
    media_pool = project.GetMediaPool()
    # CreateEmptyTimeline files a timeline in the current bin, so switch bins
    # per timeline and put the user's selection back afterwards.
    original_bin = media_pool.GetCurrentFolder()
    try:
        return _create_timelines(project, media_pool, plan, original_bin)
    finally:
        if original_bin is not None:
            media_pool.SetCurrentFolder(original_bin)


def _create_timelines(project, media_pool, plan, original_bin):
    taken = existing_timeline_names(project)
    bins = {}
    created = []
    for name, resolution, bin_name in plan:
        if bin_name is None:
            target = original_bin
        else:
            if bin_name not in bins:
                bins[bin_name] = get_or_create_bin(media_pool, bin_name)
            target = bins[bin_name]
        if target is not None and not media_pool.SetCurrentFolder(target):
            raise BuildError("Couldn't switch to bin {!r}.".format(bin_name or "current"))

        final_name = unique_name(name, taken)
        taken.add(final_name)
        timeline = media_pool.CreateEmptyTimeline(final_name)
        if timeline is None:
            raise BuildError("Resolve refused to create a timeline named {!r}.".format(final_name))
        created.append(final_name)
        if resolution is None:
            print("Created timeline: {}".format(final_name))
            continue
        width, height = resolution
        if timeline.SetSettings({
            "useCustomSettings": "1",
            "timelineResolutionWidth": str(width),
            "timelineResolutionHeight": str(height),
        }):
            print("Created timeline: {} ({}x{})".format(final_name, width, height))
        else:
            print("WARNING: created {!r} but couldn't set it to {}x{}; set it in the "
                  "timeline's settings by hand.".format(final_name, width, height),
                  file=sys.stderr)
    return created


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Create empty timelines in the currently open Resolve project."
    )
    parser.add_argument("--config", default=DEFAULT_CONFIG,
                        help="Timelines config JSON. Default: %(default)s")
    parser.add_argument("--set", choices=("both", "landscape", "vertical"), default="both",
                        help="Which set(s) to create. Default: %(default)s")
    args = parser.parse_args(argv)

    try:
        names, vertical = load_names(args.config)
        plan = plan_sets(names, vertical, args.set)
        resolve = connect_resolve()
        project = get_project(resolve)
        create_timelines(project, plan)
    except BuildError as exc:
        print("ERROR: {}".format(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
