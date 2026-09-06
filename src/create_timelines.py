#!/usr/bin/env python3
"""Create empty timelines in the currently open DaVinci Resolve project.

Names come from config/timelines.json - edit that file's "names" list rather
than passing names on the command line.

Usage:
    python3 src/create_timelines.py
    python3 src/create_timelines.py --config config/timelines.json
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

    return [str(n).strip() for n in names]


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


def create_timelines(project, names):
    media_pool = project.GetMediaPool()
    taken = existing_timeline_names(project)
    created = []
    for name in names:
        final_name = unique_name(name, taken)
        taken.add(final_name)
        timeline = media_pool.CreateEmptyTimeline(final_name)
        if timeline is None:
            raise BuildError("Resolve refused to create a timeline named {!r}.".format(final_name))
        created.append(final_name)
        print("Created timeline: {}".format(final_name))
    return created


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Create empty timelines in the currently open Resolve project."
    )
    parser.add_argument("--config", default=DEFAULT_CONFIG,
                        help="Timelines config JSON. Default: %(default)s")
    args = parser.parse_args(argv)

    try:
        names = load_names(args.config)
        resolve = connect_resolve()
        project = get_project(resolve)
        create_timelines(project, names)
    except BuildError as exc:
        print("ERROR: {}".format(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
