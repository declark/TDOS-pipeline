"""What the window shows about a project: stage status, the cut list, the
checker's findings and the research / review sheets.

Everything is read from the same files the scripts and skills write, through
the same loaders, so the app and the terminal can't disagree.
"""

import glob
import json
import os

import markdown

from build_timeline import BuildError, DEFAULT_CONFIG, load_config, load_cuts
import render_shorts
from check_cuts import InvalidCuts, run_checks, run_shorts_checks, words_paths
from convert_movie import needs_converting
from make_proxies import proxy_paths
from new_project import CUTS_DIR, project_path

MEDIA_SUFFIX = ".media.json"
MEDIA_LABELS = (("reaction_media", "Reaction recording"), ("movie_media", "Movie file"))

# Resolve's 16 clip colours, near enough to recognise a segment at a glance.
CLIP_COLOR_HEX = {
    "Orange": "#eb6e01", "Apricot": "#ffa833", "Yellow": "#d4ad1f", "Lime": "#9fc615",
    "Olive": "#5e9920", "Green": "#448f65", "Teal": "#00987f", "Navy": "#15627b",
    "Blue": "#4376a1", "Purple": "#996ebb", "Violet": "#d0568d", "Pink": "#e98cb5",
    "Tan": "#b9af97", "Beige": "#c4915e", "Brown": "#996601", "Chocolate": "#8c5a3f",
}


def cuts_file(slug, suffix):
    return os.path.join(CUTS_DIR, slug + suffix)


def read_media(slug):
    with open(project_path(slug), "r", encoding="utf-8") as handle:
        return json.load(handle)


def write_media(slug, media):
    with open(project_path(slug), "w", encoding="utf-8") as handle:
        json.dump(media, handle, indent=2, ensure_ascii=False)
        handle.write("\n")


def movie_offset(slug, media):
    """movie_offset_seconds from the media config, else from an existing cut list."""
    if media.get("movie_offset_seconds") is not None:
        return media["movie_offset_seconds"]
    try:
        _, meta = load_cuts(cuts_file(slug, ".json"))
    except (BuildError, ValueError):
        return None
    return meta.get("movie_offset_seconds")


def project_status(slug):
    media = read_media(slug)
    clips = []
    for key, label in MEDIA_LABELS:
        path = media.get(key) or ""
        clips.append({
            "key": key,
            "label": label,
            "path": path,
            "exists": bool(path) and os.path.exists(path),
            "transcribed": bool(path) and bool(words_paths(path)),
        })
    movie = media.get("movie_media") or ""
    has = {
        # None when the movie never was an .mkv, so there's nothing to convert.
        "converted": False if needs_converting(movie) else (
            True if needs_converting(media.get("movie_source")) else None),
        "transcripts": all(clip["transcribed"] for clip in clips),
        "research": os.path.exists(cuts_file(slug, ".research.md")),
        "cuts": os.path.exists(cuts_file(slug, ".json")),
        "draft": os.path.exists(cuts_file(slug, ".draft.json")),
        "review": os.path.exists(cuts_file(slug, ".review.md")),
        "shorts": os.path.exists(shorts_path(slug)),
        "tightened": is_tightened(slug),
        "proxies": all(
            media.get(key) and all(os.path.exists(p) for p in proxy_paths(media[key]))
            for key in ("reaction_media", "movie_media")),
    }
    return {
        "slug": slug,
        "title": media.get("title") or slug,
        "clips": clips,
        "offset": movie_offset(slug, media),
        "has": has,
    }


def is_tightened(slug):
    """True when the cut list as it stands has been through src/tighten_cuts.py."""
    path = cuts_file(slug, ".json")
    if not os.path.exists(path):
        return False
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return False
    return isinstance(data, dict) and bool(data.get("tightened"))


def list_projects():
    projects = []
    for path in glob.glob(os.path.join(CUTS_DIR, "*" + MEDIA_SUFFIX)):
        slug = os.path.basename(path)[:-len(MEDIA_SUFFIX)]
        try:
            projects.append(project_status(slug))
        except (OSError, ValueError) as error:
            projects.append({"slug": slug, "title": slug, "error": str(error)})
    return sorted(projects, key=lambda p: p["title"].lower())


def blockers(status, claude_found):
    """action -> why it can't run yet. An action that isn't listed can run."""
    has = status["has"]
    blocked = {}

    missing = [clip["label"] for clip in status["clips"] if not clip["exists"]]
    if missing:
        blocked["transcribe"] = "{} not found.".format(" and ".join(missing))
    elif has["converted"] is False:
        blocked["transcribe"] = "Convert the movie first."

    if has["converted"] is None:
        blocked["convert"] = "The movie isn't an .mkv."
    elif has["converted"] is False and "Movie file" in missing:
        blocked["convert"] = "Movie file not found."

    needs_inputs = None
    if not has["transcripts"]:
        needs_inputs = "Transcribe both clips first."
    elif status["offset"] is None:
        needs_inputs = "Set the movie offset first."

    for action, needs in (
        ("research", needs_inputs),
        ("make_cuts", needs_inputs),
        ("select_shorts", needs_inputs),
        ("short_feedback", None if has["shorts"] else "There's no shorts file yet."),
        ("select", needs_inputs or (None if has["research"] else "Research the film first.")),
        ("review", needs_inputs or (None if has["cuts"] else "Select the cuts first.")
         or (None if has["research"] else "Research the film first.")),
    ):
        if not claude_found:
            blocked[action] = "Claude Code isn't on PATH."
        elif needs:
            blocked[action] = needs

    if not has["cuts"]:
        blocked["dry_run"] = blocked["build"] = blocked["tighten"] = "There's no cut list yet."
    if missing:
        blocked["make_proxies"] = "{} not found.".format(" and ".join(missing))
    elif has["converted"] is False:
        blocked["make_proxies"] = "Convert the movie first."
    if not has["shorts"]:
        blocked["render_shorts"] = blocked["preview_shorts"] = blocked["tighten_shorts"] = \
            "There's no shorts file yet."
    return blocked


# --- the cut list -------------------------------------------------------------


def cut_list_path(slug, which):
    return cuts_file(slug, ".draft.json" if which == "draft" else ".json")


def cuts_view(slug, which="final"):
    cuts, meta = load_cuts(cut_list_path(slug, which))
    config = load_config(DEFAULT_CONFIG)
    colors = config["layout_colors"]

    total = sum(cut["end"] - cut["start"] for cut in cuts)
    seconds = {}
    for cut in cuts:
        seconds[cut["layout"]] = seconds.get(cut["layout"], 0.0) + cut["end"] - cut["start"]

    def hex_for(layout):
        return CLIP_COLOR_HEX.get(colors.get(layout), "#888888")

    mix = [
        {"layout": layout, "seconds": s, "share": 100.0 * s / total if total else 0.0,
         "color": hex_for(layout)}
        for layout, s in sorted(seconds.items(), key=lambda item: -item[1])
    ]
    segments, position = [], 0.0
    for cut in cuts:
        segments.append({
            "n": cut["index"] + 1,
            "start": cut["start"],
            "end": cut["end"],
            "at": position,
            "layout": cut["layout"],
            "color": hex_for(cut["layout"]),
            "film_beat": cut["film_beat"],
            "iconic": cut["iconic"],
            "reason": cut["reason"],
            "fix": cut["fix"],
        })
        position += cut["end"] - cut["start"]

    hook = meta.get("hook")
    return {
        "file": os.path.basename(cut_list_path(slug, which)),
        "total": total,
        "count": len(cuts),
        "flagged": sum(1 for cut in cuts if cut["fix"]),
        "offset": meta.get("movie_offset_seconds"),
        "hook": hook if isinstance(hook, (dict, str)) else None,
        "mix": mix,
        "segments": segments,
    }


def check_view(slug, which="final"):
    path = cut_list_path(slug, which)
    try:
        cuts, total, rows, fails, warns, notes = run_checks(path)
    except InvalidCuts as error:
        return {"invalid": str(error)}
    return {
        "file": os.path.basename(path),
        "count": len(cuts),
        "total": total,
        "mix": [{"name": name, "share": share, "target": target} for name, share, target in rows],
        "fails": fails,
        "warns": warns,
        "notes": notes,
    }


# --- shorts ---------------------------------------------------------------------


def shorts_path(slug):
    return cuts_file(slug, ".shorts.json")


def short_files(slug):
    """{number: path without extension} for every short's rendered files."""
    job = render_shorts.load_job(shorts_path(slug))
    out_dir = render_shorts.default_out_dir(job["media"])
    return {short["number"]: os.path.join(out_dir, render_shorts.output_base(job["title"], short))
            for short in job["shorts"]}


def shorts_view(slug):
    path = shorts_path(slug)
    if not os.path.exists(path):
        return {"exists": False}
    job = render_shorts.load_job(path)
    settings = render_shorts.load_settings()
    checks = {check["number"]: check for check in run_shorts_checks(path)}
    out_dir = render_shorts.default_out_dir(job["media"])

    shorts = []
    for short, raw in zip(job["shorts"], job["raw"]):
        base = os.path.join(out_dir, render_shorts.output_base(job["title"], short))
        video = base + ".mp4"
        rendered = os.path.exists(video)
        stale = False
        if rendered:
            try:
                with open(base + ".render.json", "r", encoding="utf-8") as handle:
                    signature = json.load(handle).get("signature")
            except (OSError, ValueError):
                signature = None
            stale = signature != render_shorts.short_signature(raw, job, settings)
        preview = base + ".preview.png"
        score = short.get("score") if isinstance(short.get("score"), dict) else {}
        check = checks[short["number"]]
        shorts.append({
            "number": short["number"],
            "name": short["name"],
            "type": short.get("type"),
            "yt_title": short.get("yt_title"),
            "hook_text": short.get("hook_text"),
            "description": short.get("description"),
            "score": sum(v for v in score.values() if isinstance(v, (int, float))) if score else None,
            "runtime": check["runtime"],
            "fails": check["fails"],
            "warns": check["warns"],
            "segments": [{
                "start": cut["start"], "end": cut["end"], "layout": cut["layout"],
                "reason": cut["reason"],
                "captions": None if cut["captions"] is None else [
                    {"who": c.get("who"), "text": c.get("text")} for c in cut["captions"]],
            } for cut in short["cuts"]],
            "video": int(os.path.getmtime(video)) if rendered else None,
            "stale": stale,
            "preview": int(os.path.getmtime(preview)) if os.path.exists(preview) else None,
        })
    return {
        "exists": True,
        "file": os.path.basename(path),
        "shorts": shorts,
        "out_dir": out_dir,
        "crop_x": job["media"].get("shorts_hosts_crop_x", settings["hosts_crop_x"]),
        "nudge": job["media"].get("shorts_sync_nudge_seconds") or 0,
    }


# --- the research and review sheets -------------------------------------------


def sheet_html(slug, kind):
    path = cuts_file(slug, ".review.md" if kind == "review" else ".research.md")
    with open(path, "r", encoding="utf-8") as handle:
        text = handle.read()

    renderer = markdown.Markdown(extensions=["tables", "fenced_code", "sane_lists"])
    # The research sheet is written from web pages, so no raw HTML gets through.
    renderer.preprocessors.deregister("html_block")
    renderer.inlinePatterns.deregister("html")
    return {"file": os.path.basename(path), "html": renderer.convert(text)}
